# Live extraction (the back end the submission doesn't have)

**Live:** https://synquery-live.vercel.app (passcode-gated)
**Sibling:** https://synquery-synthesis.vercel.app — the submitted static prototype, unchanged.

## Current workflow: project brief first

New projects begin with three fields: project name, the decision/context, and one to six research questions. The editable Harbor example is a convenience, not evidence or an answer key. Saving a brief makes no model call.

`api/_brief.py` receives the brief and complete interview together. One model call proposes up to 30 relevant findings with a type (observation, opinion, estimate, risk, recommendation or open question) and a contiguous quote. Deterministic matching locates each quote in the source, preserving original line numbers; it does not invent timestamps for untimed files. A second model call independently reviews the interpretation against the original interview. An unmatched quote, missing review or rejected interpretation cannot be confirmed or enter downstream analysis. These are fallible checks, not an accuracy guarantee.

After the analyst confirms findings, **Compare evidence** groups them by research question and interview. **Coverage** counts confirmed findings; it does not infer agreement. Synthesis and claim checking receive both the brief (context only, never evidence) and the confirmed findings. Each finding carries a brief identifier; the server rejects mismatched or unchecked findings in brief-mode judgement requests. This validates the client payload, not a tamper-proof audit trail: this demo trusts the browser's confirmation state.

The brief locks once an interview has been extracted. **New project** saves the current workspace into a browser-local archive before opening a fresh intake. **Saved in this browser** restores earlier projects. Drafts and completed interviews survive refresh; unprocessed File objects do not. Storage failures are visible and prevent project switching from discarding the current workspace. A cross-tab guard prevents another v3 tab's saved work from being silently overwritten.

Existing `synq.live.v2` workspaces are imported as **Original IT software questionnaire** runs, with the old storage record left intact. New work uses `synq.live.v3`. The legacy questionnaire remains selectable for the original ITSM interviews; it is not the general extraction path. New interviews use the brief attached to their project, so different research questions are never silently mixed within a run.

Brief mode is limited to 60,000 characters per interview and at most two interviews in flight. It makes one extraction call and, when quotes match, one review call per transcript. Review failures remain visible with instructions to re-extract. Confirmation changes or replacement interviews invalidate prior synthesis and claim checks.

## Original questionnaire: provenance and prior evaluation

The sections below describe the original ITSM workflow and its historical evaluation. Those scores do not establish accuracy for the new brief-guided mode.

## Why this exists

**Provenance, up front:** every number and every finding in the submitted site was drafted by Claude from the transcripts and approved by me. Nothing there was hand-extracted. This app does the same work with the machinery exposed — the drafting cites the atoms it rests on, the approval step is an explicit review queue rather than something that happened in my head, and it runs on transcripts nobody has read.

In the 21 Aug round, Bren asked: *"Did you — do you have a backend?"* The honest answer for the submission is no. `build.py` renders `site/index.html` from `facts.json` plus 20 finding rows hardcoded into `build.py` itself. Both were produced the same way: Claude worked through the three transcripts, I reviewed and approved the result, and the approved output was frozen into the repo. `pipeline/extract.py` writes `out/extracted.json` that **nothing reads**; it exists to be scored against that approved set. That is a normal way to produce analysis and I would defend it — but it ran once, by hand, and nobody but me can run it again.

The original questionnaire exposes that same schema and prompt for new uploads. The new project-brief mode uses a separate general extraction schema and review step.

## Original questionnaire back end

Three things that cannot happen in a browser or in a committed HTML file:

1. **Holds the key.** `ANTHROPIC_API_KEY` is a Vercel environment variable read at request time. It never reaches the client. This is the main reason a back end exists at all.
2. **Runs the work.** Six extraction groups fire concurrently against the model on upload. The original timing observation was about 15 seconds for a 12,000-character transcript; it is not a service guarantee.
3. **Checks the citations before the browser sees them.** Every returned quote is normalised and matched character-for-character against the uploaded source. Deterministic, no model, no answer key.

## The honest part

`score.py` has two halves. Citation integrity needs no ground truth, so it survives here and runs live on any transcript. Value agreement is scored against `facts.json` — an approved answer key for three specific transcripts. There is no answer key for a transcript nobody has read, so that half of the check cannot travel.

So that half becomes a **review queue**: every atom shows its source quote, model-supplied timestamp, confidence, and quote-match badge, and a human confirms or rejects it. Rollup tables are computed by arithmetic from confirmed atoms only. An unverified or unconfirmed atom never reaches a table.

**Themes are drafted, under the same discipline.** Extraction cites the transcript and the server checks every quote verbatim. Drafting cites *atoms* and the server checks every atom id against the confirmed set. Only confirmed atoms are ever sent, so an atom the analyst rejected cannot appear in an argument — the human's confirm/reject decisions bound what the model is allowed to say. Each theme carries its supporting atoms, a strength label (one expert / several / whole panel), and a citations-resolve badge. A draft also returns **what this panel does not support**, which is the half analysts skip.

All model stages now use `claude-sonnet-5`: extraction, semantic review, synthesis and claim checking. Brief-mode synthesis uses the regular model call within an 8,000-token output budget; the original questionnaire retains adaptive thinking. Cut-off or incomplete structured synthesis/claim responses return a retryable error instead of a success badge.

A draft leads with a **Summary** — the connected paragraph a client reads before any bullet. Same discipline: every figure in it must appear in a cited atom, the server checks those ids, and the schema requires the last sentence to name the sample size plainly. The prompt forbids opening with background, restating the theme list, or ending on a flourish.

The whole output is a first draft for an analyst to edit, labelled as such, and it sits above a free-text notes box that is still yours.

## Summary — the live form of Slide Check

The submitted site's **Summary** tab graded five representative slide claims against `facts.json`. That needs an answer key. The live version grades *any* claim you type against whatever you confirmed, which works on a transcript nobody has read.

You get a verdict (supported / partially supported / not supported / contradicted), one sentence naming which half of the claim the evidence carries, the atoms bearing on it, the caveats a reader would otherwise assume away, and a **paste-ready footnote** with source references so provenance travels with the finding. Brief-mode findings use line numbers when no timestamp is supplied.

The grading rules are written to refuse, not to please. A claim about "buyers" or "the market" backed by one expert comes back *not supported* however true it sounds. A claim that is directionally right and numerically wrong is *partially supported*, never supported.

## Panel, not one interview at a time

The product is panel synthesis, so the app holds several interviews at once. Drop in the whole panel at once. Files queue with a label derived from each filename (deduped, editable), and extract **two at a time** — each transcript is already six concurrent model calls, so two in flight is twelve, fast without tripping rate limits. Three real transcripts take about 26 seconds wall clock. A failure on one leaves the others loaded, keeps the failed row for a retry, and holds the upload view open rather than hiding the thing you have to act on.

Loaded interviews stack in a bar across the top; the review queue switches between them; and **every downstream view computes across every confirmed atom from every expert**.

- **Rollups** — the ratings grid is criterion x vendor with each cell carrying every expert who scored it, and a `split` marker where they disagree. Divergence is displayed, never averaged. A "rated by 2 of 3" column shows at a glance what is actually comparable.
- **Coverage** — who is in the panel, which vendors are rated versus actually run by someone, which criteria are comparable across all experts versus one only, the matrix fill rate, and a derived list of what the panel *cannot* support. All counting, no judgment.
- **Synthesis and Claim check** — receive the whole panel with every atom id prefixed by its expert. The prompt requires a claim covering all N to have support from all N; two of three is "several experts", never the whole panel.

Verified on the three real ITSM transcripts: 107 confirmed atoms, and the draft correctly labelled seven themes "whole panel" and one "several experts" (the two who discussed Freshservice), while refusing to average a ServiceNow price that was recalled at $100, quoted at $160 and quoted at $150 by the three experts.

## Deliverable — getting the synthesis out

A sixth tab assembles the finished document from what survived review: the panel, the summary, the kept findings each followed by the verbatim quotes behind it, the rollup tables, the coverage limits, and your own notes. **Print / save as PDF** uses a real print stylesheet that drops the app chrome, and **Copy as markdown** puts the whole thing on the clipboard.

Each drafted finding carries a *keep in deliverable* checkbox, because an analyst always cuts. The rollup and coverage tables are generated by the same builders the workspace tabs use, so the document cannot drift from what the app shows.

Every deliverable ends with a provenance paragraph stating how it was made — extracted by model against a fixed schema, every quote checked character-for-character, a human confirming each one, findings drafted from confirmed facts only, nothing averaged. The artifact says how it was made, which is the same standard the citations are held to.

## What it does not do

| Not built | Why | What it would take |
|--------------------------|-------------------------------|------------------------------|
| Multi-user persistence | demo scope | Postgres + auth |
| Cross-device results | results are in localStorage | the same |
| Real accounts | one shared passcode | SSO or magic links |

State lives in the viewer's browser. Clear site data and it's gone. That's a deliberate v1 bound, not an oversight.

## Layout

```
live/
  api/extract.py      HTTP function — gate, decode, extract, verify
  api/_pipeline.py    original schema, synthesis, claim check
  api/_brief.py       brief validation, general extraction, semantic review
  public/index.html   the whole front end, no build step
  pyproject.toml      deps + the Vercel entrypoint declaration
  dev/check_schema.py asserts this schema still matches pipeline/extract.py
  dev/check_brief.py  offline brief/source/review regression checks
  dev/check_workspace.cjs browser-state migration and recovery checks
  dev/local_run.py    runs the original questionnaire locally against a transcript
```

## Running it

```bash
python3 dev/check_schema.py                       # original contract drift guard
python3 dev/check_entry.py
python3 dev/check_brief.py
node dev/check_workspace.cjs
source ~/.config/secrets.env
python3 dev/local_run.py "/path/to/transcript.docx"   # real model calls; incurs cost
# Deployment uses the clean-package instructions below.
```

`GET /api/extract` is a health probe: reports the model, the group list, and whether both environment variables are set — without revealing either.

## Notes

- Model is pinned to `claude-sonnet-5`, matching the run that scored 52/52 on ratings and 11/11 on prices. Changing the model invalidates that number.
- `dev/check_schema.py` exists because the schema is duplicated here so the function can deploy self-contained. Duplication nothing checks is duplication that drifts.
- The passcode is in `PASSCODE.local.txt`, gitignored. A missing `DEMO_PASSCODE` on the server fails closed with a 500, never open.
- One extraction group failing returns empty for that group and reports it in the response rather than losing the other five.

## Demo entry

The browser validates the shared `DEMO_PASSCODE` on entry and refresh by posting `{action: "authenticate", passcode}` to `api/extract.py`, the server entry point. This check makes no model call. A rejected or stale passcode returns to the entry screen without deleting the saved interview workspace. Run `python3 dev/check_entry.py` for the no-model HTTP check.

The Vercel project has `rootDirectory` set to `live`. For CLI deployment, package `live/public/index.html`, `live/api/extract.py`, `live/api/_pipeline.py`, `live/api/_brief.py`, `live/pyproject.toml` and `live/vercel.json` under a clean package root, copy `live/.vercel/project.json` to the package root’s `.vercel/project.json`, and run `vercel deploy --prod --yes --cwd <package-root>`. Do not deploy directly from the `live` directory because the configured root is applied again. This runtime-only package excludes transcripts, local access files and environment files.

Entry update verified on 8 September 2026. Live deployment `dpl_E6zRiHBjU83PZK49mdS6AY1F4G7v` accepted the current passcode, rejected the old passcode, and preserved the existing browser workspace. No new model execution was used for verification.

Brief-intake validation on 8 September 2026: offline API, source, semantic-gate, migration and recovery checks passed. A local browser run on the two fictional Harbor interviews produced 38 candidates, 35 with located source quotes and passed model reviews; three unmatched quotes were held out of confirmation. Synthesis generated eight themes and explicit evidence gaps, and claim checking distinguished the stated sales cycle from unsupported Harbor implementation timing. This is a smoke test, not a measured accuracy benchmark. Desktop and 390px mobile intake, project restoration, comparison and Markdown export were exercised.
