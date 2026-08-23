"""Extraction schema and citation check, shared by the HTTP function and the dev CLI.

This is the same schema-first contract as pipeline/extract.py in the static prototype:
the interview guide is treated as a schema, the model is asked only to LOCATE and TYPE
what was said, and every atom must carry a verbatim quote plus a timestamp.

The one thing that changes here is what happens afterwards. The static prototype scored
extraction against a hand-verified answer key (facts.json). No answer key exists for a
transcript nobody has read yet, so this module keeps the half of that check which needs
no ground truth -- does the quote actually appear in the source -- and leaves the value
judgement to a human in the review queue.
"""

import re
import unicodedata

MODEL = "claude-sonnet-5"

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

# Field labels for the review queue. Kept beside the schema so a new field cannot be
# added to GROUPS without a label being noticed as missing.
GROUP_LABELS = {
    "ranked_criteria": "Ranked criteria",
    "ratings": "Vendor ratings",
    "pricing": "Pricing",
    "commercial_terms": "Commercial terms",
    "loyalty": "Loyalty & satisfaction",
    "switching": "Switching",
}


# --------------------------------------------------------------- citation check
def norm(s):
    """Normalise for verbatim comparison. Identical to pipeline/score.py's norm()."""
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("‐", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def verify_citations(atoms, transcript_text):
    """Stamp every atom with verified True/False. Deterministic, no model, no answer key.

    This is the check that would fail a build in production, and the only half of the
    static prototype's scoring that survives contact with an unseen transcript.
    """
    haystack = norm(transcript_text)
    total = verified = 0
    for items in atoms.values():
        for it in items:
            total += 1
            ok = norm(it.get("quote", "")) in haystack
            it["verified"] = ok
            verified += ok
    return {"total": total, "verified": verified}


# --------------------------------------------------------------- extraction
def extract_group(client, expert, transcript, spec):
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
