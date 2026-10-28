#!/usr/bin/env python3
"""Assert the live extraction contract still matches the submitted prototype's.

The live app duplicates the schema from pipeline/extract.py so it can be deployed as a
self-contained function. Duplication that nothing checks is duplication that silently
drifts, and a drifted schema would quietly invalidate the 52/52 and 11/11 scoring the
write-up cites. This fails loudly instead.

    python3 dev/check_schema.py
"""

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "live" / "api"))


def load(alias, path):
    """Load by explicit path. Both trees contain an extract.py, so a plain import
    would resolve by sys.path order and silently compare a file against itself."""
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


submitted = load("_submitted_extract", ROOT / "pipeline" / "extract.py")
live = load("_live_pipeline", ROOT / "live" / "api" / "_pipeline.py")

fails = []


def same(name, a, b):
    if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
        fails.append(name)
        print(f"  DRIFT  {name}")
    else:
        print(f"  ok     {name}")


print("comparing live/api/_pipeline.py against pipeline/extract.py\n")
same("MODEL", submitted.MODEL, live.MODEL)
same("SYSTEM", submitted.SYSTEM, live.SYSTEM)
same("CITATION", submitted.CITATION, live.CITATION)
same("VENDORS", submitted.VENDORS, live.VENDORS)
same("GROUPS", submitted.GROUPS, live.GROUPS)

missing = set(live.GROUPS) - set(live.GROUP_LABELS)
if missing:
    fails.append("GROUP_LABELS")
    print(f"  DRIFT  GROUP_LABELS missing: {sorted(missing)}")
else:
    print("  ok     GROUP_LABELS")

if fails:
    sys.exit(f"\nFAIL: {len(fails)} contract(s) drifted: {', '.join(fails)}")
print("\nPASS: the live app extracts against the same contract that was scored.")
