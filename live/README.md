# Live extraction (the back end the submission doesn't have)

**Live:** https://synquery-live.vercel.app (passcode-gated)
**Sibling:** https://synquery-synthesis.vercel.app — the submitted static prototype, unchanged.

## Why this exists

In the 21 Aug round, Bren asked: *"Did you — do you have a backend?"* The honest answer for the submission is no. `build.py` renders `site/index.html` from a `facts.json` built during the take-home, plus 20 finding rows hardcoded into `build.py` itself — drafted with Claude from the transcripts and approved before they were pasted in. `pipeline/extract.py` writes `out/extracted.json` that **nothing reads**; it exists to be scored against the answer key. That's a defensible take-home choice, and it is not a system anyone but me can run.

This is that system. Same schema, same prompt, same model. What changes is that a stranger can now use it.

## What the back end actually does

Three things that cannot happen in a browser or in a committed HTML file:

1. **Holds the key.** `ANTHROPIC_API_KEY` is a Vercel environment variable read at request time. It never reaches the client. This is the main reason a back end exists at all.
2. **Runs the work.** Six extraction groups fire concurrently against the model on upload. About 15 seconds for a 12,000-character transcript.
3. **Checks the citations before the browser sees them.** Every returned quote is normalised and matched character-for-character against the uploaded source. Deterministic, no model, no answer key.

## The honest part

`score.py` has two halves. Citation integrity needs no ground truth, so it survives here and runs live on any transcript. Value agreement is scored against `facts.json`, which exists only because those three transcripts were gone through and verified during the take-home. There is no answer key for a transcript nobody has read.

So that half becomes a **review queue**: every atom shows its verbatim quote, timestamp, confidence, and a verified badge, and a human confirms or rejects it. Rollup tables are computed by arithmetic from confirmed atoms only. An unverified or unconfirmed atom never reaches a table.

**Themes are drafted, under the same discipline.** Extraction cites the transcript and the server checks every quote verbatim. Drafting cites *atoms* and the server checks every atom id against the confirmed set. Only confirmed atoms are ever sent, so an atom the analyst rejected cannot appear in an argument — the human's confirm/reject decisions bound what the model is allowed to say. Each theme carries its supporting atoms, a strength label (one expert / several / whole panel), and a citations-resolve badge. A draft also returns **what this panel does not support**, which is the half analysts skip.

Drafting runs on `claude-opus-5` rather than the pinned `claude-sonnet-5`, because it has no scoring parity to preserve and the work is judgment-heavy.

A draft leads with a **Summary** — the connected paragraph a client reads before any bullet. Same discipline: every figure in it must appear in a cited atom, the server checks those ids, and the schema requires the last sentence to name the sample size plainly. The prompt forbids opening with background, restating the theme list, or ending on a flourish.

The whole output is a first draft for an analyst to edit, labelled as such, and it sits above a free-text notes box that is still yours.

## Summary — the live form of Slide Check

The submitted site's **Summary** tab graded five representative slide claims against `facts.json`. That needs an answer key. The live version grades *any* claim you type against whatever you confirmed, which works on a transcript nobody has read.

You get a verdict (supported / partially supported / not supported / contradicted), one sentence naming which half of the claim the evidence carries, the atoms bearing on it, the caveats a reader would otherwise assume away, and a **paste-ready footnote** with figures and timestamps so provenance travels with the number.

The grading rules are written to refuse, not to please. A claim about "buyers" or "the market" backed by one expert comes back *not supported* however true it sounds. A claim that is directionally right and numerically wrong is *partially supported*, never supported.

## Panel, not one interview at a time

The product is panel synthesis, so the app holds several interviews at once. Transcripts load one after another and stack in a bar across the top; the review queue switches between them; and **every downstream view computes across every confirmed atom from every expert**.

- **Rollups** — the ratings grid is criterion x vendor with each cell carrying every expert who scored it, and a `split` marker where they disagree. Divergence is displayed, never averaged. A "rated by 2 of 3" column shows at a glance what is actually comparable.
- **Coverage** — who is in the panel, which vendors are rated versus actually run by someone, which criteria are comparable across all experts versus one only, the matrix fill rate, and a derived list of what the panel *cannot* support. All counting, no judgment.
- **Synthesis and Claim check** — receive the whole panel with every atom id prefixed by its expert. The prompt requires a claim covering all N to have support from all N; two of three is "several experts", never the whole panel.

Verified on the three real ITSM transcripts: 107 confirmed atoms, and the draft correctly labelled seven themes "whole panel" and one "several experts" (the two who discussed Freshservice), while refusing to average a ServiceNow price that was recalled at $100, quoted at $160 and quoted at $150 by the three experts.

## What it does not do

| Not built | Why | What it would take |
|--------------------------|-------------------------------|------------------------------|
| Multi-user persistence | demo scope | Postgres + auth |
| Cross-device results | results are in localStorage | the same |
| Real accounts | one shared passcode | SSO or magic links |
| Multiple workstreams | one panel at a time | a project model |

State lives in the viewer's browser. Clear site data and it's gone. That's a deliberate v1 bound, not an oversight.

## Layout

```
live/
  api/extract.py      HTTP function — gate, decode, extract, verify
  api/_pipeline.py    schema, prompt, citation check
  public/index.html   the whole front end, no build step
  pyproject.toml      deps + the Vercel entrypoint declaration
  dev/check_schema.py asserts this schema still matches pipeline/extract.py
  dev/local_run.py    runs the real code path locally against a transcript
```

## Running it

```bash
python3 dev/check_schema.py                       # contract drift guard
source ~/.config/secrets.env
python3 dev/local_run.py "/path/to/transcript.docx"   # real end-to-end, ~$0.30
vercel deploy --prod
```

`GET /api/extract` is a health probe: reports the model, the group list, and whether both environment variables are set — without revealing either.

## Notes

- Model is pinned to `claude-sonnet-5`, matching the run that scored 52/52 on ratings and 11/11 on prices. Changing the model invalidates that number.
- `dev/check_schema.py` exists because the schema is duplicated here so the function can deploy self-contained. Duplication nothing checks is duplication that drifts.
- The passcode is in `PASSCODE.local.txt`, gitignored. A missing `DEMO_PASSCODE` on the server fails closed with a 500, never open.
- One extraction group failing returns empty for that group and reports it in the response rather than losing the other five.
