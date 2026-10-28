"""Offline benchmark orchestration, billing, blinding and review-gate tests."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "benchmark"))
import run as bench
import report
from _providers import StructuredProvider
from _brief import FINDINGS_TOOL


def approved_gold():
    value = bench.read_gold()
    value["review"] = {"status": "approved", "reviewer": "offline test fixture",
                       "content_sha256": bench.gold_content_hash(value)}
    return value


class FakeSDK:
    def __init__(self, provider, model, gold, counter):
        self.provider, self.model, self.gold, self.counter = provider, model, gold, counter
        self.messages = self.responses = self

    def create(self, **request):
        self.counter.append(request)
        anthropic = self.provider == "anthropic"
        name = request["tools"][0]["name"] if anthropic else request["text"]["format"]["name"]
        text = request["messages"][0]["content"] if anthropic else request["input"]
        if name == "emit_findings":
            expert = json.loads(text)["expert_label"]
            f = next(f for f in self.gold["findings"] if f["expert"] == expert)
            value = {"items": [{k: f[k] for k in ("finding", "quote", "kind", "question_index")} | {"confidence": "high"}]}
        elif name == "review_findings":
            findings = json.loads(text)["findings"]
            flags = [True, False, False, True] if len(findings) == 4 else [True]
            value = {"checks": [{"index": f["index"], "supported": flag, "reason": "offline fixture"}
                                for f, flag in zip(findings, flags)]}
        elif name == "emit_themes":
            value = {"summary": {"text": "A summary from two fictional experts.", "atom_ids": ["E1-G01"]},
                     "themes": [{"theme": "Reconciliation", "takeaway": "An attributed opinion.",
                                 "strength": "one expert", "atom_ids": ["E1-G01"]}],
                     "not_supported": ["Harbor's measured customer outcomes."]}
        else:
            claim = text.split('Claim to grade:\n"', 1)[1][:-1]
            c = next(c for c in self.gold["claims"] if c["claim"] == claim)
            value = dict(verdict=c["expected"], reasoning="offline fixture", atom_ids=c["evidence"],
                         footnote="Source lines in gold evidence.", caveats=["Fictional interviews."])
        usage = NS(input_tokens=100, output_tokens=50)
        if anthropic:
            return NS(id="msg_offline", model=self.model, stop_reason="tool_use", usage=usage,
                      content=[NS(type="tool_use", name=name, input=value)])
        usage.input_tokens_details = NS(cached_tokens=0)
        usage.output_tokens_details = NS(reasoning_tokens=10)
        return NS(id="resp_offline", model=self.model, status="completed", usage=usage,
                  output=[NS(type="message", content=[NS(type="output_text", text=json.dumps(value))])])


class BenchmarkTests(unittest.TestCase):
    def test_no_paid_work_before_review_and_no_stale_approval(self):
        gold = deepcopy(approved_gold())
        gold["review"]["status"] = "pending"
        with TemporaryDirectory() as tmp, patch.object(bench, "create_provider") as factory:
            path = Path(tmp) / "run"
            with self.assertRaises(ValueError): bench.run(gold, path, 3, False)
            self.assertFalse(path.exists())
            factory.assert_not_called()
        gold = approved_gold()
        gold["findings"][0]["finding"] += " Changed after review."
        with self.assertRaises(ValueError): bench.require_approved_gold(gold)

    def test_budget_blocks_before_client_call_and_unknown_billing_blocks_resume(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = bench.Ledger(root, .000001)
            with patch.object(FakeSDK, "create") as call:
                p = StructuredProvider("openai", "gpt-5.6-terra", FakeSDK("openai", "gpt-5.6-terra", approved_gold(), []),
                                       before_call=ledger.before, after_call=ledger.after)
                with self.assertRaises(bench.BudgetStop):
                    p.generate_structured(instructions="test", input="test", tool=FINDINGS_TOOL, max_output_tokens=500)
                call.assert_not_called()
            ledger = bench.Ledger(root, 3)
            with patch.object(FakeSDK, "create", side_effect=RuntimeError("transport interrupted")):
                p = StructuredProvider("openai", "gpt-5.6-terra", FakeSDK("openai", "gpt-5.6-terra", approved_gold(), []),
                                       before_call=ledger.before, after_call=ledger.after)
                with self.assertRaises(RuntimeError):
                    p.generate_structured(instructions="test", input="test", tool=FINDINGS_TOOL, max_output_tokens=500)
            self.assertTrue(ledger.unknown)
            with self.assertRaises(bench.BudgetStop): bench.Ledger(root, 3)

    def test_cost_counts_cached_and_reasoning_tokens_once(self):
        usage = dict(input_tokens=100, cached_input_tokens=20, cache_creation_input_tokens=0,
                     output_tokens=40, reasoning_tokens=10)
        self.assertAlmostEqual(bench.cost("gpt-5.6-terra", usage), (80*2+20*.2+40*12)/1e6)
        self.assertIsNone(bench.cost("gpt-5.6-terra", None))

    def test_complete_fake_run_resumes_without_recharging_and_reports_blindly(self):
        gold = approved_gold()
        counter = []
        def factory(provider, model, **kwargs):
            return StructuredProvider(provider, model, FakeSDK(provider, model, gold, counter), capture=kwargs["capture"],
                before_call=kwargs["before_call"], after_call=kwargs["after_call"])
        with TemporaryDirectory() as tmp, patch.object(bench, "load_credentials"), \
                patch.object(bench, "create_provider", side_effect=factory), redirect_stdout(io.StringIO()):
            root = Path(tmp) / "run"
            first_cost = bench.run(gold, root, 3, False)
            self.assertEqual(len(counter), 39)
            second_cost = bench.run(gold, root, 3, True)
            self.assertEqual(len(counter), 39)
            self.assertAlmostEqual(first_cost, second_cost)
            metrics = report.build(root)
            for value in metrics.values():
                self.assertEqual(value["claim_verdicts_correct"], 6)
                self.assertEqual(value["controlled_review_correct"], 8)
                self.assertEqual(value["calls_finished"], 13)
                self.assertIsNone(value["finding_precision"])
                self.assertIsNone(value["finding_recall"])
                self.assertTrue(value["synthesis_citations_resolve"])
            text = (root / "BLINDED-REVIEW.md").read_text()
            for _, model in bench.ARMS: self.assertNotIn(model, text)
            rows = [line for line in (root / "COMPARISON.md").read_text().splitlines() if line.startswith("|")]
            self.assertTrue(all(len(line) < 70 for line in rows))
            self.assertEqual(len(set(map(len, rows))), 1)
            # Invalid reviewer mappings cannot manufacture recall.
            review = json.loads((root / "human-review.json").read_text())
            next(iter(review["findings"].values()))["gold_ids"] = ["nonexistent-gold"]
            bench.write_json(root / "human-review.json", review)
            with self.assertRaises(ValueError): report.build(root)


if __name__ == "__main__":
    unittest.main()
