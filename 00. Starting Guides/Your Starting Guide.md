# Synquery Panel Synthesis (prototype)

## Current location — October 27, 2026

This guide is the maintained original after the approved interior filing. The complete software is in `04. Tools and Applications/Interview Research Application/`; its submitted static site and continuing `live/` application remain distinct. Run the commands below from `/Users/stephenlese/dev/AI Projects/workspaces/01. Business/Other Demos and Prototypes/Synquery — Interview Research and Claim Checking Demo/04. Tools and Applications/Interview Research Application`. Earlier path/hosting observations are dated history. Existing local settings, saved demo state, hosted URLs and provider defaults are preserved; this filing does not deploy, run paid models or resume the provider benchmark.

Open [the application bundle](../04.%20Tools%20and%20Applications/Interview%20Research%20Application/), [the other starting guide](Live%20Application%20Guide.md) or [the source case](../../../../02.%20Career/Recruiting/03.%20Work%20and%20Outputs/Opportunities/synquery/Case%20Study/HANDOFF.md). The unfinished provider/benchmark files remain pending with their existing handoff in the application. Former local paths are compatibility links to these same originals.

**October 22, 2026 — preserved application home:** this complete repository moved to workspaces/01. Business/Other Demos and Prototypes/Synquery — Interview Research and Claim Checking Demo. The submitted static site/ and continuing live/ application remain distinct, with their history, saved configuration and existing unfinished work intact. [Original case inputs and submission records](../../../../02.%20Career/Recruiting/03.%20Work%20and%20Outputs/Opportunities/synquery/Case%20Study/HANDOFF.md) remain in Recruiting; source-input paths read those originals. Existing hosted addresses, storage keys and credentials are unchanged. This move performs no rebuild, deployment or model test.

## What this is

A client-facing synthesis prototype built over three AI-led expert interview transcripts from a Synquery ITSM buying-decision workstream. It renders as a single static HTML page with five tabs — Themes & Quotes, Ratings & Numbers, Transcripts, Coverage, and Slide Check — plus a defensibility layer on top: the Slide Check tab takes five representative slide claims and computes, from the underlying facts, exactly what verdict the panel can support for each one, with the atoms and a paste-ready footnote behind it.

## Confidentiality

The raw transcripts and the hand-verified ground-truth facts file are deliberately excluded from this repo; the build reads them from a local case folder by absolute path. The committed site embeds redacted content only — names and employers are replaced at build time and the build fails if any slips through.

## How to build

Requires Python 3, standard library only, no dependencies to install.

```
python3 build.py
```

This writes `site/index.html`. Before it writes anything, the build runs and prints four checks, and fails loudly (nonzero exit, no output written) if any of them do not pass:

- **Citation resolution** — every clickable quote and score links to a real turn in a real transcript; a broken link fails the build.
- **Banned-term scan** — a redaction map built from the facts file (never hardcoded) is checked against the rendered output and against maintained `.py`/`.md`/`.html`/`.json`/`.gitignore` files across the application, guides and original submission. Generated environments, caches, Git metadata and compatibility-link duplicates are excluded.
- **Exact counts** — findings rows, rendered rating scores, and Slide Check claims/verdicts are each checked against the facts file, not eyeballed.
- **Evidentiary-tag coverage and verbatim-quote precondition** — all three evidentiary states (volunteered, confirmed-on-prompt, confirmed-and-elaborated) must actually render, and every price quote in the facts file must appear verbatim in the output.

## How to run extraction and scoring

The pipeline scripts under `pipeline/` are optional — the committed `site/index.html` was built from the hand-verified facts file, not from a live extraction run. To run the extraction pipeline yourself:

- Requires `ANTHROPIC_API_KEY` set in the environment.
- `python3 pipeline/extract.py` calls the Anthropic API with `claude-sonnet-5` and writes `out/extracted.json` (gitignored).
- `python3 pipeline/score.py` is offline and checks citation integrity (does every quote actually appear in the source transcript) plus value agreement against the hand-verified ground-truth facts file.

## Repo layout

```
build.py            builds site/index.html from the facts file and transcripts
template.html        the static HTML/CSS/JS shell, filled in at build time
pipeline/
  extract.py          schema-first extraction over the transcripts (needs API key)
  score.py            offline scoring of extracted.json against facts.json
site/
  index.html          the built, committed prototype
```
