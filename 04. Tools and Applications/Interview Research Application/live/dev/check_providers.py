"""Offline checks for provider compatibility and evidence safety. No API calls."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from _providers import (StructuredProvider, StructuredResponseError, ProviderConfigurationError,
                        create_provider, credential_name, normalized_usage, strict_schema)
from _brief import extract_brief, FINDINGS_TOOL, REVIEW_TOOL, EXTRACT_SYSTEM
from _pipeline import GROUPS, CHECK_TOOL, THEME_TOOL, check_claim, draft_themes
from check_brief import Client, message, finding, BRIEF, TRANSCRIPT, QUOTE
import extract as api


def response(value, *, status="completed", refusal=False, usage=True):
    part = NS(type="refusal", refusal="declined") if refusal else NS(type="output_text", text=json.dumps(value))
    return NS(status=status, id="resp_fixture", model="gpt-5.6-terra",
              output=[NS(type="message", content=[part])],
              usage=NS(input_tokens=100, output_tokens=40,
                       input_tokens_details=NS(cached_tokens=20),
                       output_tokens_details=NS(reasoning_tokens=10)) if usage else None)


class Responses:
    def __init__(self, *values):
        self.values = iter(values)
        self.calls = []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = next(self.values)
        if isinstance(item, Exception):
            raise item
        return item


def provider(*values):
    return StructuredProvider("openai", "gpt-5.6-terra", Responses(*values), capture=True)


def generate(p, tool=FINDINGS_TOOL):
    return p.generate_structured(instructions="test", input="fictional input", tool=tool, max_output_tokens=500)


class ProviderTests(unittest.TestCase):
    def test_interview_key_precedence_and_generic_fallback(self):
        for scoped in ("sk-interview-fixture", ""):
            with self.subTest(scoped=bool(scoped)), patch.dict(os.environ, {
                "OPENAI_API_KEY": "sk-general-fixture",
                "INTERVIEW_OPENAI_API_KEY": scoped,
            }, clear=True), patch("openai.OpenAI") as sdk:
                create_provider("openai")
                self.assertEqual(sdk.call_args.kwargs["api_key"], scoped or "sk-general-fixture")
                self.assertEqual(credential_name("openai"),
                                 "INTERVIEW_OPENAI_API_KEY" if scoped else "OPENAI_API_KEY")
                self.assertEqual(credential_name("anthropic"), "ANTHROPIC_API_KEY")

    def test_anthropic_request_preserves_control(self):
        raw = Client(message("emit_findings", {"items": [finding()]}),
                     message("review_findings", {"checks": [{"index": 0, "supported": True, "reason": "faithful"}]}))
        wrapped = StructuredProvider("anthropic", "claude-sonnet-5", raw, capture=True)
        atoms, usage, failures = extract_brief(wrapped, "E1", TRANSCRIPT, BRIEF)
        self.assertEqual(raw.calls[0], dict(model="claude-sonnet-5", max_tokens=6500,
            system=EXTRACT_SYSTEM, tools=[FINDINGS_TOOL], tool_choice={"type": "tool", "name": "emit_findings"},
            messages=[{"role": "user", "content": json.dumps({"research_brief": BRIEF,
                        "expert_label": "E1", "transcript": TRANSCRIPT}, ensure_ascii=False)}]))
        self.assertEqual(usage, {"input_tokens": 200, "output_tokens": 100})
        self.assertEqual(failures, [])
        self.assertEqual(atoms["findings"][0]["review_status"], "supported")
        self.assertEqual(len(wrapped.records), 2)

    def test_openai_storage_schema_and_same_source_gates(self):
        items = [finding(), {**finding(), "finding": "An invented claim.", "quote": "This does not exist anywhere in the source."}]
        p = provider(response({"items": items}), response({"checks": [{"index": 0, "supported": True, "reason": "faithful"}]}))
        atoms, usage, failures = extract_brief(p, "E1", TRANSCRIPT, BRIEF)
        self.assertTrue(atoms["findings"][0]["verified"])
        self.assertEqual(atoms["findings"][0]["source_start_line"], 3)
        self.assertFalse(atoms["findings"][1]["verified"])
        self.assertEqual(atoms["findings"][1]["review_status"], "flagged")
        self.assertEqual(len(json.loads(p.client.calls[1]["input"])["findings"]), 1)
        request = p.client.calls[0]
        self.assertIs(request["store"], False)
        self.assertEqual(request["reasoning"], {"effort": "none"})
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(request["instructions"], EXTRACT_SYSTEM)
        self.assertEqual(usage["output_tokens"], 80)
        self.assertEqual(failures, [])

    def test_real_openai_sdk_serializes_and_parses_without_network(self):
        import httpx2
        from openai import OpenAI
        captured = []
        def transport(request):
            captured.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/responses")
            return httpx2.Response(200, json={
                "id": "resp_offline", "object": "response", "created_at": 0,
                "model": "gpt-5.6-terra", "status": "completed",
                "output": [{"id": "msg_offline", "type": "message", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": '{"items":[]}', "annotations": []}]}],
                "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140,
                          "input_tokens_details": {"cached_tokens": 20},
                          "output_tokens_details": {"reasoning_tokens": 10}}})
        with OpenAI(api_key="sk-offline-fixture", max_retries=0,
                    http_client=httpx2.Client(transport=httpx2.MockTransport(transport))) as sdk:
            p = StructuredProvider("openai", "gpt-5.6-terra", sdk)
            result = generate(p)
        self.assertEqual(result.payload, {"items": []})
        self.assertEqual(result.usage.output_tokens, 40)
        self.assertIs(captured[0]["store"], False)
        self.assertEqual(captured[0]["reasoning"]["effort"], "none")

    def test_schemas_are_strict_without_changing_canonical_contract(self):
        tools = [FINDINGS_TOOL, REVIEW_TOOL, CHECK_TOOL, THEME_TOOL, *GROUPS.values()]
        before = deepcopy(tools)
        def inspect(s):
            if s.get("type") == "object":
                self.assertIs(s["additionalProperties"], False)
                self.assertEqual(set(s["required"]), set(s["properties"]))
                for v in s["properties"].values(): inspect(v)
            if s.get("type") == "array": inspect(s["items"])
            for key in ("anyOf", "oneOf", "allOf"):
                for v in s.get(key, []): inspect(v)
        for t in tools: inspect(strict_schema(t["input_schema"]))
        self.assertEqual(tools, before)
        item = {"vendor": "bmc", "usd_per_user_month": 20, "basis": "quoted", "operator": None,
                "quote": "an exact source quote", "timestamp": "00:01:00", "confidence": "high"}
        out = generate(provider(response({"items": [item]})), GROUPS["pricing"])
        self.assertNotIn("operator", out.payload["items"][0])

    def test_incomplete_refusal_invalid_json_missing_fields_and_multiple_outputs_fail(self):
        invalid_json = response({"items": []})
        invalid_json.output[0].content[0].text = "{"
        multiple = response({"items": []})
        multiple.output *= 2
        values = [response({"items": []}, status="incomplete"),
                  response({"items": []}, status="failed"), response({}, refusal=True),
                  response({}), response({"items": [{"finding": "missing fields"}]}),
                  invalid_json, multiple]
        for r in values:
            p = provider(r)
            with self.subTest(response=r), self.assertRaises(StructuredResponseError): generate(p)
            self.assertEqual(p.records[0]["status"], "failed")
            self.assertEqual(p.records[0]["usage"]["output_tokens"], 40)

    def test_anthropic_cutoff_and_duplicate_payloads_fail(self):
        cut = message("emit_findings", {"items": []}, stop="max_tokens")
        dup = message("emit_findings", {"items": []})
        dup.content *= 2
        for r in (cut, dup):
            p = StructuredProvider("anthropic", "claude-sonnet-5", Client(r))
            with self.assertRaises(StructuredResponseError): generate(p)

    def test_review_failure_and_missing_or_duplicate_reviews_block_confirmation(self):
        responses = [RuntimeError("review failed"), response({"checks": []}),
                     response({"checks": [{"index": 0, "supported": True, "reason": "x"}]*2})]
        for r in responses:
            p = provider(response({"items": [finding()]}), r)
            atoms, _, _ = extract_brief(p, "E1", TRANSCRIPT, BRIEF)
            self.assertNotEqual(atoms["findings"][0]["review_status"], "supported")

    def test_usage_does_not_double_count_reasoning_or_cache(self):
        u = normalized_usage("openai", response({}))
        self.assertEqual(asdict(u), dict(input_tokens=100, cached_input_tokens=20,
            cache_creation_input_tokens=0, output_tokens=40, reasoning_tokens=10))
        anth = NS(usage=NS(input_tokens=100, cache_read_input_tokens=30,
                          cache_creation_input_tokens=20, output_tokens=50))
        u = normalized_usage("anthropic", anth)
        self.assertEqual(u.input_tokens, 150)
        self.assertIsNone(u.reasoning_tokens)
        p = provider(response({"items": []}, usage=False))
        with self.assertRaises(StructuredResponseError): generate(p)
        self.assertIsNone(p.records[0]["usage"])

    def test_server_defaults_and_allowlists(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderConfigurationError): create_provider()
            p = create_provider(client=Client())
            self.assertEqual((p.provider, p.model), ("anthropic", "claude-sonnet-5"))
            with self.assertRaises(ProviderConfigurationError): create_provider("openai", "arbitrary-model", client=Responses())
            with self.assertRaises(ProviderConfigurationError): create_provider("arbitrary-provider", client=Responses())
        with patch.dict(os.environ, {"INTERVIEW_PROVIDER": "openai", "INTERVIEW_MODEL": "gpt-5.6-sol"}, clear=True):
            p = create_provider(client=Responses())
            self.assertEqual((p.provider, p.model), ("openai", "gpt-5.6-sol"))
            with self.assertRaises(api.Bad): api.model_client()

    def test_claim_and_synthesis_keep_citation_checks_and_thinking_roles(self):
        atoms = {"E1-f0": {"quote": QUOTE, "finding": "The sales cycle is four to nine months."}}
        claim = dict(verdict="supported", reasoning="The quote carries it.", atom_ids=["E1-f0", "invented"],
                     footnote="E1 line 3", caveats=["One expert."])
        synthesis = dict(summary={"text": "One expert.", "atom_ids": ["invented"]},
                         themes=[{"theme": "Timing", "takeaway": "A sales cycle.",
                                  "strength": "one expert", "atom_ids": ["E1-f0", "rejected"]}],
                         not_supported=["Market-wide outcomes."])
        p = provider(response(claim), response(synthesis))
        verdict = check_claim(p, "The sales cycle is four to nine months.", atoms, "One expert")
        self.assertFalse(verdict["citations_resolve"])
        self.assertEqual(verdict["atom_ids"], ["E1-f0"])
        summary, themes, _, dropped = draft_themes(p, atoms, "One expert", brief_mode=True)
        self.assertFalse(summary["citations_resolve"])
        self.assertFalse(themes[0]["citations_resolve"])
        self.assertEqual(set(dropped), {"invented", "rejected"})
        self.assertEqual(p.client.calls[0]["reasoning"], {"effort": "medium"})
        self.assertEqual(p.client.calls[1]["reasoning"], {"effort": "none"})


if __name__ == "__main__":
    unittest.main()
