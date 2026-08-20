#!/usr/bin/env python3
"""Build site/index.html: findings + ratings + linked transcripts + coverage + slide check."""
import json, pathlib, re, html

CASE = pathlib.Path("/Users/stephenlese/dev/AI Projects/projects/career/companies/interviews/synquery/Case Study")
FACTS = json.load(open(CASE / "analysis" / "facts.json"))
TXT = CASE / "transcripts-txt"
FILES = {
    "E1": "Synquery FULL-transcript_ITSM Test_Expert1.txt",
    "E2": "Synquery_FULL-transcript_ITSM Test_Expert2.txt",
    "E3": "Synquery_FULL-transcript_ITSM Test_Expert3.txt",
}
SEG = {"E1": "Large enterprise", "E2": "Regulated mid-market", "E3": "Lower mid-market"}
ROLE = {"E1": "Sr Dir, IT Infrastructure &amp; Ops", "E2": "Director, IT Service Management", "E3": "Head of IT Operations"}
ROLE_PLAIN = {"E1": "Sr Dir, IT Infrastructure & Ops", "E2": "Director, IT Service Management", "E3": "Head of IT Operations"}

SPK = re.compile(r"^(Expert \d|AI Interviewer)\s+(\d{2}:\d{2}:\d{2})\s*$")


# ---------------------------------------------------------------- redaction
def redaction_map():
    """Build {literal-term: replacement} purely from FACTS["experts"]. No banned literal
    is ever hardcoded in this file -- every key here is read out of facts.json at run time."""
    m = {}
    for ex in FACTS["experts"]:
        alias = ex.get("alias")
        if alias:
            m[alias] = "[name]"
        emp_disc = ex.get("employer_discussed")
        emp_body = ex.get("current_employer_named_in_body")
        if emp_disc and emp_body and emp_disc != emp_body:
            m[emp_disc] = "[prior employer]"
            m[emp_body] = "[employer]"
        else:
            if emp_disc:
                m[emp_disc] = "[employer]"
            if emp_body:
                m[emp_body] = "[employer]"
        for emp in (emp_disc, emp_body):
            if emp and " " in emp and emp in m:
                first = emp.split()[0]
                m.setdefault(first, m[emp])
        note = ex.get("redaction_note")
        if note:
            for cap in re.findall(r"'([A-Z][A-Za-z]+)'", note):
                m.setdefault(cap, "[employer]")
    return m


REDACT_MAP = redaction_map()
_REDACT_TERMS = sorted(REDACT_MAP, key=lambda t: -len(t))


def redact(s):
    for term in _REDACT_TERMS:
        repl = REDACT_MAP[term]
        if " " in term:
            s = re.sub(re.escape(term), repl, s)
        else:
            s = re.sub(r"\b" + re.escape(term) + r"\b", repl, s)
    return s


def parse(path):
    """-> list of {section|None, speaker, ts, text}"""
    raw = [l.rstrip() for l in open(path, encoding="utf8")]
    turns, cur, pending_section = [], None, None
    for line in raw:
        m = SPK.match(line.strip())
        if m:
            if cur:
                # trailing short line with no terminal punctuation = next section header
                while cur["lines"] and not cur["lines"][-1]:
                    cur["lines"].pop()
                if cur["lines"]:
                    last = cur["lines"][-1]
                    if len(last) < 70 and not re.search(r"[.?!\"”’)]$", last) and len(cur["lines"]) > 1:
                        pending_section = cur["lines"].pop()
                turns.append(cur)
            cur = {"speaker": m.group(1), "ts": m.group(2), "lines": [], "section": pending_section}
            pending_section = None
        elif cur is not None:
            if line.strip():
                cur["lines"].append(line.strip())
    if cur:
        turns.append(cur)
    for t in turns:
        t["text"] = " ".join(t["lines"])
    # first turn section
    if turns and not turns[0]["section"]:
        turns[0]["section"] = "Introduction"
    return turns


def anchor(e, ts):
    return f"t-{e}-{ts.replace(':', '')}"


# ---------------------------------------------------------------- findings
def findings_rows():
    rows = []

    def add(e, theme, takeaway, quote, ts, price_ref=None):
        r = dict(e=e, theme=theme, takeaway=takeaway, quote=quote, ts=ts)
        if price_ref:
            r["price_ref"] = price_ref
        rows.append(r)

    add("E2", "Cost & TCO",
        "ServiceNow was quoted at roughly 2.7x the per-seat price actually paid for BMC Helix, for a comparable module set.",
        "ServiceNow's quote came in closer to one-sixty for a comparable module set",
        "00:17:00", price_ref=("E2", "servicenow"))
    add("E3", "Cost & TCO",
        "ServiceNow was quoted at more than 3.75x the per-agent price paid for Freshservice.",
        "ServiceNow's quote for a comparable scope was north of one-fifty",
        "00:12:30", price_ref=("E3", "servicenow"))
    add("E1", "Cost & TCO",
        "Anchored ServiceNow at roughly $100 per user per month, with Zendesk at half that and Jira at a fifth.",
        "If we set ServiceNow at about $100 per user/month as a baseline, I'd put Zendesk at roughly $50-55. Jira was very inexpensive but lacked capabilities\u2014around $20-21.",
        "00:20:59", price_ref=("E1", "servicenow"))
    add("E1", "Cost & TCO",
        "Annual renewal uplift at the largest buyer was the smallest in the panel, at 3-5%.",
        "Yeah, it was somewhere around 3-5%.",
        "00:44:32")
    add("E3", "Cost & TCO",
        "The smallest buyer absorbs the largest annual increase, at 6-8%.",
        "increases have been around 6 to 8 percent each time",
        "00:13:29")

    add("E3", "Vendor selection",
        "ServiceNow was eliminated early on cost rather than on capability.",
        "We ruled out ServiceNow pretty quickly on cost; it felt like way more platform than we needed at our size.",
        "00:03:43")
    add("E2", "Vendor selection",
        "Four alternatives were weighed against BMC; Jira was ruled out early on CMDB and compliance depth.",
        "We looked at ServiceNow, Ivanti Neurons for ITSM, and Freshservice. We also briefly looked at Jira Service Management but ruled it out pretty early - it just didn't have the depth we needed for CMDB and compliance workflows.",
        "00:05:19")
    add("E1", "Vendor selection",
        "Would require a live demo first, then a short POC on a named integration, with customer references secondary.",
        "First, we'd want a live demo of the capabilities. From there, we might ask for customer references",
        "00:16:36")
    add("E1", "Vendor selection",
        "Competitors win on lower TCO and faster deployment.",
        "Yes, agreed.",
        "00:27:32")

    add("E1", "Compliance as funding trigger",
        "Counter-case. The funding argument led on scalability and growth, with GxP one clause inside it; "
        "escalation to a global programme came from complaints recurring across sites, not from compliance.",
        "The business case focused on scalability. We were growing\u2014from roughly a $20B company to about $30B\u2014and adding around 10-50K users.",
        "00:21:44")
    add("E2", "Compliance as funding trigger",
        "Reframing an IT refresh as compliance risk moved the decision up to a VP and the Head of Quality.",
        "Once I built the business case around compliance risk, it got elevated",
        "00:03:36")
    add("E3", "Compliance as funding trigger",
        "A SOC 2 requirement from the CFO's office, driven by financing partners, is what got leadership attention.",
        "It became more strategic once the SOC 2 requirement came from our CFO's office - that got leadership attention pretty fast.",
        "00:03:07")

    add("E1", "Implementation",
        "The 20-30% overrun was internal validation and UAT labour, not a platform defect; unbundled modules like GRC were a separate surprise.",
        "I'd say that added another 20-30% in cost. It's soft cost",
        "00:39:50")
    add("E2", "Implementation",
        "Went live in seven months, faster than expected, but 15% over budget, mostly the custom SAP integration plus unscoped Digital Workplace licences.",
        "It took about seven months from kickoff to go-live, which was faster than I expected",
        "00:13:20")
    add("E3", "Implementation",
        "Ten weeks contract to go-live, and only 5% over budget, with the overrun in extra agent seats.",
        "about ten weeks from contract to go-live",
        "00:10:00")

    add("E1", "Switching dynamics",
        "Rates switching difficulty at 7-8 out of 10, below ERP at 10, with a $1.0-1.5M cost and at least a year.",
        "This would be around 7-8. You'd still make a significant investment, around $1M-$1.5M, and invest a lot of time\u2014at least a year for implementation.",
        "00:52:09")
    add("E2", "Switching dynamics",
        "Would move to ServiceNow for its ecosystem and AI roadmap, budget permitting, since the switching cost is paid once either way.",
        "Probably ServiceNow at this point, just because if we're going to absorb switching costs anyway, I'd want the platform with the broadest long-term ecosystem and AI roadmap, assuming budget allowed it",
        "00:22:27")
    add("E3", "Switching dynamics",
        "Would also move to ServiceNow, and gave the same reason in almost the same words.",
        "Probably ServiceNow, just because if we're big enough to justify switching costs, I'd want the platform with the most long-term headroom",
        "00:17:11")
    add("E2", "Switching dynamics",
        "BMC's integrator pool is smaller than ServiceNow's, the same ecosystem gap he names at 00:22:27 as why ServiceNow would be his first look if he switched.",
        "Yes, that's fair. When we needed a specialized integration, our BMC partner pool was smaller, and it sometimes took longer to find someone who'd done exactly what we needed. With ServiceNow, there's just a much bigger community and more integrators to choose from.",
        "00:11:58")
    add("E3", "Switching dynamics",
        "Freshservice's automation builder gets clunky as approval chains grow, the exact limit he names at 00:16:44 as his switching trigger if the company tripled.",
        "Yeah, that's fair. We're starting to feel some of that as we've added more complex approval chains for the Project module. It's not a hard wall, but you notice the automation builder gets clunky once you're chaining a lot of conditional logic.",
        "00:08:50")
    return rows


CLIENT_THEMES = ["Cost & TCO", "Vendor selection", "Implementation", "Switching dynamics"]
SQ_THEMES = ["Compliance as funding trigger"]

# ---------------------------------------------------------------- evidentiary state
def basis_label(basis):
    """Order matters. "quoted, not paid" contains the substring "paid", so the
    negated forms are tested before the positive one -- the same
    longest-and-most-specific-first rule the redaction map uses."""
    b = basis.lower()
    if "not paid" in b or "quoted" in b:
        return "quoted, not paid"
    if "illustrative" in b or "baseline" in b:
        return "illustrative baseline"
    if "paid" in b:
        return "paid"
    return "recalled"


def spoken(entry, key):
    """Render the value as the expert stated it. facts.json stores a midpoint
    alongside a range for answers given as a band ("around 7-8"); the midpoint is
    fine to compute WITH and wrong to print AS speech. On a surface whose whole
    claim is traceability, a number nobody said is the worst kind of small error."""
    r = entry.get("range")
    if r and r[0] != r[1]:
        return f"{r[0]:g}-{r[1]:g}"
    return f"{entry[key]:g}"


def basis_verb(basis):
    """The same fact as basis_label, phrased as a verb so it reads as a sentence
    in client-facing prose rather than as a tag dropped mid-clause."""
    return {
        "paid": "was paid at",
        "quoted, not paid": "was quoted at, but not purchased for,",
        "illustrative baseline": "was anchored by the expert at",
        "recalled": "was recalled at",
    }[basis_label(basis)]


def check_basis_labels():
    """Regression guard for the substring-ordering bug that rendered every quoted
    price as a paid one. A price the client never paid must never be labelled paid
    anywhere in the deliverable -- that is the exact error this product exists to
    prevent, so it fails the build rather than warning."""
    cases = {
        "quoted, not paid": "quoted, not paid",
        "paid, blended across license tiers": "paid",
        "illustrative baseline set by expert for comparison, historical employer": "illustrative baseline",
        "recalled comparison": "recalled",
    }
    for raw, want in cases.items():
        got = basis_label(raw)
        if got != want:
            raise SystemExit(f"BASIS LABEL WRONG: {raw!r} -> {got!r}, expected {want!r}")
    for p in FACTS["pricing"]:
        if "not paid" in p["basis"].lower() and basis_label(p["basis"]) == "paid":
            raise SystemExit(
                f"BASIS LABEL WRONG: {p['expert']}/{p['vendor']} quoted price labelled paid")
    print(f"basis labels: {len(cases)} synthetic + {len(FACTS['pricing'])} real priced atoms, 0 mislabelled")


def evidence_tags(row, all_rows):
    """Every tag here is computed from facts.json / the findings list. No tag string
    is ever attached to a specific row as a literal."""
    tags = []

    bare = elab = False
    for flag in FACTS["data_quality_flags"]:
        if flag.get("expert") != row["e"]:
            continue
        ts = flag.get("ts")
        if ts is None:
            continue
        matched = (ts == row["ts"]) or (isinstance(ts, list) and row["ts"] in ts)
        if not matched:
            continue
        if flag["type"] == "leading_question_bare_acquiescence":
            bare = True
        elif flag["type"] == "leading_question_elaborated":
            elab = True

    if bare:
        tags.append(("confirmed on prompt, nothing added", True))
    elif elab:
        tags.append(("confirmed on prompt, expert added specifics", False))
    else:
        tags.append(("volunteered", False))

    if "price_ref" in row:
        pe, pv = row["price_ref"]
        fact = next(p for p in FACTS["pricing"] if p["expert"] == pe and p["vendor"] == pv)
        tags.append((basis_label(fact["basis"]), bare))

    exp = next(x for x in FACTS["experts"] if x["id"] == row["e"])
    if exp.get("employer_discussed") and exp.get("current_employer_named_in_body") \
            and exp["employer_discussed"] != exp["current_employer_named_in_body"]:
        tags.append(("prior employer", False))

    same_theme_experts = {r["e"] for r in all_rows if r["theme"] == row["theme"]}
    tags.append((f"theme spoken to by {len(same_theme_experts)} of 3 experts", False))

    return tags


# ---------------------------------------------------------------- ratings
CRIT_LABEL = {
    "integration": "Integration", "tco": "Cost / TCO", "user_experience": "Ease of use",
    "ease_of_use": "Ease of use", "scalability": "Scalability", "customization": "Customization",
    "compliance_workflow": "Compliance workflow", "ease_of_administration": "Ease of administration",
    "asset_management": "Asset management",
}
VENDORS = [("servicenow", "ServiceNow"), ("bmc", "BMC"), ("freshservice", "Freshservice"),
           ("ivanti", "Ivanti"), ("zendesk", "Zendesk"), ("jira", "Jira")]
VENDOR_DISPLAY = dict(VENDORS)


def ratings_grid():
    grid = {}
    for r in FACTS["ratings"]:
        lab = CRIT_LABEL[r["criterion"]]
        cell = grid.setdefault(lab, {})
        for v, s in r["scores"].items():
            cell.setdefault(v, []).append((r["expert"], s, r["ts"]))
    return grid


WHY = {
 ("E1","Scalability","servicenow"):"very scalable",
 ("E1","Cost / TCO","servicenow"):"very expensive",
 ("E1","Cost / TCO","jira"):"very economical",
 ("E1","Cost / TCO","bmc"):"also very expensive",
 ("E1","Ease of use","jira"):"has a really strong user experience",
 ("E1","Ease of use","zendesk"):"very simple; a simplified and easy-to-use experience, and so is the backend",
 ("E1","Ease of use","servicenow"):"can have its complexity depending on how you configure it",
 ("E1","Ease of use","bmc"):"probably a little bit easier to use",
 ("E1","Customization","servicenow"):"you can customise pretty much everything",
 ("E1","Customization","jira"):"has some customisation",
 ("E1","Customization","bmc"):"offers more customisation",
 ("E2","Integration","servicenow"):"ecosystem of connectors is just bigger",
 ("E2","Cost / TCO","servicenow"):"given how expensive it gets at scale",
 ("E2","Ease of administration","freshservice"):"probably the easiest",
 ("E2","Ease of administration","bmc"):"manageable for my small team, but there's a learning curve",
 ("E2","Ease of administration","servicenow"):"powerful but complex for a team our size",
 ("E2","Compliance workflow","bmc"):"an 8 for us specifically, because of the pharma-specific templates they had available",
 ("E2","Compliance workflow","servicenow"):"a 9 in raw capability, but you have to build a lot of it yourself",
 ("E2","Compliance workflow","ivanti"):"doable, but more custom work",
 ("E2","Compliance workflow","freshservice"):"really built more for lighter-weight IT support use cases",
 ("E3","Ease of use","zendesk"):"also strong there",
 ("E3","Ease of use","servicenow"):"powerful but a lot to configure",
 ("E3","Ease of use","ivanti"):"rated from prior experience, not current use",
 ("E3","Cost / TCO","servicenow"):"a 4 for a company our size",
 ("E3","Asset management","servicenow"):"strongest on paper, but it's overkill for us",
 ("E3","Asset management","freshservice"):"solid discovery agent, good enough for our needs",
 ("E3","Asset management","ivanti"):"the asset piece was actually decent",
 ("E3","Asset management","zendesk"):"weak here",
 ("E3","Integration","freshservice"):"the Azure AD sync was pretty painless",
 ("E3","Integration","servicenow"):"a 9 in raw capability",
 ("E3","Integration","ivanti"):"lots of manual config",
}
CRIT_KEY = {v: k for k, v in CRIT_LABEL.items()}


def consensus_marker(pts):
    """pts: list of (expert, score, ts). Ordered E1->E2->E3 (descending company size)."""
    ordered = sorted(pts, key=lambda p: p[0])
    vals = [p[1] for p in ordered]
    n = len(vals)
    if n == 1:
        return None
    if all(v == vals[0] for v in vals):
        return (f"unanimous {n}/{n}", "consensus-u")
    if n == 3 and (vals[0] < vals[1] < vals[2] or vals[0] > vals[1] > vals[2]):
        return (f"orders by company size, {n} raters, 1 per tier", "consensus-m")
    return (f"spread {max(vals) - min(vals):g}, n={n}", "consensus-c")


# ---------------------------------------------------------------- numeric tables
class Raw(str):
    """Marker: this cell is already-safe HTML, do not esc() it again."""
    pass


def expert_vendor(e):
    """The platform an expert's figures describe: their primary_vendor from
    facts.json, plus whether that deployment was at a prior employer. Derived
    entirely from FACTS["experts"] -- no expert-to-vendor mapping is hardcoded."""
    exp = next(x for x in FACTS["experts"] if x["id"] == e)
    name = VENDOR_DISPLAY.get(exp["primary_vendor"], exp["primary_vendor"])
    prior = bool(exp.get("employer_discussed") and exp.get("current_employer_named_in_body")
                 and exp["employer_discussed"] != exp["current_employer_named_in_body"])
    return name, prior


def vendor_cell(e):
    """Vendor name as a table cell, carrying the prior-employer tag where it applies."""
    name, prior = expert_vendor(e)
    tag = ' <span class="tag">prior employer</span>' if prior else ''
    return Raw(f'{esc(name)}{tag}')


def numeric_tables():
    """Every other typed number the guide asked for, as its own small table.
    Row shape: (*cells, expert, quote, ts) -- the renderer peels the last three,
    so a display column never doubles as the citation's expert id."""
    vmap = dict(VENDORS)
    vorder = {k: i for i, (k, _) in enumerate(VENDORS)}
    out = []

    # 1. price -- vendor is the first column and rows group by vendor,
    # ServiceNow first; the order comes from VENDORS, never hand-sorted.
    # The Vendor cell here is the row's SUBJECT vendor (the platform priced),
    # not the expert's primary vendor, so it carries no prior-employer tag;
    # E1's prior-employer signal stays in the basis tooltip as before.
    rows = []
    for p in sorted(FACTS["pricing"],
                    key=lambda p: (vorder.get(p["vendor"], len(VENDORS)), p["expert"])):
        op = p.get("operator", "")
        basis_html = Raw(f'<span title="{esc(p["basis"])}">{esc(basis_label(p["basis"]))}</span>')
        rows.append((vmap.get(p["vendor"], p["vendor"]), p["expert"],
                     f'{op}${p["usd_per_user_month"]:g}', basis_html,
                     p["expert"], p["quote"], p["ts"]))
    out.append(("Price per user per month",
                "Three different measurement bases sit in this column. A price someone pays and a price someone was quoted are not the same fact, so every row carries its basis and the product never lets them into one average.",
                ["Vendor", "Expert", "$/user/mo", "Basis"], rows))

    # 2. commercial + implementation -- measure-first row order kept; the new
    # Vendor column names the platform each figure describes.
    LBL = {"renewal_uplift_pct": "Annual renewal uplift", "implementation_months": "Implementation",
           "over_budget_pct": "Over initial budget"}
    UNIT = {"renewal_uplift_pct": "%", "implementation_months": " months", "over_budget_pct": "%"}
    rows = []
    for c in FACTS["commercial_terms"]:
        v = c["value"]
        val = f'{v[0]:g}-{v[1]:g}' if v[0] != v[1] else f'{v[0]:g}'
        rows.append((c["expert"], vendor_cell(c["expert"]), LBL.get(c["field"], c["field"]),
                     val + UNIT.get(c["field"], ""), c.get("cause", ""),
                     c["expert"], c["quote"], c["ts"]))
    out.append(("Commercial terms and implementation",
                "Five separate measures order the same way by company size, and two of them run opposite to intuition: the largest buyer gets the smallest annual increase and the smallest overrun. Three points cannot establish a slope, so this is a hypothesis worth three more interviews, not a trend.",
                ["Expert", "Vendor", "Measure", "Value", "Driver"], rows))

    # 3. loyalty + switching -- the Vendor column says who each score is about,
    # and rows group by vendor (stable sort keeps continue/recommend/switch order).
    LL = {"continue_3yr": "Likely to continue (3yr)", "recommend": "Likely to recommend"}
    rows = []
    for l in FACTS["loyalty"]:
        note = (f'SCALE MISMATCH: asked on {l["scale_asked"]}, answered {l["value"]} on {l["scale_answered"]}'
                if l.get("scale_mismatch") else (l.get("caveat", "") or f'asked on {l["scale_asked"]}'))
        rows.append((vendor_cell(l["expert"]), l["expert"], LL[l["field"]], str(l["value"]), note,
                     l["expert"], l["quote"], l["ts"]))
    for sw in FACTS["switching"]:
        if sw.get("difficulty_1_10") is not None:
            rows.append((vendor_cell(sw["expert"]), sw["expert"], "Switching difficulty (1-10)",
                         spoken(sw, "difficulty_1_10"), "", sw["expert"], sw["quote"], sw["ts"]))
    rows.sort(key=lambda r: vorder.get(
        next(x for x in FACTS["experts"] if x["id"] == r[-3])["primary_vendor"], len(VENDORS)))
    out.append(("Loyalty and switching",
                "One row is held out of every aggregate. At 00:44:58 the interviewer asked for a rating on a 1-7 scale and the expert answered 9 out of 10, and the interview moved on. A validator catches that every time; a human reading at volume will not.",
                ["Vendor", "Expert", "Measure", "Value", "Note"], rows))
    return out


def render_numeric():
    blocks = []
    for title, note, heads, rows in numeric_tables():
        th = "".join(f"<th>{esc(h)}</th>" for h in heads) + "<th>What we heard</th>"
        trs = []
        for r in rows:
            cells = r[:-3]
            e, quote, ts = r[-3], r[-2], r[-1]
            warn = ' class="weak"' if "MISMATCH" in str(cells[-1]) else ''
            tds = "".join(f"<td>{c if isinstance(c, Raw) else esc(c)}</td>" for c in cells)
            trs.append(f'<tr{warn}>{tds}<td><a class="qlink" onclick="goto(\'{e}\',\'{ts}\')">'
                       f'<span class="quote">&ldquo;{esc(redact(quote))}&rdquo;</span>'
                       f'<span class="prov">{ts} <b class="jump">open transcript &rsaquo;</b></span></a></td></tr>')
        blocks.append(f'<div class="card"><h2>{esc(title)}</h2><div class="scroll"><table><tr>{th}</tr>'
                      + "".join(trs) + f'</table></div><div class="note">{esc(note)}</div></div>')
    return "\n".join(blocks)


# ---------------------------------------------------------------- slide check
def slide_claims():
    claims = []

    # (a) ServiceNow best-in-class on integration
    int_rows = [r for r in FACTS["ratings"] if r["criterion"] == "integration"]
    int_by_e = {r["expert"]: r for r in int_rows}
    sn_scores = {e: int_by_e[e]["scores"].get("servicenow") for e in ("E1", "E2", "E3") if e in int_by_e}
    all_present = all(sn_scores.get(e) is not None for e in ("E1", "E2", "E3"))
    all_equal = all_present and len(set(sn_scores.values())) == 1
    comparable = "integration" in FACTS["criterion_comparability"]["rated_by_all_three"]
    best_each = all_present and all(sn_scores[e] >= max(int_by_e[e]["scores"].values()) for e in ("E1", "E2", "E3"))
    verdict_a = "SUPPORTED" if (all_present and all_equal and comparable and best_each) else "SUPPORTED WITH CAVEAT"
    if verdict_a == "SUPPORTED":
        reason_a = (f"All three experts rated ServiceNow {sn_scores['E1']:g}/10 on integration, the highest "
                    f"score they gave any vendor on that criterion, and integration is one of the two criteria "
                    f"the full panel rated.")
    else:
        reason_a = "The panel does not agree closely enough on this to support the claim as written."
    atoms_a = [(e, int_by_e[e]["ts"], f'{e}: ServiceNow {sn_scores[e]:g}/10 on integration')
               for e in ("E1", "E2", "E3") if e in sn_scores]
    claims.append(dict(
        claim="ServiceNow is rated best-in-class on integration.",
        verdict=verdict_a, reason=reason_a, atoms=atoms_a,
        footnote="Source: 3 of 3 expert interviews, one per size tier (large enterprise, regulated mid-market, lower mid-market). Each rated ServiceNow 9/10 on integration, the top score any of them gave any vendor on that criterion, and integration is one of only two criteria the full panel rated. The large-enterprise deployment was at a prior employer. Neither of the two who evaluated ServiceNow for their current platform bought it, and both still rated it top on integration, each naming cost as the reason they went elsewhere.",
    ))

    # (b) price ratio
    p_sn = next(p for p in FACTS["pricing"] if p["expert"] == "E2" and p["vendor"] == "servicenow")
    p_bmc = next(p for p in FACTS["pricing"] if p["expert"] == "E2" and p["vendor"] == "bmc")
    ratio = p_sn["usd_per_user_month"] / p_bmc["usd_per_user_month"]
    same_basis = p_sn["basis"] == p_bmc["basis"]
    verdict_b = "SUPPORTED" if same_basis else "SUPPORTED WITH CAVEAT"
    reason_b = (f"BMC {basis_verb(p_bmc['basis'])} ${p_bmc['usd_per_user_month']:g}/user/mo; "
                f"ServiceNow {basis_verb(p_sn['basis'])} ${p_sn['usd_per_user_month']:g}/user/mo. "
                + ("Same measurement basis." if same_basis else
                   "Different measurement bases, so the multiple is indicative, not audited."))
    atoms_b = [
        ("E2", p_bmc["ts"], f'E2: BMC ${p_bmc["usd_per_user_month"]:g}/user/mo, {basis_label(p_bmc["basis"])}'),
        ("E2", p_sn["ts"], f'E2: ServiceNow ${p_sn["usd_per_user_month"]:g}/user/mo, {basis_label(p_sn["basis"])}'),
    ]
    claims.append(dict(
        claim=f"ServiceNow costs roughly {ratio:.1f}x BMC per seat.",
        verdict=verdict_b, reason=reason_b, atoms=atoms_b,
        footnote="Source: 1 expert interview (regulated mid-market). BMC at roughly $60/user/mo blended, a price actually paid; ServiceNow at roughly $160/user/mo, a quote received but not purchased. Quoted and paid prices are different measurement bases, so treat the multiple as indicative, not audited. A quote precedes discounting while the paid figure follows it, so the mismatch leans one way and 2.7x reads high rather than uncertain in both directions. The same expert separately called ServiceNow almost triple the BMC quote, quote against quote and still near 3x, which suggests the lean is small.",
    ))

    # (c) switching difficulty falls with company size
    sw = {s["expert"]: s for s in FACTS["switching"] if "difficulty_1_10" in s}
    diffs = [sw[e]["difficulty_1_10"] for e in ("E1", "E2", "E3")]
    strictly_decreasing = diffs[0] > diffs[1] > diffs[2]
    industries = [next(x for x in FACTS["experts"] if x["id"] == e)["industry"] for e in ("E1", "E2", "E3")]
    industries_distinct = len(set(industries)) == len(industries)
    verdict_c = "SUPPORTED WITH CAVEAT" if strictly_decreasing else "NOT SUPPORTED BY THIS PANEL"
    caveat_c = " and each in a different industry, so size is confounded with industry" if industries_distinct else ""
    said = [spoken(sw[e], "difficulty_1_10") for e in ("E1", "E2", "E3")]
    incumbents = [next(x for x in FACTS["experts"] if x["id"] == e)["primary_vendor"] for e in ("E1", "E2", "E3")]
    vendor_confound = (" Each tier also runs a different incumbent platform, so the panel cannot separate "
                       "company size from entrenchment in a particular product."
                       if len(set(incumbents)) == len(incumbents) else "")
    reason_c = (f"Switching difficulty runs {said[0]}, {said[1]}, {said[2]} out of 10 in descending "
                f"company-size order. One respondent per size tier{caveat_c}.{vendor_confound}")
    atoms_c = [(e, sw[e]["ts"], f'{e}: switching difficulty {spoken(sw[e], "difficulty_1_10")}/10') for e in ("E1", "E2", "E3")]
    claims.append(dict(
        claim="Switching difficulty falls as company size falls.",
        verdict=verdict_c, reason=reason_c, atoms=atoms_c,
        footnote="Source: 3 expert interviews, one per company-size tier. Switching difficulty rated 7-8, 6 and 4 out of 10 in descending size order. One respondent per tier, and each tier also runs a different incumbent platform (ServiceNow, BMC Helix, Freshservice), so size cannot be separated from platform. Two of the three are life sciences firms. The largest respondent was asked a yes/no question that suggested difficulty was high, where the other two were asked open-ended. All three attribute difficulty to customisation depth and validation effort rather than to headcount.",
    ))

    # (d) 40% share claim
    assert not any("share" in k for k in FACTS), "share data unexpectedly present in facts.json"
    claims.append(dict(
        claim="ServiceNow holds 40% share of the mid-market.",
        verdict="NOT SUPPORTED BY THIS PANEL",
        reason="Nobody was asked about market share, and nothing in the panel measures it. Three interviews describe three individual buying decisions, not a sized market.",
        atoms=[],
        footnote="No defensible footnote exists for a share claim from this panel. Nearest supportable sentence: \"All three respondents evaluated ServiceNow and one had deployed it at a prior employer; the two who chose other platforms each named ServiceNow as the alternative they would probably evaluate first if they ever switched, one conditioning that on budget and one on being large enough to justify the switching costs (00:22:27, 00:17:11).\" Closing the gap needs a sized survey or third-party share data.",
    ))

    # (e) Ivanti underperforms on integration
    cov = FACTS["coverage"]
    ivanti_never_owned = "ivanti" in cov["vendors_rated_but_never_owned_by_anyone_in_panel"]
    verdict_e = "NOT SUPPORTED BY THIS PANEL" if ivanti_never_owned else "SUPPORTED"
    reason_e = cov["known_gaps"][0]
    e2 = next(x for x in FACTS["experts"] if x["id"] == "E2")
    e3 = next(x for x in FACTS["experts"] if x["id"] == "E3")
    iv_e2 = next(r for r in FACTS["ratings"] if r["expert"] == "E2" and r["criterion"] == "integration")
    iv_e3 = next(r for r in FACTS["ratings"] if r["expert"] == "E3" and r["criterion"] == "integration")
    atoms_e = [
        ("E2", iv_e2["ts"], f'E2 (primary vendor {VENDOR_DISPLAY.get(e2["primary_vendor"], e2["primary_vendor"])}): '
                             f'Ivanti {iv_e2["scores"]["ivanti"]:g}/10 on integration'),
        ("E3", iv_e3["ts"], f'E3 (primary vendor {VENDOR_DISPLAY.get(e3["primary_vendor"], e3["primary_vendor"])}): '
                             f'Ivanti {iv_e3["scores"]["ivanti"]:g}/10 on integration'),
    ]
    claims.append(dict(
        claim="Ivanti underperforms on integration.",
        verdict=verdict_e, reason=reason_e, atoms=atoms_e,
        footnote="Not paste-able as a client-facing footnote; the panel has no Ivanti-primary respondent. Commission an Ivanti-primary interview before claiming anything about Ivanti's integration performance.",
    ))

    return claims


def render_slidecheck():
    verdict_class = {
        "SUPPORTED": "verdict-s",
        "SUPPORTED WITH CAVEAT": "verdict-w",
        "NOT SUPPORTED BY THIS PANEL": "verdict-n",
    }
    cards = []
    for c in slide_claims():
        atoms_html = "".join(
            f'<li><a class="qlink" onclick="goto(\'{e}\',\'{ts}\')">{esc(label)} <b class="jump">open transcript &rsaquo;</b></a></li>'
            for e, ts, label in c["atoms"]
        )
        vcls = verdict_class[c["verdict"]]
        ft_attr = html.escape(c["footnote"], quote=True)
        cards.append(
            f'<div class="card claim"><div class="slideline">{esc(c["claim"])}</div>'
            f'<span class="verdict {vcls}">{esc(c["verdict"])}</span>'
            f'<p>{esc(c["reason"])}</p>'
            f'<ul class="atoms">{atoms_html}</ul>'
            f'<div class="footnote"><span class="fttext">{esc(c["footnote"])}</span> '
            f'<button class="copy" data-text="{ft_attr}">copy footnote</button></div></div>'
        )
    return "\n".join(cards)



GAP_OVERRIDES = {
    "No expert who actually migrated away from ServiceNow to a competitor and stayed there.":
        "No expert who migrated from ServiceNow to a rival commercial platform and stayed. The closest case is "
        "E1&rsquo;s current employer, which replaced ServiceNow with a custom in-house tool before he joined and "
        "is now weighing buying the asset-management module back.",
}


def gap_text(g):
    return GAP_OVERRIDES.get(g, g)


# ---------------------------------------------------------------- render
def esc(s):
    return html.escape(str(s), quote=False)


def r_key(cell, crit):
    """Ease of use is stored as user_experience for E1 and ease_of_use for E3."""
    return CRIT_KEY.get(crit, "")


def render():
    out = []
    A = out.append

    # ---- transcripts
    tabs_tx, toc_all = [], []
    for e, fn in FILES.items():
        turns = parse(TXT / fn)
        toc, body = [], []
        for i, t in enumerate(turns):
            if t["section"]:
                sid = f"s-{e}-{i}"
                toc.append(f'<li><a href="#{sid}" onclick="return jump(\'{sid}\')">{esc(redact(t["section"]))}</a></li>')
                body.append(f'<h4 id="{sid}" class="sect">{esc(redact(t["section"]))}</h4>')
            who = "Interviewer" if t["speaker"] == "AI Interviewer" else f"Expert {e[1]}"
            cls = "ai" if t["speaker"] == "AI Interviewer" else "ex"
            body.append(
                f'<div class="turn {cls}" id="{anchor(e, t["ts"])}">'
                f'<div class="meta"><b>{who}</b> <span class="ts">{t["ts"]}</span></div>'
                f'<div class="say">{esc(redact(t["text"]))}</div></div>'
            )
        tabs_tx.append((e, "\n".join(toc), "\n".join(body)))

    # ---- findings
    rows = findings_rows()
    counts = {}
    for r in rows:
        counts[r["theme"]] = counts.get(r["theme"], 0) + 1

    rail = [f'<button class="on" data-th="ALL">All <span class="n">{len(rows)}</span></button>']
    rail.append('<div class="railgrp">Outlined by your team</div>')
    for th in CLIENT_THEMES:
        rail.append(f'<button data-th="{esc(th)}">{esc(th)} <span class="n">{counts.get(th,0)}</span></button>')
    rail.append('<div class="railgrp sq">Proposed by Synquery</div>')
    for th in SQ_THEMES:
        rail.append(f'<button class="sq" data-th="{esc(th)}">{esc(th)} <span class="n">{counts.get(th,0)}</span></button>')

    frows = []
    for r in rows:
        tags = evidence_tags(r, rows)
        weak = ' weak' if any(w for _, w in tags) else ''
        sq = ' sq' if r["theme"] in SQ_THEMES else ''
        tags_html = "".join(f'<span class="tag{" weak" if w else ""}">{esc(t)}</span>' for t, w in tags)
        copy_text = f'{r["takeaway"]} “{r["quote"]}” — {ROLE_PLAIN[r["e"]]}, {SEG[r["e"]]} interview, {r["ts"]}'
        data_text = html.escape(copy_text, quote=True)
        frows.append(f'''<tr class="frow{weak}" data-th="{esc(r["theme"])}" data-e="{r["e"]}">
<td>{r["e"]}<span class="prov">{ROLE[r["e"]]}<br>{SEG[r["e"]]}</span></td>
<td><span class="thchip{sq}">{esc(r["theme"])}</span></td>
<td>{esc(r["takeaway"])}</td>
<td><a class="qlink" onclick="goto('{r["e"]}','{r["ts"]}')"><span class="quote">&ldquo;{esc(redact(r["quote"]))}&rdquo;</span>
<span class="prov">{r["e"]} &middot; {r["ts"]} {tags_html}<b class="jump">open transcript &rsaquo;</b></span></a></td>
<td><button class="copy" data-text="{data_text}">copy</button></td></tr>''')

    # ---- ratings
    grid = ratings_grid()
    order = ["Integration", "Cost / TCO", "Ease of use", "Scalability", "Customization",
             "Compliance workflow", "Ease of administration", "Asset management"]
    comparable_keys = FACTS["criterion_comparability"]["rated_by_all_three"]
    rrows = []
    for crit in order:
        cell = grid.get(crit, {})
        raters = sorted({x[0] for v in cell.values() for x in v})
        ck = CRIT_KEY.get(crit, "")
        compat_html = (f'<span class="compat">comparable &middot; rated by all 3</span>' if ck in comparable_keys
                       else f'<span class="compat">n={len(raters)} of 3 &middot; not comparable across panel</span>')
        tds = []
        for vk, vlab in VENDORS:
            pts = cell.get(vk)
            if not pts:
                tds.append(f'<td class="num empty" data-v="{vk}">&mdash;</td>')
                continue
            vals = [p[1] for p in pts]
            mean = sum(vals) / len(vals)
            marker = consensus_marker(pts)
            marker_html = f'<span class="consensus {marker[1]}">{esc(marker[0])}</span>' if marker else ''
            chips = []
            for e_, sc, ts_ in pts:
                why = WHY.get((e_, crit, vk))
                mark = '<sup class="tmark">T</sup>' if why else ''
                tip = f'<span class="tip"><b>{e_} on {vlab}</b>{esc(why)}<i>{ts_} &middot; click to open transcript</i></span>' if why else ''
                chips.append(
                    f'<span class="sc{" has" if why else ""}" data-e="{e_}">'
                    f'<a class="score" data-e="{e_}" onclick="goto(\'{e_}\',\'{ts_}\')">{sc:g}{mark}</a>'
                    f'<span class="who">{e_}</span>{tip}</span>')
            head = f'<b>{mean:g}</b>{marker_html}' if len(vals) > 1 else ''
            tds.append(f'<td class="num" data-v="{vk}">{head}<span class="pts">' + "".join(chips) + '</span></td>')
        strong = ' strong' if len(raters) == 3 else ''
        rrows.append(f'<tr class="critrow{strong}"><td>{crit}{compat_html}</td>' + "".join(tds) + '</tr>')

    # ---- coverage
    cov = FACTS["coverage"]
    gaps = "".join(f"<li>{gap_text(esc(g))}</li>" for g in cov["known_gaps"])
    miss = "".join(f"<li>{esc(m)}</li>" for m in cov["segments_missing"])

    tmpl = pathlib.Path(__file__).with_name("template.html").read_text()
    outp = (tmpl
            .replace("{{RAIL}}", "\n".join(rail))
            .replace("{{FROWS}}", "\n".join(frows))
            .replace("{{RROWS}}", "\n".join(rrows))
            .replace("{{TX_TABS}}", "\n".join(
                f'<button data-tx="{e}" class="{"on" if i == 0 else ""}">Expert {e[1]} &middot; {SEG[e]}</button>'
                for i, (e, _, _) in enumerate(tabs_tx)))
            .replace("{{TX_BODIES}}", "\n".join(
                f'<div class="txpane {"on" if i == 0 else ""}" data-tx="{e}">'
                f'<div class="txlayout"><div class="toc"><h3>Contents</h3><ol>{toc}</ol></div>'
                f'<div class="txbody">{body}</div></div></div>'
                for i, (e, toc, body) in enumerate(tabs_tx)))
            .replace("{{GAPS}}", gaps)
            .replace("{{MISSING}}", miss)
            .replace("{{NFIND}}", str(len(rows)))
            .replace("{{NUMERIC}}", render_numeric())
            .replace("{{SLIDECHECK}}", render_slidecheck()))
    return outp


# ---------------------------------------------------------------- build-time checks
def check_citations(doc):
    ids = set(re.findall(r'id="(t-E\d-\d{6})"', doc))
    links = set("t-%s-%s" % (e, ts.replace(":", "")) for e, ts in
                re.findall(r"goto\('(E\d)','([\d:]+)'\)", doc))
    broken = sorted(links - ids)
    if broken:
        raise SystemExit(f"BROKEN CITATION LINKS (no such turn): {broken}")
    if len(links) == 0:
        raise SystemExit("NO CITATION LINKS FOUND")
    print(f"citation links: {len(links)} checked, 0 broken")


def check_banned(doc):
    m = redaction_map()
    if len(m) < 8:
        raise SystemExit(f"REDACTION MAP TOO SMALL: {len(m)} entries (need >= 8)")

    e1 = next(e for e in FACTS["experts"] if e["id"] == "E1")
    note = e1.get("redaction_note", "")
    caps = re.findall(r"'([A-Z][A-Za-z]+)'", note)
    if len(caps) < 2:
        raise SystemExit("redaction_note captures missing — variant employer spellings would go unredacted")

    terms = sorted(m.keys(), key=lambda t: -len(t))
    parts = [re.escape(t) if " " in t else r"\b" + re.escape(t) + r"\b" for t in terms]
    pattern = re.compile("|".join(parts))

    if pattern.search(doc):
        raise SystemExit("BANNED TERM PRESENT in <rendered output>")

    root = pathlib.Path(__file__).parent
    n_files = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts[0] in (".git", "out"):
            continue
        if not (p.name == ".gitignore" or p.suffix in (".py", ".md", ".html", ".json")):
            continue
        n_files += 1
        text = p.read_text(encoding="utf8", errors="ignore")
        if pattern.search(text):
            raise SystemExit(f"BANNED TERM PRESENT in {rel}")

    print(f"banned-term scan: {len(m)} terms, 0 hits (output + {n_files} repo files)")
    return len(m), n_files


def check_counts(doc):
    n_frows = doc.count('class="frow')
    if n_frows != 20:
        raise SystemExit(f"FINDINGS ROW COUNT WRONG: got {n_frows}, expected 20")

    expected_scores = sum(len(r["scores"]) for r in FACTS["ratings"])
    if expected_scores < 52:
        raise SystemExit(f"expected_scores unexpectedly low: {expected_scores}")
    n_scores = len(re.findall(r'class="score"', doc))
    if n_scores != expected_scores:
        raise SystemExit(f"RATING SCORE COUNT WRONG: got {n_scores}, expected {expected_scores}")

    n_claims = doc.count('class="card claim"')
    if not (4 <= n_claims <= 5):
        raise SystemExit(f"SLIDE CLAIM COUNT WRONG: got {n_claims}")
    n_verdicts = len(re.findall(r'class="verdict ', doc))
    if n_verdicts != n_claims:
        raise SystemExit(f"VERDICT COUNT MISMATCH: {n_verdicts} verdicts vs {n_claims} claims")

    for label in ("volunteered", "confirmed on prompt, nothing added", "confirmed on prompt, expert added specifics"):
        if label not in doc:
            raise SystemExit(f"EVIDENTIARY TAG MISSING FROM OUTPUT: {label}")

    for p in FACTS["pricing"]:
        if esc(redact(p["quote"])) not in doc:
            raise SystemExit(f"VERBATIM PRICE QUOTE MISSING: {p['expert']}/{p['vendor']}")

    if 'id="slidecheck"' not in doc:
        raise SystemExit("SLIDECHECK SECTION MISSING")

    print(f"findings rows: {n_frows} (expected 20)")
    print(f"rating scores rendered: {n_scores} (expected {expected_scores} from facts.json)")
    print(f"slide-check claims: {n_claims}, verdicts: {n_verdicts}")


if __name__ == "__main__":
    doc = render()
    check_citations(doc)
    check_banned(doc)
    check_counts(doc)
    check_basis_labels()
    site_dir = pathlib.Path(__file__).parent / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    dest = site_dir / "index.html"
    dest.write_text(doc)
    print(f"wrote {dest} ({len(doc)} bytes)")
