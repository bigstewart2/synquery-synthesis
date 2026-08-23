"""POST /api/extract -- turn one uploaded transcript into typed, cited atoms.

This is the back end the static prototype does not have. Three things happen here that
cannot happen in a browser or in a committed HTML file:

  1. The Anthropic key lives server-side. It is read from the environment at request
     time and never leaves this process.
  2. The six extraction groups run concurrently against the model.
  3. Every returned quote is checked verbatim against the uploaded source before the
     browser ever sees it.

Request  JSON {passcode, filename, b64}
Response JSON {ok, expert, atoms{group: [atom]}, stats, labels}
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

    text = text.strip()
    if len(text) < 200:
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
def run_extraction(text, expert_label):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise Bad(500, "Server is missing ANTHROPIC_API_KEY.")
    import anthropic

    client = anthropic.Anthropic()
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


def confirmed_from(payload):
    """Pull and validate the confirmed-atom set both judgement routes depend on."""
    confirmed = payload.get("confirmed") or {}
    if not isinstance(confirmed, dict) or not confirmed:
        raise Bad(400, "No confirmed atoms were sent. Confirm some atoms first.")
    if len(confirmed) > MAX_ATOMS:
        raise Bad(413, f"More than {MAX_ATOMS} atoms sent.")
    for aid, a in confirmed.items():
        if not isinstance(a, dict) or "quote" not in a:
            raise Bad(400, f"Atom {aid} is malformed.")
    return confirmed


def expert_note_from(payload):
    expert = payload.get("expert") or "this expert"
    n = payload.get("n_experts") or 1
    return (f"These atoms come from {n} expert interview{'' if n == 1 else 's'} "
            f"(label: {expert}). "
            + ("Because this is a single expert, nothing here may be written or graded "
               "as if the whole panel agreed." if n == 1 else ""))


def run_check(payload):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise Bad(500, "Server is missing ANTHROPIC_API_KEY.")
    claim = (payload.get("claim") or "").strip()
    if len(claim) < 10:
        raise Bad(400, "Write a claim to check — at least a sentence.")
    if len(claim) > 2000:
        raise Bad(413, "Claim is too long.")
    confirmed = confirmed_from(payload)

    import anthropic
    result = check_claim(anthropic.Anthropic(), claim, confirmed,
                         expert_note_from(payload))
    result["ok"] = True
    result["model"] = THEME_MODEL
    result["atoms_used"] = len(confirmed)
    return result


def run_themes(payload):
    """Draft themes from atoms the client says the human confirmed.

    The client sends only confirmed atoms. That is the whole gate: an atom the analyst
    rejected is never in this request, so the model cannot build an argument on it.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise Bad(500, "Server is missing ANTHROPIC_API_KEY.")

    confirmed = confirmed_from(payload)

    import anthropic
    themes, not_supported, dropped = draft_themes(
        anthropic.Anthropic(), confirmed, expert_note_from(payload))
    return {
        "ok": True,
        "themes": themes,
        "not_supported": not_supported,
        "dropped_citations": dropped,
        "model": THEME_MODEL,
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
        self._send(200, {
            "ok": True,
            "model": MODEL,
            "groups": list(GROUPS),
            "configured": {
                "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY")),
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

            check_passcode(payload.get("passcode"))

            # One entrypoint serves both routes; branch on the path.
            route = self.path.rstrip("/")
            if route.endswith("/themes") or route.endswith("/check"):
                result = run_themes(payload) if route.endswith("/themes") \
                    else run_check(payload)
                result["elapsed_s"] = round(time.time() - started, 1)
                self._send(200, result)
                return

            filename = payload.get("filename") or "transcript.txt"
            text = decode_upload(filename, payload.get("b64"))
            expert_label = payload.get("expert") or "E1"

            atoms, usage, failures = run_extraction(text, expert_label)
            stats = verify_citations(atoms, text)
            stats.update(
                elapsed_s=round(time.time() - started, 1),
                model=MODEL,
                usage=usage,
                chars=len(text),
            )

            self._send(200, {
                "ok": True,
                "expert": expert_label,
                "filename": filename,
                "atoms": atoms,
                "labels": GROUP_LABELS,
                "stats": stats,
                "failures": failures,
            })

        except Bad as e:
            self._send(e.status, {"ok": False, "error": e.message})
        except Exception:
            # Log the trace server-side; return nothing that could carry a secret.
            traceback.print_exc()
            self._send(500, {"ok": False, "error": "Extraction failed on the server."})
