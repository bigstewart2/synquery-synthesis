#!/usr/bin/env python3
"""Content audit. Every check compares the RENDERED page against ground truth
(the transcripts and facts.json) and fails loudly. Nothing here trusts the
build; the build could be confidently wrong and still be internally consistent.

Run:  python3 verify.py
Exit: 0 clean, 1 with a numbered list of every discrepancy.
"""
import html as H
import json
import pathlib
import re
import sys
import unicodedata

import build as B

SITE = pathlib.Path(__file__).parent / "site" / "index.html"
DOC = SITE.read_text()
FACTS = B.FACTS
FAILS = []
CHECKS = 0


def fail(cat, msg):
    FAILS.append(f"[{cat}] {msg}")


def norm(s):
    """Compare on content, not on typography: unify quote marks, dashes, spaces."""
    s = unicodedata.normalize("NFKD", H.unescape(s))
    s = (s.replace("\u2019", "'").replace("\u2018", "'")
          .replace("\u201c", '"').replace("\u201d", '"')
          .replace("\u2014", "-").replace("\u2013", "-")
          .replace("\u2026", "..."))
    return re.sub(r"\s+", " ", s).strip().lower()


TRANSCRIPTS = {e: norm(B.redact((B.TXT / f).read_text()))
               for e, f in B.FILES.items()}
RAW = {e: (B.TXT / f).read_text() for e, f in B.FILES.items()}


# 1 ---------------------------------------------------------------- quotes real
def check_quotes_verbatim():
    global CHECKS
    for m in re.finditer(r'class="quote">&ldquo;(.*?)&rdquo;</span>\s*<span class="prov">(E\d)[^<]*?(\d\d:\d\d:\d\d)', DOC, re.S):
        raw, expert, ts = m.group(1), m.group(2), m.group(3)
        CHECKS += 1
        q = norm(re.sub(r"<[^>]+>", "", raw))
        if q not in TRANSCRIPTS[expert]:
            fail("QUOTE-NOT-IN-TRANSCRIPT", f"{expert} {ts}: {q[:80]!r}")


# 2 ------------------------------------------------- quote is at the cited turn
def turns(e):
    """Reuse build.parse() rather than a second parser -- a verifier with its own
    copy of the parsing logic drifts and reports the drift as a page defect."""
    return {t["ts"]: norm(B.redact(t["text"]))
            for t in B.parse(B.TXT / B.FILES[e])}


TURNS = {e: turns(e) for e in B.FILES}


def check_quote_timestamps():
    global CHECKS
    for m in re.finditer(r'class="quote">&ldquo;(.*?)&rdquo;</span>\s*<span class="prov">(E\d)[^<]*?(\d\d:\d\d:\d\d)', DOC, re.S):
        raw, e, ts = m.group(1), m.group(2), m.group(3)
        CHECKS += 1
        q = norm(re.sub(r"<[^>]+>", "", raw))
        turn = TURNS[e].get(ts)
        if turn is None:
            fail("TIMESTAMP-MISSING", f"{e} {ts} is not a turn in the transcript")
        elif q not in turn:
            fail("QUOTE-WRONG-TIMESTAMP",
                 f"{e} {ts} does not contain {q[:70]!r} (that turn says {turn[:70]!r})")


# 3 ------------------------------------------------- every rating matches facts
def check_ratings():
    global CHECKS
    truth = {}
    for r in FACTS["ratings"]:
        lab = B.CRIT_LABEL[r["criterion"]]
        for v, sc in r["scores"].items():
            truth[(r["expert"], lab, v)] = (sc, r["ts"])
    sec = DOC[DOC.index('id="ratings"'):]
    sec = sec[:sec.index("</section>")]
    rendered = {}
    for row in re.finditer(r'<tr class="critrow[^"]*"><td>(.*?)</td>(.*?)</tr>', sec, re.S):
        crit = H.unescape(re.sub(r"<span class=\"(compat|consensus)[^>]*>.*?</span>", "",
                                 row.group(1), flags=re.S)).strip()
        crit = re.sub(r"<[^>]+>", "", crit).strip()
        for cell in re.finditer(r'<td class="num"[^>]*data-v="(\w+)"(.*?)</td>', row.group(2), re.S):
            vendor = cell.group(1)
            for sc in re.finditer(r'data-e="(E\d)"[^>]*onclick="goto\(\'E\d\',\'([\d:]+)\'\)">([\d.]+)', cell.group(2)):
                rendered[(sc.group(1), crit, vendor)] = (float(sc.group(3)), sc.group(2))
    for k, (val, ts) in rendered.items():
        CHECKS += 1
        if k not in truth:
            fail("RATING-INVENTED", f"{k} rendered {val} but no such rating in facts.json")
        else:
            tv, tts = truth[k]
            if float(tv) != val:
                fail("RATING-WRONG", f"{k}: page says {val}, facts.json says {tv}")
            if tts != ts:
                fail("RATING-WRONG-TS", f"{k}: page links {ts}, facts.json says {tts}")
    for k in truth:
        if k not in rendered:
            fail("RATING-DROPPED", f"{k} is in facts.json but not on the page")
            CHECKS += 1


# 4 ------------------------------------------- numeric tables match facts.json
def check_numbers():
    global CHECKS
    for p in FACTS["pricing"]:
        CHECKS += 1
        want = f'${p["usd_per_user_month"]:g}'
        if want not in DOC:
            fail("PRICE-MISSING", f'{p["expert"]}/{p["vendor"]} {want} not rendered')
        lbl = B.basis_label(p["basis"])
        if "not paid" in p["basis"].lower() and lbl != "quoted, not paid":
            fail("BASIS-WRONG", f'{p["expert"]}/{p["vendor"]} basis rendered as {lbl}')
    for l in FACTS["loyalty"]:
        if l.get("scale_mismatch"):
            CHECKS += 1
            if "SCALE MISMATCH" not in DOC.upper():
                fail("SCALE-FLAG-MISSING", f'{l["expert"]} {l["ts"]} mismatch not flagged')


# 5 ------------------------------------------ transcript text matches the source
def check_transcript_render():
    global CHECKS
    for e in B.FILES:
        for ts, text in list(TURNS[e].items())[:400]:
            if not text:
                continue
            CHECKS += 1
            anchor = f'id="t-{e}-{ts.replace(":", "")}"'
            if anchor not in DOC:
                fail("TURN-NOT-RENDERED", f"{e} {ts} missing from transcripts tab")
                continue
            seg = DOC[DOC.index(anchor):][:4000]
            body = norm(re.sub(r"<[^>]+>", " ", seg.split("</div></div>")[0]))
            probe = " ".join(text.split()[:8])
            if probe and probe not in body:
                fail("TURN-TEXT-DRIFT", f"{e} {ts}: rendered text does not start with {probe!r}")


# 6 ------------------------------------------------- slide check atoms are real
def check_slidecheck():
    global CHECKS
    sec = DOC[DOC.index('id="slidecheck"'):]
    sec = sec[:sec.index("</section>")]
    for m in re.finditer(r"goto\('(E\d)','([\d:]+)'\)", sec):
        CHECKS += 1
        e, ts = m.group(1), m.group(2)
        if ts not in TURNS[e]:
            fail("SLIDE-ATOM-BAD-TS", f"{e} {ts} is not a real turn")
    n = len(re.findall(r'class="verdict', sec))
    CHECKS += 1
    if n != 5:
        fail("SLIDE-COUNT", f"{n} verdicts rendered, expected 5")


# 7 ------------------------------------------------------- no leaked identities
def check_redaction():
    global CHECKS
    CHECKS += 1
    try:
        B.check_banned(DOC)
    except SystemExit as ex:
        fail("REDACTION", str(ex))


for fn in (check_quotes_verbatim, check_quote_timestamps, check_ratings,
           check_numbers, check_transcript_render, check_slidecheck, check_redaction):
    fn()

print(f"content audit: {CHECKS} assertions across 7 categories")
if FAILS:
    print(f"\n{len(FAILS)} DISCREPANCIES\n")
    for i, f in enumerate(FAILS, 1):
        print(f"{i:3}. {f}")
    sys.exit(1)
print("all clean")
