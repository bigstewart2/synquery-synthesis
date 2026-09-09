"""Extraction schema and citation check, shared by the HTTP function and the dev CLI.

This is the same schema-first contract as pipeline/extract.py in the static prototype:
the interview guide is treated as a schema, the model is asked only to LOCATE and TYPE
what was said, and every atom must carry a verbatim quote plus a timestamp.

The one thing that changes here is what happens afterwards. The static prototype scored
extraction against a verified answer key (facts.json) built during the take-home. No
answer key exists for a
transcript nobody has read yet, so this module keeps the half of that check which needs
no ground truth -- does the quote actually appear in the source -- and leaves the value
judgement to a human in the review queue.
"""

import json
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


# --------------------------------------------------------------- theme drafting
#
# Drafting is a SEPARATE step from extraction, on purpose, and it obeys the same rule
# that makes extraction trustworthy: nothing may be asserted that isn't traceable.
#
# Extraction cites the transcript, and the server checks every quote verbatim.
# Drafting cites ATOMS, and the server checks every atom id against the confirmed set.
# A theme resting on an atom the analyst rejected cannot survive that check. So the
# human's confirm/reject decisions bound what the model is allowed to argue.
#
# Model differs from extraction deliberately. Extraction is pinned to sonnet-5 because
# the 52/52 and 11/11 figures were measured on it. Drafting has no such parity to keep
# and is judgment-heavy, so it runs on the stronger model.

THEME_MODEL = "claude-opus-5"

THEME_TOOL = {
    "name": "emit_themes",
    "description": "Draft candidate themes strictly from the confirmed atoms supplied.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {
                "type": "object",
                "description": "The connected paragraph a client reads first, before any "
                "bullet. This is prose, not a list of the themes restated.",
                "additionalProperties": False,
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Three to five sentences. Lead with the finding that "
                        "changes a decision, not with background. Every number in it must "
                        "appear in a cited atom. Name the sample size in the last sentence.",
                    },
                    "atom_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ids of every atom the summary rests on, copied exactly.",
                    },
                },
                "required": ["text", "atom_ids"],
            },
            "themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "theme": {
                            "type": "string",
                            "description": "Short label, two to five words. No punctuation.",
                        },
                        "takeaway": {
                            "type": "string",
                            "description": "One sentence an analyst could put on a slide. Every "
                            "number in it must appear in a cited atom.",
                        },
                        "atom_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "ids of the confirmed atoms this rests on, copied "
                            "exactly from the supplied list. Never invent an id.",
                        },
                        "strength": {
                            "type": "string",
                            "enum": ["one expert", "several experts", "whole panel"],
                            "description": "How much of the panel actually supports this.",
                        },
                    },
                    "required": ["theme", "takeaway", "atom_ids", "strength"],
                },
            },
            "not_supported": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Claims a reader might expect this panel to support but it does "
                "not, given what was and was not asked. Name real gaps, not hedges.",
            },
        },
        "required": ["summary", "themes", "not_supported"],
    },
}

THEME_SYSTEM = """You draft candidate themes for an analyst from expert-interview facts that a human has already reviewed and confirmed.

You are writing a FIRST DRAFT that the analyst will edit. You are not the author of record.

Rules, in priority order:
1. Every theme must cite at least one atom id from the supplied list, copied exactly. Never cite an id that was not supplied.
2. Never state a number, vendor, or fact that does not appear in a cited atom. If you cannot cite it, do not write it.
3. Do not average, extrapolate, or reconcile inconsistent atoms. If two atoms disagree, that disagreement is itself the theme.
4. Match the strength claim to the evidence. Facts from a single transcript are "one expert" and must not be written as if the whole panel agreed.
5. Prefer four sharp themes to eight soft ones. A theme that restates one atom is not a theme.
6. not_supported must name real gaps a partner would otherwise assume were covered. Silence on a topic is a gap, not a finding.
7. The summary is prose a client reads before any bullet. Lead with what changes a decision. Do not open with background, do not restate the theme list, and do not end on a flourish. Name the sample size plainly in the last sentence.
"""


def judgement_payload(message, tool_name):
    if getattr(message, "stop_reason", None) == "max_tokens":
        raise ValueError("The model response was cut off. Please retry with fewer confirmed findings.")
    for block in message.content:
        if block.type == "tool_use" and block.name == tool_name and isinstance(block.input, dict):
            return block.input
    raise ValueError("The model did not return a complete structured response. Please retry.")


def draft_themes(client, atoms_by_id, expert_note, brief_mode=False):
    """Draft themes from confirmed atoms, then drop any citation that does not resolve.

    Returns (summary, themes, not_supported, dropped_ids). A theme left with no valid citation is
    kept and flagged rather than silently deleted -- a disappearing theme hides a bug.
    """
    listing = "\n".join(
        f"[{aid}] {json.dumps({k: v for k, v in a.items() if k not in ('verified', 'review_note', 'review_status', 'brief_id')}, ensure_ascii=False)}"
        for aid, a in atoms_by_id.items()
    )
    msg = client.messages.create(
        model=THEME_MODEL,
        max_tokens=8000,
        system=THEME_SYSTEM,
        tools=[THEME_TOOL],
        tool_choice={"type": "tool", "name": "emit_themes"},
        **({} if brief_mode else {"thinking": {"type": "adaptive"}}),
        messages=[{
            "role": "user",
            "content": f"{expert_note}\n\nConfirmed atoms:\n{listing}\n\n"
                       f"Draft the themes these atoms support.",
        }],
    )
    payload = judgement_payload(msg, "emit_themes")
    summary = payload.get("summary")
    if (not isinstance(summary, dict) or not isinstance(summary.get("text"), str) or
        not isinstance(summary.get("atom_ids"), list) or
        not isinstance(payload.get("themes"), list) or not isinstance(payload.get("not_supported"), list)):
        raise ValueError("The synthesis response was incomplete. Please retry.")
    for theme in payload["themes"]:
        if (not isinstance(theme, dict) or not all(isinstance(theme.get(k), str) for k in ("theme", "takeaway", "strength")) or
            not isinstance(theme.get("atom_ids"), list)):
            raise ValueError("A synthesis finding was incomplete. Please retry.")

    known, dropped = set(atoms_by_id), []

    summary = payload.get("summary") or {}
    if isinstance(summary, str):          # seen in the wild: prose instead of the object
        summary = {"text": summary, "atom_ids": []}
    elif not isinstance(summary, dict):
        summary = {"text": "", "atom_ids": []}
    s_cited = summary.get("atom_ids") or []
    s_good = [i for i in s_cited if i in known]
    dropped.extend(i for i in s_cited if i not in known)
    summary["atom_ids"] = s_good
    summary["citations_resolve"] = bool(s_good) and len(s_good) == len(s_cited)

    themes = []
    for t in payload.get("themes", []) or []:
        if not isinstance(t, dict):
            continue
        cited = t.get("atom_ids") or []
        good = [i for i in cited if i in known]
        dropped.extend(i for i in cited if i not in known)
        t["atom_ids"] = good
        t["citations_resolve"] = bool(good) and len(good) == len(cited)
        themes.append(t)

    return summary, themes, payload.get("not_supported", []), dropped


# --------------------------------------------------------------- slide check
#
# The live form of the submitted site's Summary tab. There, five representative slide
# claims were graded against facts.json. Here any claim can be graded against whatever
# the analyst confirmed, which is the version that works on a transcript nobody read.
#
# The verdict is the model's. The footnote is what makes it usable: a partner pastes it
# under the claim and the provenance travels with the number.

CHECK_TOOL = {
    "name": "emit_verdict",
    "description": "Grade one claim against the confirmed atoms supplied.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["supported", "partially supported", "not supported", "contradicted"],
                "description": "not supported = no atom bears on it. contradicted = an atom "
                "says the opposite. Never use 'supported' when the atoms only imply it.",
            },
            "reasoning": {
                "type": "string",
                "description": "One sentence naming exactly which part of the claim the atoms "
                "carry and which part they do not.",
            },
            "atom_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "ids of every confirmed atom bearing on this claim, supporting "
                "or contradicting. Copy exactly. Never invent an id.",
            },
            "footnote": {
                "type": "string",
                "description": "A paste-ready source note for the bottom of a slide. Name the "
                "expert label, the figures, and the timestamps. One or two sentences. No "
                "hedging language and no citation of anything outside the atoms.",
            },
            "caveats": {
                "type": "array",
                "items": {"type": "string"},
                "description": "What a reader would wrongly assume from this claim. Include "
                "sample size whenever the evidence is one expert.",
            },
        },
        "required": ["verdict", "reasoning", "atom_ids", "footnote", "caveats"],
    },
}

CHECK_SYSTEM = """You grade a claim an analyst intends to put on a slide against expert-interview facts a human has already confirmed.

You are a check, not an advocate. Your job is to stop a claim the evidence cannot carry.

Rules, in priority order:
1. Judge only against the supplied atoms. If nothing bears on the claim, the verdict is "not supported" -- that is a correct and useful answer, not a failure.
2. Never state a number that does not appear in a cited atom.
3. A claim that is directionally right but numerically wrong is "partially supported", never "supported". Say which number is off.
4. Evidence from one expert can never support a claim written about buyers, the market, or most companies. Grade the claim as written.
5. The footnote must let a reader trace every figure back without the transcript in front of them.
6. Caveats name what a reader would wrongly conclude. Sample size is always one of them when the evidence is a single expert.
"""


def check_claim(client, claim, atoms_by_id, expert_note):
    """Grade one claim. Same citation discipline as drafting -- ids must resolve."""
    listing = "\n".join(
        f"[{aid}] {json.dumps({k: v for k, v in a.items() if k not in ('verified', 'review_note', 'review_status', 'brief_id')}, ensure_ascii=False)}"
        for aid, a in atoms_by_id.items()
    )
    msg = client.messages.create(
        model=THEME_MODEL,
        max_tokens=4000,
        system=CHECK_SYSTEM,
        tools=[CHECK_TOOL],
        tool_choice={"type": "tool", "name": "emit_verdict"},
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": f"{expert_note}\n\nConfirmed atoms:\n{listing}\n\n"
                       f"Claim to grade:\n\"{claim}\"",
        }],
    )
    out = judgement_payload(msg, "emit_verdict")
    if (out.get("verdict") not in ("supported", "partially supported", "not supported", "contradicted") or
        not all(isinstance(out.get(k), str) for k in ("reasoning", "footnote")) or
        not isinstance(out.get("atom_ids"), list) or not isinstance(out.get("caveats"), list)):
        raise ValueError("The claim-check response was incomplete. Please retry.")

    known = set(atoms_by_id)
    if not isinstance(out, dict):
        out = {}
    cited = out.get("atom_ids") or []
    good = [i for i in cited if i in known]
    out["atom_ids"] = good
    out["citations_resolve"] = len(good) == len(cited)
    out["claim"] = claim
    return out


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
            quote = norm(it.get("quote", ""))
            ok = bool(quote) and quote in haystack
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
