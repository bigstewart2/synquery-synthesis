# Synquery verification lessons

## Source privacy checks and local environments — October 27, 2026

For source privacy audits, keep the actual application and public output covered while excluding generated Python environments and caches. The preserved pilot environment caused the existing audit to flag a dependency implementation as source content. Check the original failure, the normal source build/audit and a deliberately introduced forbidden term in a real source file; the latter must still fail. Resolve script paths before selecting the scan/output root so legacy symlink entry points use the same complete app.

Evidence: the local organization pass preserved the original 426-assertion audit failure in `.venv-pilot` and adds the narrow generated-directory exclusion in `build.py`, with resolved application roots in `build.py` and `verify.py`. The existing organization plan owns before/after results and limits. This is a local verification lesson, not a provider benchmark, deployment or proof of hosted quality.

**Verification limit:** the pre-move source-only audit and moved audit both flag a name collision inside the fictional Harbor sample module. The 426-assertion content audit and static build therefore remain unsuccessful on that existing condition; seven live/provider offline suites pass. The source probe still fails as required. Keep the original submitted site byte-identical and address that older audit policy/sample conflict in its own scoped follow-up before claiming a fresh static build.

**Independent review correction:** moving the build script must not reduce the privacy scan to only its new app folder. Keep guides and the frozen submission covered by scanning the canonical workspace, with compatibility symlinks skipped to avoid duplicate paths. The app remains the template/output root.

**Compatibility ignore check:** test the old alias itself with `git check-ignore --no-index`. A directory-only rule such as `__pycache__/` does not match a symlink named `__pycache__`; the root alias needs an explicit name rule. The normal generated directory and the legacy alias must both stay excluded.
