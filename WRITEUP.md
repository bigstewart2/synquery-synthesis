# Writeup

## Thesis

The interview guide is already a schema. The agent asks typed questions — ranked criteria, 1-10 ratings per vendor per criterion, per-user prices, percentages, satisfaction scores on a stated scale — so synthesis is typed extraction against that schema, with every piece of arithmetic done deterministically afterward and every number traceable to a quoted span and a timestamp. The client's actual job is to put a claim on a slide and defend it in a partner meeting, so the product's job is to say, for each claim, what this panel actually allows them to claim.

## Architecture

AI does the work that requires reading comprehension: locating and typing the atoms in a transcript (a rating, a price, a ranked criterion, a quote that supports a takeaway), and drafting the takeaway prose that sits next to each finding. Everything downstream of that is deterministic and lives in code, not in a model call: every count, every mean, every ratio, the consensus-vs-contested marker on each rating cell, the comparable-vs-not-comparable status of each criterion, scale-mismatch detection, citation link validation, redaction, and the banned-term scan that gates the build. What's stored is atoms — an extracted quote plus a timestamp — and a hand-verified facts file that acts as ground truth for this prototype. What's computed at read time or build time is every aggregate, every evidentiary tag, and every Slide Check verdict; none of that is hand-typed into the render code. A prior scored extraction run against this same panel came back at 52 of 52 vendor ratings matched, 11 of 11 prices matched, 106 of 106 quotes verbatim against the source transcripts, and zero hallucinated atoms — the schema-first approach held up against ground truth.

## Data-quality findings as requirements on the synthesis layer

None of the following are a grade on the interviewer; each is a requirement the synthesis layer needs to meet, with a cheap fix. A scale mismatch — the agent asks on a 1-7 scale and the expert answers 9 out of 10, and the interview moves on — needs a units validator that quarantines that row from every aggregate rather than averaging it in. Bare acquiescence to a fed hypothesis — the agent supplies a conclusion and the expert only agrees, with nothing added — needs an evidentiary tag that weights confirmed-on-prompt below a volunteered answer, with a middle state for a fed hypothesis the expert confirmed and then added first-hand specifics to. A price basis mismatch — one price paid, one price quoted but never paid, one price set as an illustrative comparison anchor — needs a typed basis field on every price so unlike bases never get averaged together. A redaction inconsistency — the header is anonymized but the body names the employer, and the employer even appears under two different spellings in the same transcript — needs entity resolution at ingest into a single redaction map, not per-string patching. Non-standard criteria per expert, where only two of eight rated criteria were asked of the full panel, is a fix at interview design, not at synthesis: standardize the criteria at setup and the comparison grid fills itself. ASR and agent artifacts — a duplicated wrap-up close, a mis-heard acronym corrected mid-turn — need a transcript QC pass before extraction runs, so the extractor is never asked to make sense of a known glitch.

## Roadmap

1. **Human review queue before client delivery.** Nothing in this prototype should reach a client without a human reading every takeaway and every computed verdict first; the build's checks catch structural failures, not judgment calls.
2. **Client question in, output structure proposed.** Right now the output shape (five tabs plus Slide Check) is fixed by hand. The next step is proposing that structure from the client's actual question, so a different workstream doesn't need a rebuild.
3. **Export where the client works.** A static HTML page is a good prototype surface, not a good delivery surface; the real destination is wherever the client already reads decks and docs.
4. **Interview guide derived from the goal.** Once the output structure is proposed from the question, the interview guide itself should be derived from the same goal, closing the loop between what's asked and what's synthesized.
5. **Archetype library and cross-project corpus.** As more panels run through this pipeline, the extracted atoms and the evidentiary patterns become a corpus worth mining across projects, not just within one.

## Where an engineer is wanted before this carries load

Schema generation from an arbitrary interview guide (rather than a hand-written one per project), an extraction eval harness that runs at volume instead of one hand-scored panel, entity resolution for redaction that generalizes past a small hand-built map, multi-tenant storage and permissions once more than one client's data lives in the same system, and the review-queue workflow itself — routing, sign-off, and versioning once a human is in the loop on every delivery.

## Deliberately left out

No free-text claim checker in Slide Check — a fixed set of five claims keeps every verdict deterministic and honest at a panel of three; an open input box would invite verdicts this panel cannot actually support. Separately: the Slide Check tab completes the layer that a prior draft's Answer tab had marked parked, rather than sitting beside it as a second, competing thing — that tab's own text said the work was on hold pending a call, and the call was to build this instead.
