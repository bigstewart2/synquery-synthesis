#!/usr/bin/env python3
"""Small, resumable Harbor provider pilot. Defaults to offline validation.

No generated finding is automatically human-confirmed. Controlled downstream
tests use the same reviewed gold evidence for every arm, isolating stage quality.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import shlex
import sys
import time

HERE = Path(__file__).resolve().parent
LIVE = HERE.parents[1]
sys.path.insert(0, str(LIVE / "api"))
from _brief import (EXTRACT_SYSTEM, REVIEW_SYSTEM, FINDINGS_TOOL, REVIEW_TOOL,
                    brief_id, context_note, extract_brief, review_findings, source_map)
from _harbor import BRIEF, SAMPLES
from _pipeline import CHECK_SYSTEM, CHECK_TOOL, THEME_SYSTEM, THEME_TOOL, check_claim, draft_themes, norm
from _providers import create_provider, digest

ARMS = [("anthropic", "claude-sonnet-5"), ("openai", "gpt-5.6-terra"), ("openai", "gpt-5.6-sol")]
# Official list rates checked 2026-09-09; USD / 1M tokens. Invoiced cost is not
# returned by generation APIs. All reported dollars are usage-based estimates.
PRICES = {
    "claude-sonnet-5": {"input": 2, "cached": .2, "cache_write": 2.5, "output": 10},
    "gpt-5.6-terra": {"input": 2, "cached": .2, "cache_write": 2.5, "output": 12},
    "gpt-5.6-sol": {"input": 4, "cached": .4, "cache_write": 5, "output": 20},
}
PRICE_SOURCES = ["https://platform.claude.com/docs/en/about-claude/pricing",
                 "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
                 "https://developers.openai.com/api/docs/models/gpt-5.6-sol"]


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def read_gold():
    gold = json.loads((HERE / "gold.json").read_text())
    if gold["brief_sha256"] != hashlib.sha256(json.dumps(BRIEF, sort_keys=True).encode()).hexdigest():
        raise ValueError("Canonical brief changed; review a new answer key.")
    for sid, sample in SAMPLES.items():
        if hashlib.sha256(sample["text"].encode()).hexdigest() != gold["source_sha256"][sid]:
            raise ValueError("Canonical source changed; review a new answer key.")
    ids = set()
    for finding in gold["findings"]:
        if finding["id"] in ids:
            raise ValueError("Duplicate gold finding ID.")
        ids.add(finding["id"])
        text = SAMPLES[finding["sample_id"]]["text"]
        haystack, locations = source_map(text)
        start = haystack.find(norm(finding["quote"]))
        if start < 0 or locations[start] != finding["source_start_line"]:
            raise ValueError("Gold quote or source location no longer matches.")
        end = start + len(norm(finding["quote"])) - 1
        if locations[end] != finding["source_end_line"]:
            raise ValueError("Gold quote end location no longer matches.")
    for claim in gold["claims"]:
        if not set(claim["evidence"]) <= ids:
            raise ValueError("Claim refers to an unknown gold finding.")
    return gold


def load_credentials():
    """Read only provider keys. Do not execute a secrets file or print its values."""
    for path in (Path.home() / ".config/secrets.env", LIVE / ".env.local"):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            name = name.strip()
            if not sep or name not in ("OPENAI_API_KEY", "INTERVIEW_OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
                continue
            try:
                values = shlex.split(value, comments=True)
            except ValueError:
                raise ValueError(f"Could not parse {name} in {path.name}.") from None
            if len(values) == 1 and values[0].startswith("sk-"):
                if path == LIVE / ".env.local":
                    os.environ[name] = values[0]
                else:
                    os.environ.setdefault(name, values[0])


def cost(model, usage):
    if usage is None:
        return None
    price = PRICES[model]
    cached = usage.get("cached_input_tokens", 0)
    created = usage.get("cache_creation_input_tokens", 0)
    uncached = usage["input_tokens"] - cached - created
    if uncached < 0:
        raise ValueError("Inconsistent provider usage.")
    return (uncached * price["input"] + cached * price["cached"] +
            created * price["cache_write"] + usage["output_tokens"] * price["output"]) / 1_000_000


def reserve_cost(model, request, output_limit):
    # UTF-8 bytes give a deliberately generous text-token bound; add headroom
    # for provider wrappers/tool schema overhead. No retries or hosted tools.
    input_bound = len(json.dumps(request, ensure_ascii=False).encode()) + 8192
    return (input_bound * PRICES[model]["input"] + output_limit * PRICES[model]["output"]) / 1_000_000


def manifest(gold):
    files = [LIVE / "api" / name for name in ("_providers.py", "_pipeline.py", "_brief.py", "_harbor.py")]
    files.append(Path(__file__).resolve())
    return {"gold_sha256": digest(gold), "source_sha256": gold["source_sha256"],
            "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            "prompt_sha256": {"extract": digest(EXTRACT_SYSTEM), "review": digest(REVIEW_SYSTEM),
                              "synthesis": digest(THEME_SYSTEM), "claim": digest(CHECK_SYSTEM)},
            "schema_sha256": {t["name"]: digest(t["input_schema"]) for t in
                              (FINDINGS_TOOL, REVIEW_TOOL, THEME_TOOL, CHECK_TOOL)},
            "arms": ARMS, "prices": PRICES, "price_sources": PRICE_SOURCES,
            "price_checked_at": "2026-09-09", "sdk_retries": 0,
            "openai_reasoning": {"extract_review_synthesis": "none", "claim": "medium"},
            "downstream_evidence": "same human-reviewed gold for all providers"}


def approved_atoms(gold):
    fields = ("finding", "quote", "kind", "question_index", "source_start_line", "source_end_line")
    return {f["id"]: {**{k: f[k] for k in fields}, "confidence": "high",
                       "verified": True, "review_status": "supported", "brief_id": brief_id(BRIEF)}
            for f in gold["findings"]}


def gold_content_hash(gold):
    return digest({k: v for k, v in gold.items() if k != "review"})


def require_approved_gold(gold):
    if (gold["review"]["status"] != "approved" or not gold["review"].get("reviewer") or
            gold["review"].get("content_sha256") != gold_content_hash(gold)):
        raise ValueError("Gold answer key needs human review before paid benchmark calls.")


def probes(gold, sid):
    ids = (["E1-G04", "E1-G10"] if sid == "harbor-david" else ["E2-G03", "E2-G06"])
    by_id = {f["id"]: f for f in gold["findings"]}
    values = [{k: v for k, v in by_id[i].items() if k not in ("id", "expert", "sample_id")}
              for i in ids]
    negatives = deepcopy(values)
    if sid == "harbor-david":
        negatives[0]["finding"] = "David says middleware cannot work and is a structural failure."
        negatives[1]["finding"] = "Harbor loses all mid-market deals to big integrated treasury providers."
    else:
        negatives[0]["finding"] = "Harbor implementations take four to nine months."
        negatives[1]["finding"] = "Maria says the CFO alone decides whether implementation starts."
    # Interleave positive/negative cases so a positional yes/no heuristic is not rewarded.
    ordered = [values[0], negatives[0], negatives[1], values[1]]
    return [{"index": i, "confidence": "high", **v} for i, v in enumerate(ordered)], [True, False, False, True]


class BudgetStop(RuntimeError):
    pass


class Ledger:
    def __init__(self, root, limit):
        self.path = root / "calls.jsonl"
        self.limit = limit
        self.spent = 0.0
        self.pending = set()
        self.unknown = False
        self.task = None
        self.counter = 0
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                event = json.loads(line)
                self.counter = max(self.counter, event["call_id"])
                if event["event"] == "started":
                    self.pending.add(event["call_id"])
                else:
                    self.pending.discard(event["call_id"])
                    amount = event["record"].get("estimated_cost_usd")
                    if amount is None:
                        self.unknown = True
                    else:
                        self.spent += amount
        if self.pending or self.unknown:
            raise BudgetStop("A previous call has uncertain billing. Inspect the run before issuing another paid call.")

    def append(self, event):
        with self.path.open("a") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def before(self, record, request):
        reservation = reserve_cost(record["model"], request, record["max_output_tokens"])
        if self.unknown or self.spent + reservation > self.limit:
            raise BudgetStop("Stopped before the next call to stay within the pilot budget.")
        self.counter += 1
        record["call_id"] = self.counter
        record["task"] = self.task
        self.append({"event": "started", "call_id": self.counter, "record": deepcopy(record),
                     "reserved_cost_usd": reservation})

    def after(self, record):
        amount = cost(record["model"], record["usage"])
        record["estimated_cost_usd"] = amount
        self.append({"event": "finished", "call_id": record["call_id"], "record": record})
        if amount is None:
            self.unknown = True
        else:
            self.spent += amount


def estimate(gold):
    # Planning estimate, not a promise: 65k input and 16k output tokens per arm
    # across 13 calls. The actual ledger uses provider-reported usage.
    return {"calls_per_arm": 13, "calls_total": 39, "assumption_input_per_arm": 65_000,
            "assumption_output_per_arm": 16_000,
            "estimated_cost_usd": {model: round((65_000*p["input"]+16_000*p["output"])/1e6, 3)
                                   for model, p in PRICES.items()},
            "run_budget_usd": 3.0,
            "note": "Two extractions with reviews, two review-probe batches, one controlled synthesis, six controlled claims per arm."}


def preflight():
    load_credentials()
    results = []
    for provider, model in ARMS:
        try:
            p = create_provider(provider, model, max_retries=0, timeout=30)
            response = p.client.models.retrieve(model)
            results.append({"provider": provider, "requested_model": model, "available": True,
                            "returned_model": response.id})
        except Exception as exc:
            results.append({"provider": provider, "requested_model": model, "available": False,
                            "error_type": type(exc).__name__, "http_status": getattr(exc, "status_code", None)})
    print(json.dumps(results, indent=2))
    return all(r["available"] for r in results)


def run(gold, root, max_cost, resume, retry_failed=False):
    require_approved_gold(gold)
    if os.environ.get("INTERVIEW_OPENAI_REASONING_EFFORT"):
        raise ValueError("Unset INTERVIEW_OPENAI_REASONING_EFFORT for the fixed comparison protocol.")
    config = manifest(gold)
    if resume:
        saved = json.loads((root / "manifest.json").read_text())
        if saved["protocol"] != json.loads(json.dumps(config)):
            raise ValueError("The inputs, code, prompts or protocol changed; cannot resume this run.")
    else:
        root.mkdir(parents=True, exist_ok=False)
        order = list(ARMS)
        random.SystemRandom().shuffle(order)
        saved = {"created_at": utc(), "protocol": config,
                 "order": order, "arm_mapping": {chr(65+i): list(pair) for i, pair in enumerate(order)},
                 "python": sys.version, "sdk_versions": {name: importlib.metadata.version(name)
                    for name in ("openai", "anthropic", "jsonschema")}}
        write_json(root / "manifest.json", saved)
        write_json(root / "gold.json", gold)
        write_json(root / "sources.json", {"brief": BRIEF, "samples": SAMPLES})
    ledger = Ledger(root, max_cost)
    load_credentials()
    atoms = approved_atoms(gold)
    note = "Panel: 2 experts. Expert labels: E1, E2. " + context_note(BRIEF)
    for arm, (provider, model) in saved["arm_mapping"].items():
        client = create_provider(provider, model, capture=True, max_retries=0, timeout=180,
                                 before_call=ledger.before, after_call=ledger.after)
        tasks = [("extract-"+sid, "extract", sid) for sid in SAMPLES]
        tasks += [("review-probes-"+sid, "review", sid) for sid in SAMPLES]
        tasks += [("synthesis", "synthesis", None)]
        tasks += [("claim-"+c["id"], "claim", c) for c in gold["claims"]]
        for name, stage, arg in tasks:
            path = root / f"{arm}-{name}.json"
            if path.exists():
                old = json.loads(path.read_text())
                if old["status"] == "completed":
                    continue
                if not retry_failed:
                    raise ValueError("A saved task is unfinished or failed. Inspect it before using --resume --retry-failed; retrying may incur cost.")
                history = root / "history"
                history.mkdir(exist_ok=True)
                write_json(history / f"{path.stem}-{time.time_ns()}.json", old)
            ledger.task = f"{arm}-{name}"
            out = {"arm": arm, "task": name, "stage": stage, "status": "pending", "started_at": utc()}
            write_json(path, out)
            started = time.perf_counter()
            try:
                if stage == "extract":
                    sample = SAMPLES[arg]
                    findings, usage, failures = extract_brief(client, sample["label"], sample["text"], BRIEF)
                    out.update(sample_id=arg, findings=findings["findings"], usage=usage, failures=failures)
                elif stage == "review":
                    cases, expected = probes(gold, arg)
                    result = review_findings(client, SAMPLES[arg]["text"], BRIEF, cases)
                    out.update(sample_id=arg, cases=cases, expected=expected, checks=result.payload["checks"])
                elif stage == "synthesis":
                    summary, themes, gaps, dropped = draft_themes(client, atoms, note, brief_mode=True)
                    out.update(summary=summary, themes=themes, not_supported=gaps, dropped_citations=dropped)
                else:
                    out.update(claim_id=arg["id"], expected=arg["expected"], result=check_claim(client, arg["claim"], atoms, note))
                out["status"] = "completed"
            except Exception as exc:
                out.update(status="failed", error_type=type(exc).__name__,
                           http_status=getattr(exc, "status_code", None))
                if isinstance(exc, BudgetStop) or ledger.unknown:
                    out["halt_reason"] = "budget_or_uncertain_billing"
            finally:
                out["elapsed_s"] = round(time.perf_counter()-started, 6)
                write_json(path, out)
            print(f"Arm {arm}: {name} {out['status']}; estimated spend ${ledger.spent:.3f}", flush=True)
            if out.get("halt_reason") or ledger.unknown:
                raise BudgetStop("Pilot stopped; saved outputs and usage are available.")
    return ledger.spent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "estimate", "preflight", "approve-gold", "run"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-cost-usd", type=float, default=3.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--reviewer", help="Name of the human who actually reviewed and approved the answer key")
    args = parser.parse_args()
    gold = read_gold()
    if args.action == "validate":
        print(f"Validated {len(gold['findings'])} gold source spans and {len(gold['claims'])} claims; human review: {gold['review']['status']}.")
    elif args.action == "estimate":
        print(json.dumps(estimate(gold), indent=2))
    elif args.action == "preflight":
        return 0 if preflight() else 1
    elif args.action == "approve-gold":
        if not args.reviewer or not args.reviewer.strip():
            parser.error("approve-gold requires the actual human reviewer's name")
        gold["review"] = {"status": "approved", "reviewer": args.reviewer.strip(),
                          "reviewed_at": utc(), "content_sha256": gold_content_hash(gold)}
        write_json(HERE / "gold.json", gold)
        print("Recorded human approval of the exact current answer key.")
    else:
        if args.max_cost_usd <= 0 or not args.output:
            parser.error("run requires --output and a positive budget")
        spend = run(gold, args.output.resolve(), args.max_cost_usd, args.resume, args.retry_failed)
        print(f"Complete. Estimated cost from reported usage: ${spend:.4f}. Run report.py for blinded review.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, BudgetStop) as exc:
        sys.exit(str(exc))
