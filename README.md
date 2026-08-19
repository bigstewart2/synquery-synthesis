# Synquery Panel Synthesis (prototype)

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
- **Banned-term scan** — a redaction map built from the facts file (never hardcoded) is checked against the rendered output and against every `.py`/`.md`/`.html`/`.json`/`.gitignore` file in the repo.
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
