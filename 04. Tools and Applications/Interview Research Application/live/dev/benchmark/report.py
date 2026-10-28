#!/usr/bin/env python3
"""Generate blinded review artifacts and separate deterministic/human metrics."""
import argparse
import json
from pathlib import Path
import random

from run import digest, write_json


def build(root):
    gold = json.loads((root / "gold.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    if digest(gold) != manifest["protocol"]["gold_sha256"]:
        raise ValueError("Saved answer key no longer matches this run.")
    gold_ids = {f["id"] for f in gold["findings"]}
    outputs = [json.loads(p.read_text()) for p in sorted(root.glob("[ABC]-*.json"))]
    events = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
    records = [e["record"] for e in events if e["event"] == "finished"]
    finished_ids = {e["call_id"] for e in events if e["event"] == "finished"}
    pending = [e for e in events if e["event"] == "started" and e["call_id"] not in finished_ids]
    review_path = root / "human-review.json"
    review = json.loads(review_path.read_text()) if review_path.exists() else {
        "reviewer": None, "status": "pending", "findings": {}, "synthesis": {}, "evidence_gaps": {}}
    blinded = ["# Blinded Harbor review", "", "Models are labeled A, B and C in a randomized order. Review this file before opening manifest.json or raw call logs, which reveal providers. The answer key was fixed before these outputs. Ratings in human-review.json remain null until a person supplies them.", "",
               "For each candidate, judge whether every part is supported, including scope, attribution, type and numeric meaning. List any gold evidence units it covers. Do not reward polish. The provider's separate review decision appears only after the candidate text, and does not establish truth.", ""]
    metrics = {}
    for arm in manifest["arm_mapping"]:
        rows = [o for o in outputs if o["arm"] == arm]
        candidates = []
        for row in rows:
            if row["stage"] == "extract":
                for i, finding in enumerate(row.get("findings", [])):
                    cid = f"{arm}-{row['sample_id']}-{i:02d}"
                    candidates.append((cid, row["sample_id"], finding))
                    review["findings"].setdefault(cid, {"supported": None, "gold_ids": [], "notes": ""})
        # Stable randomization for review readability across repeated report builds.
        random.Random(arm + manifest["created_at"]).shuffle(candidates)
        blinded += [f"## Arm {arm}", ""]
        for cid, sid, finding in candidates:
            blinded += [f"### {cid}", "", f"**Finding ({finding['kind']})**: {finding['finding']}", "",
                        f"**Source quote**: {finding['quote']}", "",
                        f"Source: {sid}; lines {finding.get('source_start_line', 'unlocated')}–{finding.get('source_end_line', 'unlocated')}. Exact quote located: {finding['verified']}.", "",
                        f"Provider review: {finding['review_status']}. {finding['review_note']}", ""]
        for row in rows:
            if row["stage"] == "synthesis" and row["status"] == "completed":
                blinded += [f"### {arm} controlled synthesis", "", row["summary"]["text"], "",
                            "Summary citations: " + ", ".join(row["summary"]["atom_ids"]), ""]
                review["synthesis"].setdefault(arm + "-summary", {"supported": None, "notes": ""})
                for i, theme in enumerate(row["themes"]):
                    tid = f"{arm}-theme-{i:02d}"
                    review["synthesis"].setdefault(tid, {"supported": None, "notes": ""})
                    blinded += [f"- **{tid}: {theme['theme']}** — {theme['takeaway']} ({theme['strength']}; citations: {', '.join(theme['atom_ids'])})"]
                blinded += ["", "Evidence gaps:", ""] + [f"- {gap}" for gap in row["not_supported"]] + [""]
                review["evidence_gaps"].setdefault(arm, {"adequate": None, "notes": ""})
            if row["stage"] == "claim" and row["status"] == "completed":
                r = row["result"]
                blinded += [f"### {arm} {row['claim_id']}", "", r["claim"], "",
                            f"Verdict: **{r['verdict']}**. {r['reasoning']}", "",
                            f"Footnote: {r['footnote']}", ""] + [f"- {c}" for c in r["caveats"]] + [""]
        assigned = [r for r in records if r.get("task", "").startswith(arm + "-")]
        judgments = [review["findings"][cid] for cid, _, _ in candidates]
        for cid, sid, _ in candidates:
            judged = review["findings"][cid]
            allowed = {f["id"] for f in gold["findings"] if f["sample_id"] == sid}
            if not isinstance(judged.get("gold_ids"), list) or not set(judged["gold_ids"]) <= allowed:
                raise ValueError(f"Invalid gold mapping for {cid}.")
            if judged["gold_ids"] and judged.get("supported") is not True:
                raise ValueError(f"Unsupported or unreviewed finding {cid} cannot earn recall credit.")
        human_complete = (review.get("status") == "complete" and bool(review.get("reviewer")) and
                          all(type(j.get("supported")) is bool for j in judgments))
        covered, eligible_covered = set(), set()
        for cid, _, finding in candidates:
            judged = review["findings"][cid]
            if judged.get("supported") is True:
                covered.update(judged["gold_ids"])
                if finding["verified"] and finding["review_status"] == "supported":
                    eligible_covered.update(judged["gold_ids"])
        review_correct = review_total = 0
        for row in rows:
            if row["stage"] == "review":
                expected = row.get("expected", [True, False, False, True])
                for i, value in enumerate(expected):
                    matches = [c for c in row.get("checks", []) if c.get("index") == i]
                    review_correct += len(matches) == 1 and matches[0].get("supported") is value
                review_total += len(expected)
        claims = [r for r in rows if r["stage"] == "claim"]
        claim_correct = sum(r.get("result", {}).get("verdict") == r.get("expected")
                            for r in claims if r["status"] == "completed")
        synth = next((r for r in rows if r["stage"] == "synthesis" and r["status"] == "completed"), None)
        known_cost = sum(r["estimated_cost_usd"] for r in assigned if r.get("estimated_cost_usd") is not None)
        unknown_billing = sum(r.get("estimated_cost_usd") is None for r in assigned)
        unknown_billing += sum(e["record"].get("task", "").startswith(arm+"-") for e in pending)
        supported = sum(j.get("supported") is True for j in judgments)
        n = len(candidates)
        actual_reviews = [(review["findings"][cid], f) for cid, _, f in candidates
                          if f["verified"] and f["review_status"] in ("supported", "flagged")]
        def task_usage(name):
            calls = [r for r in assigned if r["task"] == arm + "-" + name]
            return {"known_estimated_cost_usd": sum(r["estimated_cost_usd"] for r in calls if r.get("estimated_cost_usd") is not None),
                    "calls_with_uncertain_billing": sum(r.get("estimated_cost_usd") is None for r in calls),
                    "input_tokens": sum((r.get("usage") or {}).get("input_tokens", 0) for r in calls),
                    "output_tokens": sum((r.get("usage") or {}).get("output_tokens", 0) for r in calls)}
        metrics[arm] = {
            "candidate_count": n,
            "exact_quotes_located": sum(f["verified"] for _, _, f in candidates),
            "eligible_for_human_confirmation": sum(f["verified"] and f["review_status"] == "supported" for _, _, f in candidates),
            "finding_precision": supported/n if human_complete and n else None,
            "finding_recall": len(covered)/len(gold_ids) if human_complete else None,
            "eligible_finding_recall": len(eligible_covered)/len(gold_ids) if human_complete else None,
            "unsupported_finding_rate": (n-supported)/n if human_complete and n else None,
            "actual_review_accuracy": sum(j["supported"] == (f["review_status"] == "supported") for j,f in actual_reviews)/len(actual_reviews)
                                      if human_complete and actual_reviews else None,
            "controlled_review_correct": review_correct, "controlled_review_expected": 8,
            "controlled_review_cases_attempted": review_total,
            "claim_verdicts_correct": claim_correct, "claim_verdicts_expected": len(gold["claims"]),
            "claim_checks_with_valid_citations": sum(r.get("result", {}).get("citations_resolve") is True for r in claims),
            "synthesis_citations_resolve": (synth["summary"]["citations_resolve"] and all(t["citations_resolve"] for t in synth["themes"])) if synth else None,
            "synthesis_semantic_review": {k:v for k,v in review["synthesis"].items() if k.startswith(arm+"-")},
            "evidence_gap_review": review["evidence_gaps"].get(arm),
            "task_failures": sum(r["status"] != "completed" for r in rows),
            "extraction_review_failures": sum(len(r.get("failures", [])) for r in rows),
            "structured_call_failures": sum(r["status"] != "completed" for r in assigned),
            "calls_finished": len(assigned), "calls_expected": 13,
            "known_estimated_cost_usd": known_cost, "calls_with_uncertain_billing": unknown_billing,
            "model_call_elapsed_s": sum(r["elapsed_s"] for r in assigned),
            "finding_review_complete": human_complete,
            "extraction_by_interview": {r["sample_id"]: {"elapsed_s": r["elapsed_s"],
                "candidate_count": len(r.get("findings", [])), **task_usage(r["task"])}
                for r in rows if r["stage"] == "extract"},
            "usage_by_task": {r["task"]: {"stage": r["stage"], **task_usage(r["task"])} for r in rows},
            "usage": {key: sum((r.get("usage") or {}).get(key, 0) or 0 for r in assigned)
                      for key in ("input_tokens", "cached_input_tokens", "cache_creation_input_tokens", "output_tokens")},
        }
    write_json(review_path, review)
    (root / "BLINDED-REVIEW.md").write_text("\n".join(blinded))
    write_json(root / "metrics.json", metrics)
    table = ["# Harbor pilot comparison", "", "Arm labels conceal provider identity. Exact quote matching and citation-ID validity do not establish semantic accuracy. Human judgments remain pending unless completed in human-review.json.", "",
             "| Arm | Quotes | Review | Claims | Cost est. | Time s |",
             "|-----|--------|--------|--------|-----------|--------|"]
    # Format aligned short cells; keep every row under 70 characters.
    cells = [["Arm", "Quotes", "Review", "Claims", "Cost est.", "Time s"]]
    for arm,m in metrics.items():
        cells.append([arm, f"{m['exact_quotes_located']}/{m['candidate_count']}",
                      f"{m['controlled_review_correct']}/8", f"{m['claim_verdicts_correct']}/6",
                      f"${m['known_estimated_cost_usd']:.3f}" + ("+?" if m['calls_with_uncertain_billing'] else ""),
                      f"{m['model_call_elapsed_s']:.1f}"])
    widths = [max(len(row[i]) for row in cells) for i in range(len(cells[0]))]
    render = lambda row: "| " + " | ".join(v.ljust(w) for v,w in zip(row,widths)) + " |"
    table = table[:4] + [render(cells[0]), "|" + "|".join("-"*(w+2) for w in widths) + "|"] + [render(r) for r in cells[1:]]
    table += ["", "Quotes = located / proposed findings. Review = correct decisions on eight deliberately supported/unsupported review probes. Claims = correct verdicts on six claims using identical gold evidence. Time is the sum of model-call durations for this sequential pilot. Cost is estimated from reported usage at the saved list prices, including reasoning once. A +? marks unresolved billing.", "",
              "Finding precision, recall, unsupported-finding rate, real-review accuracy, synthesis meaning and evidence-gap quality require completed blinded human review. See metrics.json for individual fields and failures. The controlled synthesis and claims use gold evidence, so these results do not measure an end-to-end human-confirmed generated workflow.", "",
              "Decision remains pending. One run on two fictional interviews cannot establish general superiority. Production remains on Claude until a separately approved deployment.", ""]
    (root / "COMPARISON.md").write_text("\n".join(table))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    result = build(args.run_directory.resolve())
    print(f"Wrote blinded review and metrics for {len(result)} arms. Human-only metrics are not guessed.")
