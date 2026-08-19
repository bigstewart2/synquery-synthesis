#!/usr/bin/env python3
"""
Score extracted.json against the hand-verified facts.json ground truth.

Two independent checks, deliberately separated:

  1. CITATION INTEGRITY -- deterministic. Does every quote actually appear in the
     source transcript? This is the check that would fail a build in production.
     No model is involved and no judgement is required.

  2. VALUE AGREEMENT -- against hand-verified ground truth. Precision and recall
     per field group, with every disagreement printed so it can be adjudicated
     by hand rather than assumed to be a model error.
"""

import json
import pathlib
import re
import unicodedata

HERE = pathlib.Path(__file__).parent
CASE = pathlib.Path("/Users/stephenlese/dev/AI Projects/projects/career/companies/interviews/synquery/Case Study")
GT = json.loads((CASE / "analysis" / "facts.json").read_text())
EX = json.loads((HERE.resolve().parent / "out" / "extracted.json").read_text())
TDIR = CASE / "transcripts-txt"
FILES = {
    "E1": "Synquery FULL-transcript_ITSM Test_Expert1.txt",
    "E2": "Synquery_FULL-transcript_ITSM Test_Expert2.txt",
    "E3": "Synquery_FULL-transcript_ITSM Test_Expert3.txt",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("‐", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


TEXT = {k: norm((TDIR / v).read_text()) for k, v in FILES.items()}


def rule(t):
    print(f"\n{'=' * 68}\n{t}\n{'=' * 68}")


# --------------------------------------------------------------------------
rule("1. CITATION INTEGRITY  (deterministic, no ground truth needed)")

bad, total = [], 0
for e, groups in EX.items():
    if e.startswith("_"):
        continue
    for g, items in groups.items():
        for it in items:
            total += 1
            if norm(it["quote"]) not in TEXT[e]:
                bad.append((e, g, it["quote"][:90], it.get("timestamp")))

print(f"{total - len(bad)} of {total} quotes verified verbatim against source "
      f"({100 * (total - len(bad)) / total:.1f}%)")
if bad:
    print(f"\n{len(bad)} quote(s) NOT found in source -- these would fail the build:")
    for e, g, q, ts in bad:
        print(f"  [{e}/{g} @{ts}] {q}")

# --------------------------------------------------------------------------
rule("2. RANKED CRITERIA")

gt_rank = {}
for r in GT["ranked_criteria"]:
    gt_rank.setdefault(r["expert"], {})[r["rank"]] = r["criterion"].lower()
for e in ("E1", "E2", "E3"):
    got = {i["rank"]: i["criterion"].lower() for i in EX[e]["ranked_criteria"]}
    hits = sum(1 for k, v in gt_rank[e].items()
               if k in got and (v[:6] in got[k] or got[k][:6] in v))
    print(f"  {e}: {hits}/{len(gt_rank[e])} ranks match ground truth")
    for k in sorted(gt_rank[e]):
        g, o = gt_rank[e][k], got.get(k, "-- MISSING --")
        flag = "" if (g[:6] in o or o[:6] in g) else "   <-- differs"
        print(f"      {k}. gt={g:<38} model={o}{flag}")

# --------------------------------------------------------------------------
rule("3. RATINGS")

GT_RAW = []
for r in GT["ratings"]:
    for v, s in r["scores"].items():
        GT_RAW.append((r["expert"], r["criterion"], v, s))


def crit_key(c):
    c = c.lower().replace("_", " ")
    for k, pats in {
        "integration": ["integration"],
        "tco": ["cost", "tco", "ownership"],
        "scalability": ["scalab"],
        "user_experience": ["user experience", "ease of use", "usability"],
        "customization": ["customi"],
        "ease_of_administration": ["administ", "admin"],
        "compliance_workflow": ["compliance"],
        "asset_management": ["asset"],
    }.items():
        if any(p in c for p in pats):
            return k
    return c


gt_r = {(e, crit_key(c), v): sc for e, c, v, sc in GT_RAW}

ok = miss = extra = 0
disagree, extras = [], []
seen = set()
for e in ("E1", "E2", "E3"):
    for it in EX[e]["ratings"]:
        key = (e, crit_key(it["criterion"]), it["vendor"])
        seen.add(key)
        if key in gt_r:
            if abs(gt_r[key] - it["score"]) < 0.01:
                ok += 1
            else:
                disagree.append((key, gt_r[key], it["score"], it["quote"][:70]))
        else:
            extra += 1
            extras.append((key, it["score"], it["quote"][:70]))
missing = [k for k in gt_r if k not in seen]

print(f"  matched & agreed : {ok}")
print(f"  matched & differ : {len(disagree)}")
print(f"  in model, not gt : {extra}")
print(f"  in gt, not model : {len(missing)}")
print(f"  recall vs ground truth: {ok}/{len(gt_r)} = {100*ok/len(gt_r):.0f}%")
for k, g, m, q in disagree:
    print(f"    DIFFER {k}: gt={g} model={m}  | {q}")
for k in missing:
    print(f"    MISSED {k} (gt={gt_r[k]})")
for k, s, q in extras[:15]:
    print(f"    EXTRA  {k}={s}  | {q}")

# --------------------------------------------------------------------------
rule("4. PRICING (value + basis tag)")

gt_p = {(p["expert"], p["vendor"]): p for p in GT["pricing"]}
for e in ("E1", "E2", "E3"):
    for it in EX[e]["pricing"]:
        k = (e, it["vendor"])
        if k not in gt_p:
            print(f"    EXTRA {k} = {it['usd_per_user_month']}")
            continue
        g = gt_p[k]
        vok = abs(g["usd_per_user_month"] - it["usd_per_user_month"]) <= 3
        print(f"  {k}: gt={g['usd_per_user_month']} model={it['usd_per_user_month']} "
              f"{'ok' if vok else '<-- VALUE DIFFERS'}")
        print(f"      basis: gt='{g['basis'][:34]}' model='{it['basis']}'")
for k in gt_p:
    if not any(k == (e, i["vendor"]) for e in ("E1", "E2", "E3") for i in EX[e]["pricing"]):
        print(f"    MISSED {k}")

# --------------------------------------------------------------------------
rule("5. COMMERCIAL TERMS")

gt_c = {(c["expert"], c["field"]): c["value"] for c in GT["commercial_terms"]}
for e in ("E1", "E2", "E3"):
    for it in EX[e]["commercial_terms"]:
        k = (e, it["field"])
        g = gt_c.get(k)
        m = [it["low"], it["high"]]
        ok_ = g and abs(g[0] - m[0]) < 0.3 and abs(g[1] - m[1]) < 0.3
        print(f"  {k}: gt={g} model={m} {'ok' if ok_ else '<-- DIFFERS'}")

# --------------------------------------------------------------------------
rule("6. LOYALTY -- does the extractor preserve the scale mismatch?")

for e in ("E1", "E2", "E3"):
    for it in EX[e]["loyalty"]:
        mism = it["scale_asked_max"] != it["scale_answered_max"]
        print(f"  {e} {it['field']}: value={it['value']} "
              f"asked_max={it['scale_asked_max']} answered_max={it['scale_answered_max']}"
              f"{'   <-- MISMATCH CAUGHT' if mism else ''}")
print("\n  Ground truth: E1 continue_3yr is the only mismatch "
      "(interviewer asked 1-7, expert answered 9 out of 10).")

# --------------------------------------------------------------------------
rule("7. SWITCHING")

gt_s = {s["expert"]: s for s in GT["switching"] if "difficulty_1_10" in s}
gt_n = {s["expert"]: s.get("next_platform") for s in GT["switching"] if "next_platform" in s}
for e in ("E1", "E2", "E3"):
    for it in EX[e]["switching"]:
        d, g = it.get("difficulty_1_10"), gt_s.get(e, {}).get("difficulty_1_10")
        print(f"  {e}: difficulty gt={g} model={d} | next={it.get('next_platform')} "
              f"(gt={gt_n.get(e)})")
