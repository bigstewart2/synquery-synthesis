#!/usr/bin/env python3
"""
Schema-first extraction over Synquery expert transcripts.

The thesis this tests: the interview guide is already a schema, so synthesis
should be typed extraction against that schema plus deterministic aggregation,
not free-form summarisation.

Every atom must come back with a verbatim quote and a timestamp. The model is
never asked to compute anything -- only to locate and type what was said.

Usage:
    source ~/.config/secrets.env && python3 extract.py
Writes out/extracted.json at the repo root (gitignored).
"""

import json
import os
import pathlib
import sys

import anthropic

HERE = pathlib.Path(__file__).parent
CASE = pathlib.Path("/Users/stephenlese/dev/AI Projects/projects/career/companies/interviews/synquery/Case Study")
TRANSCRIPTS = {
    "E1": CASE / "transcripts-txt" / "Synquery FULL-transcript_ITSM Test_Expert1.txt",
    "E2": CASE / "transcripts-txt" / "Synquery_FULL-transcript_ITSM Test_Expert2.txt",
    "E3": CASE / "transcripts-txt" / "Synquery_FULL-transcript_ITSM Test_Expert3.txt",
}
MODEL = "claude-sonnet-5"

# ---------------------------------------------------------------------------
# The schema. In production this is generated from the interview guide at
# workstream setup and confirmed by a human once, not hand-written per project.
# ---------------------------------------------------------------------------

CITATION = {
    "quote": {
        "type": "string",
        "description": "Verbatim span from the transcript, copied exactly. Never paraphrase.",
    },
    "timestamp": {
        "type": "string",
        "description": "The HH:MM:SS timestamp of the turn the quote came from.",
    },
    "confidence": {
        "type": "string",
        "enum": ["high", "medium", "low"],
        "description": "low if the value had to be inferred rather than read off the text.",
    },
}

VENDORS = [
    "servicenow", "bmc", "freshservice", "ivanti", "jira", "zendesk",
    "manageengine", "other",
]


def arr(name, item_props, required, desc):
    return {
        "name": name,
        "description": desc,
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {**item_props, **CITATION},
                        "required": required + ["quote", "timestamp", "confidence"],
                    },
                }
            },
            "required": ["items"],
        },
    }


GROUPS = {
    "ranked_criteria": arr(
        "emit_ranked_criteria",
        {
            "rank": {"type": "integer", "description": "1 is the highest priority."},
            "criterion": {"type": "string", "description": "As the expert said it."},
        },
        ["rank", "criterion"],
        "The expert's purchasing criteria, ONLY where they gave an explicit priority "
        "ranking when asked to rank in strict priority order. Do not include criteria "
        "they merely listed without ranking.",
    ),
    "ratings": arr(
        "emit_ratings",
        {
            "criterion": {"type": "string"},
            "vendor": {"type": "string", "enum": VENDORS},
            "score": {"type": "number", "description": "The number the expert gave."},
            "scale_max": {"type": "integer", "description": "The maximum of the scale the expert used."},
        },
        ["criterion", "vendor", "score", "scale_max"],
        "Every numeric vendor rating the expert gave against a named criterion. "
        "One item per vendor per criterion.",
    ),
    "pricing": arr(
        "emit_pricing",
        {
            "vendor": {"type": "string", "enum": VENDORS},
            "usd_per_user_month": {"type": "number"},
            "operator": {"type": "string", "enum": ["=", ">", "<", "~"]},
            "basis": {
                "type": "string",
                "enum": ["paid", "quoted", "recalled", "illustrative"],
                "description": "paid = a price their org actually pays. quoted = a price a vendor "
                "quoted them during an evaluation. recalled = remembered from elsewhere or the past. "
                "illustrative = a figure the expert set as a comparison anchor rather than a real price.",
            },
        },
        ["vendor", "usd_per_user_month", "basis"],
        "Per-user or per-agent monthly prices. If a range was given, use its midpoint "
        "and set operator to '~'.",
    ),
    "commercial_terms": arr(
        "emit_commercial_terms",
        {
            "field": {
                "type": "string",
                "enum": ["renewal_uplift_pct", "implementation_months", "over_budget_pct"],
            },
            "low": {"type": "number"},
            "high": {"type": "number", "description": "Same as low if a single figure was given."},
        },
        ["field", "low", "high"],
        "Commercial and delivery facts. Convert weeks to months for implementation_months.",
    ),
    "loyalty": arr(
        "emit_loyalty",
        {
            "field": {"type": "string", "enum": ["continue_3yr", "recommend"]},
            "value": {"type": "number"},
            "scale_asked_max": {"type": "integer", "description": "The scale maximum the INTERVIEWER asked for."},
            "scale_answered_max": {"type": "integer", "description": "The scale maximum the EXPERT actually used."},
        },
        ["field", "value", "scale_asked_max", "scale_answered_max"],
        "Satisfaction and loyalty scores. Record the interviewer's stated scale and the "
        "expert's scale separately, even when they disagree. Do not reconcile them.",
    ),
    "switching": arr(
        "emit_switching",
        {
            "difficulty_1_10": {"type": "number"},
            "next_platform": {"type": "string", "enum": VENDORS + ["none_named"]},
            "trigger": {"type": "string", "description": "What would make them seriously evaluate a switch."},
        },
        ["difficulty_1_10"],
        "Switching difficulty, the platform they would evaluate first, and the trigger.",
    ),
}

SYSTEM = """You extract typed facts from expert-interview transcripts for a research product.

Rules, in priority order:
1. Every item you emit must be supported by a verbatim quote you copy exactly from the transcript. If you cannot copy a supporting quote, do not emit the item.
2. Never compute, average, convert between vendors, or reconcile inconsistencies. Record what was said, including when it is internally inconsistent.
3. Emit nothing for a field the expert was not asked about or did not answer. An empty list is a correct answer.
4. Attribute a rating to a vendor only when the expert named that vendor for that criterion. Never carry a rating across criteria.
"""


def extract(client, expert, transcript, group, spec):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM,
        tools=[spec],
        tool_choice={"type": "tool", "name": spec["name"]},
        messages=[{
            "role": "user",
            "content": f"<transcript expert=\"{expert}\">\n{transcript}\n</transcript>\n\n"
                       f"Extract: {spec['description']}",
        }],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return block.input.get("items", []), msg.usage
    return [], msg.usage


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set. Run: source ~/.config/secrets.env")
    client = anthropic.Anthropic()

    out, tok_in, tok_out = {}, 0, 0
    for expert, path in TRANSCRIPTS.items():
        text = path.read_text()
        out[expert] = {}
        for group, spec in GROUPS.items():
            items, usage = extract(client, expert, text, group, spec)
            out[expert][group] = items
            tok_in += usage.input_tokens
            tok_out += usage.output_tokens
            print(f"  {expert} {group}: {len(items)} items", flush=True)

    out["_usage"] = {"input_tokens": tok_in, "output_tokens": tok_out, "model": MODEL}
    out_dir = HERE.resolve().parent.parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "extracted.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote {out_dir / 'extracted.json'}  ({tok_in} in / {tok_out} out)")


if __name__ == "__main__":
    main()
