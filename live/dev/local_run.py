#!/usr/bin/env python3
"""Exercise the live function's real code path locally, without deploying.

Calls the same decode -> extract -> verify functions the HTTP handler calls, so a pass
here means the deployed function fails only for reasons of environment, not of logic.

    source ~/.config/secrets.env
    python3 dev/local_run.py "/path/to/transcript.docx"
"""

import base64
import importlib.util
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

spec = importlib.util.spec_from_file_location("_live_fn", ROOT / "api" / "extract.py")
fn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fn)

if len(sys.argv) < 2:
    sys.exit("usage: local_run.py <transcript path>")
path = pathlib.Path(sys.argv[1])
if not path.exists():
    sys.exit(f"no such file: {path}")
if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY not set. Run: source ~/.config/secrets.env")

b64 = base64.b64encode(path.read_bytes()).decode()
print(f"file      {path.name}  ({len(b64) * 3 // 4 // 1024} KB)")

text = fn.decode_upload(path.name, b64)
print(f"decoded   {len(text):,} chars")

print("extracting six groups concurrently ...")
atoms, usage, failures = fn.run_extraction(text, "E-test")
stats = fn.verify_citations(atoms, text)

print()
for group, items in atoms.items():
    ok = sum(1 for i in items if i["verified"])
    print(f"  {group:<18} {len(items):>3} atoms   {ok}/{len(items)} quotes verified")

print(f"\ntotal     {stats['verified']}/{stats['total']} quotes verified verbatim")
print(f"tokens    {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")
if failures:
    print(f"FAILURES  {failures}")

bad = [(g, i["quote"][:70]) for g, items in atoms.items() for i in items if not i["verified"]]
if bad:
    print(f"\n{len(bad)} unverified quote(s) -- these render with a red badge, not silently:")
    for g, q in bad[:8]:
        print(f"  [{g}] {q}")

out = ROOT / "dev" / "last_run.json"
out.write_text(json.dumps({"atoms": atoms, "stats": stats}, indent=2))
print(f"\nwrote {out}")

if stats["total"] == 0:
    sys.exit("FAIL: zero atoms extracted -- the page would render empty.")
print("PASS: the function's code path works end to end.")
