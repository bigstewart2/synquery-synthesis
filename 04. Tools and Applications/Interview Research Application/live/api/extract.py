"""Public Harbor demo API: authenticate, extract the two samples and check findings.

The public handler enforces a fixed brief and two canonical fictional interviews.
General extraction helpers remain available for local development. Quote matching
and a separate model review run before human confirmation. Keys stay server-side.
"""

import base64
import concurrent.futures
import hmac
import io
import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _pipeline import (  # noqa: E402
    GROUPS, GROUP_LABELS, MODEL, THEME_MODEL, check_claim, draft_themes,
    extract_group, verify_citations,
)
from _brief import MAX_BRIEF_TRANSCRIPT, brief_id, context_note, extract_brief, validate_brief
from _harbor import BRIEF as HARBOR_BRIEF, SAMPLES as HARBOR_SAMPLES, DEMO_ID
from _providers import create_provider, settings, credential_name, ProviderConfigurationError

MAX_BYTES = 4 * 1024 * 1024        # a long transcript is ~100KB; this is generous
MAX_CHARS = 400_000                # guard the token bill on a pasted book


class Bad(Exception):
    """A client error worth reporting back verbatim. Never wraps a secret."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------- input
def read_docx(raw):
    """Extract paragraph text from a .docx without a heavyweight dependency chain."""
    try:
        import docx  # python-docx
    except ImportError:
        raise Bad(500, "python-docx is not installed on the server.")
    try:
        document = docx.Document(io.BytesIO(raw))
    except Exception:
        raise Bad(400, "That .docx could not be opened. Try exporting it as .txt.")
    return "\n".join(p.text for p in document.paragraphs)


def decode_upload(filename, b64):
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:
        raise Bad(400, "Upload was not valid base64.")
    if len(raw) > MAX_BYTES:
        raise Bad(413, f"File is larger than {MAX_BYTES // (1024 * 1024)}MB.")

    name = (filename or "").lower()
    if name.endswith(".docx"):
        text = read_docx(raw)
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise Bad(400, "File is not UTF-8 text. Upload .txt, .md, or .docx.")

    if len(text.strip()) < 200:
        raise Bad(400, "That file has almost no text in it.")
    if len(text) > MAX_CHARS:
        raise Bad(413, f"Transcript is longer than {MAX_CHARS:,} characters.")
    return text


def check_passcode(supplied):
    """Constant-time compare against the server's passcode.

    A missing DEMO_PASSCODE is a hard 500, never an open door -- a deploy that lost its
    env var must fail closed.
    """
    expected = os.environ.get("DEMO_PASSCODE")
    if not expected:
        raise Bad(500, "Server is missing DEMO_PASSCODE. Nothing will run until it is set.")
    if not hmac.compare_digest(str(supplied or ""), expected):
        raise Bad(401, "Wrong passcode.")


# --------------------------------------------------------------- work
def model_client():
    try:
        return create_provider()
    except ProviderConfigurationError as exc:
        raise Bad(500, str(exc)) from None


def run_extraction(text, expert_label):
    client = model_client()
    atoms, tok_in, tok_out, failures = {}, 0, 0, []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(GROUPS)) as pool:
        futures = {
            pool.submit(extract_group, client, expert_label, text, spec): group
            for group, spec in GROUPS.items()
        }
        for fut in concurrent.futures.as_completed(futures):
            group = futures[fut]
            try:
                items, usage = fut.result()
            except Exception as exc:
                # One group failing must not lose the other five.
                atoms[group] = []
                failures.append({"group": group, "error": type(exc).__name__})
                continue
            atoms[group] = items
            tok_in += usage.input_tokens
            tok_out += usage.output_tokens

    return atoms, {"input_tokens": tok_in, "output_tokens": tok_out}, failures


MAX_ATOMS = 400


def brief_from(payload):
    mode = payload.get("mode")
    if mode not in (None, "brief", "questionnaire"):
        raise Bad(400, "Choose a supported research approach.")
    if mode == "questionnaire" and payload.get("brief") is not None:
        raise Bad(400, "A questionnaire run cannot include a project brief.")
    if mode == "brief" or payload.get("brief") is not None:
        try:
            return validate_brief(payload.get("brief"))
        except ValueError as exc:
            raise Bad(400, str(exc))
    return None


def confirmed_from(payload):
    """Pull and validate the confirmed-atom set both judgement routes depend on."""
    confirmed = payload.get("confirmed") or {}
    if not isinstance(confirmed, dict) or not confirmed:
        raise Bad(400, "No confirmed atoms were sent. Confirm some atoms first.")
    if len(confirmed) > MAX_ATOMS:
        raise Bad(413, f"More than {MAX_ATOMS} atoms sent.")
    brief = brief_from(payload)
    for aid, a in confirmed.items():
        if not isinstance(a, dict) or "quote" not in a:
            raise Bad(400, f"Atom {aid} is malformed.")
        if brief and (a.get("brief_id") != brief_id(brief) or a.get("verified") is not True or
                      a.get("review_status") != "supported"):
            raise Bad(400, "Use confirmed, source-checked findings from this project brief only.")
    return confirmed


def expert_note_from(payload):
    """Tell the model exactly how many experts it is reasoning over.

    This is what licenses panel-level language. With one transcript, any claim about
    agreement is unsupportable; with three, "several experts" becomes a real finding and
    a disagreement between them is itself the finding.
    """
    labels = payload.get("experts") or [payload.get("expert") or "E1"]
    n = len(labels)
    ids = ", ".join(str(x) for x in labels)
    brief = brief_from(payload)
    research = context_note(brief) if brief else ""
    if n == 1:
        return (f"These atoms come from 1 expert interview (label: {ids}). "
                "Because this is a single expert, nothing here may be written or graded "
                "as if a panel agreed." + research)
    return (f"These atoms come from a panel of {n} expert interviews ({ids}). "
            f"Every atom id is prefixed with its expert label. "
            f"Attribute every figure to the expert it came from. A claim covering all {n} "
            f"needs support from all {n}; two out of three is 'several experts', never the "
            f"whole panel. Where experts disagree, the disagreement is the finding -- "
            f"never average them." + research)


def run_check(payload):
    claim = (payload.get("claim") or "").strip()
    if len(claim) < 10:
        raise Bad(400, "Write a claim to check — at least a sentence.")
    if len(claim) > 2000:
        raise Bad(413, "Claim is too long.")
    confirmed = confirmed_from(payload)

    client = model_client()
    result = check_claim(client, claim, confirmed,
                         expert_note_from(payload))
    result["ok"] = True
    result["model"] = client.model
    result["provider"] = client.provider
    result["atoms_used"] = len(confirmed)
    return result


def run_themes(payload):
    """Draft themes from atoms the client says the human confirmed.

    The client sends only confirmed atoms. That is the whole gate: an atom the analyst
    rejected is never in this request, so the model cannot build an argument on it.
    """
    confirmed = confirmed_from(payload)
    client = model_client()
    summary, themes, not_supported, dropped = draft_themes(
        client, confirmed, expert_note_from(payload), brief_mode=brief_from(payload) is not None)
    return {
        "ok": True,
        "summary": summary,
        "themes": themes,
        "not_supported": not_supported,
        "dropped_citations": dropped,
        "model": client.model,
        "provider": client.provider,
        "atoms_used": len(confirmed),
    }


# --------------------------------------------------------------- handler
class handler(BaseHTTPRequestHandler):

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # A health probe that proves configuration without proving the passcode.
        try:
            provider, model = settings()
        except ProviderConfigurationError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
            return
        self._send(200, {
            "ok": True,
            "model": model,
            "provider": provider,
            "groups": ["findings"],
            "research_modes": ["brief"],
            "demo": DEMO_ID,
            "sample_ids": list(HARBOR_SAMPLES),
            "configured": {
                credential_name(provider): bool(os.environ.get(credential_name(provider))),
                "DEMO_PASSCODE": bool(os.environ.get("DEMO_PASSCODE")),
            },
        })

    def do_POST(self):
        started = time.time()
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                raise Bad(400, "Empty request body.")
            if length > MAX_BYTES * 2:
                raise Bad(413, "Request body too large.")
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                raise Bad(400, "Request body was not valid JSON.")

            if not isinstance(payload, dict):
                raise Bad(400, "A JSON object is required.")
            check_passcode(payload.get("passcode"))
            if payload.get("action") == "authenticate":
                # Entry check only. No transcript processing or paid model call.
                self._send(200, {"ok": True})
                return

            # One entrypoint serves both routes; branch on the path.
            route = self.path.rstrip("/")
            if route not in ("/api/extract", "/api/themes", "/api/check"):
                raise Bad(404, "Unknown demo route.")
            if any(k in payload for k in ("provider", "model", "reasoning_effort")):
                raise Bad(400, "Model selection is configured on the server.")
            # The public demo is sample-only. Keep the general extraction helpers
            # available for local development, but never accept arbitrary inputs here.
            if any(k in payload for k in ("b64", "filename", "text", "transcript", "expert")):
                raise Bad(400, "This demo accepts only the two supplied Harbor interviews. Reload and select a sample.")
            if payload.get("mode") not in (None, "brief") or (
                    "brief" in payload and payload["brief"] != HARBOR_BRIEF):
                raise Bad(400, "This demo uses the fixed Harbor brief. Start a new Harbor demo to continue.")
            payload["mode"], payload["brief"] = "brief", HARBOR_BRIEF
            if route.endswith("/themes") or route.endswith("/check"):
                try:
                    result = run_themes(payload) if route.endswith("/themes") \
                        else run_check(payload)
                except ValueError as exc:
                    raise Bad(502, str(exc))
                result["elapsed_s"] = round(time.time() - started, 1)
                self._send(200, result)
                return

            sample_id = payload.get("sample_id")
            if not isinstance(sample_id, str) or sample_id not in HARBOR_SAMPLES:
                raise Bad(400, "Choose David’s or Maria’s Harbor interview from the sample list.")
            sample = HARBOR_SAMPLES[sample_id]
            filename, text, expert_label = sample["filename"], sample["text"], sample["label"]
            brief = brief_from(payload)
            if brief:
                if len(text) > MAX_BRIEF_TRANSCRIPT:
                    raise Bad(413, f"For this demo, keep each interview under {MAX_BRIEF_TRANSCRIPT:,} characters.")
                client = model_client()
                try:
                    atoms, usage, failures = extract_brief(client, expert_label, text, brief)
                except ValueError as exc:
                    raise Bad(502, str(exc))
                stats = {"total": len(atoms["findings"]),
                         "verified": sum(a["verified"] for a in atoms["findings"])}
                labels = {"findings": "Findings for your research questions"}
            else:
                atoms, usage, failures = run_extraction(text, expert_label)
                stats = verify_citations(atoms, text)
                labels = GROUP_LABELS
            stats.update(
                elapsed_s=round(time.time() - started, 1),
                model=settings()[1],
                provider=settings()[0],
                usage=usage,
                chars=len(text),
            )

            self._send(200, {
                "ok": True,
                "expert": expert_label,
                "filename": filename,
                "atoms": atoms,
                "labels": labels,
                "brief": brief,
                "brief_id": brief_id(brief) if brief else None,
                "stats": stats,
                "failures": failures,
            })

        except Bad as e:
            self._send(e.status, {"ok": False, "error": e.message})
        except Exception:
            # Log the trace server-side; return nothing that could carry a secret.
            traceback.print_exc()
            self._send(500, {"ok": False, "error": "Extraction failed on the server."})
