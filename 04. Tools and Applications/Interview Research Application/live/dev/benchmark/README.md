# Harbor provider pilot

Status on September 9, 2026: the local provider adapter and offline benchmark are implemented. Read-only model lookups succeeded for Claude Sonnet 5, GPT-5.6 Terra and GPT-5.6 Sol. No paid generation comparison has run. The answer key is awaiting Stephen's review. Production remains unchanged.

## Protocol

Run each arm once on the canonical fictional Harbor brief and both interviews. Preserve the current Anthropic prompts, model, forced tool choice, token limits and adaptive-thinking settings. Translate the same schemas into OpenAI strict JSON output. OpenAI uses Responses with `store=false`, `none` reasoning for extraction/review/brief synthesis and `medium` for claim checking. These are explicit operational settings, not equivalent internal reasoning budgets. No prompt tuning, hidden retries, hosted tools or automatic provider fallback are part of this first run.

Each arm makes up to 13 calls: two extractions and their two separate reviews, two controlled review-probe batches, one controlled synthesis and six controlled claim checks. A source with no located findings needs no second extraction review. Failed or empty outputs remain visible in the counts.

The draft answer key contains 39 evidence units, exact source spans, nine forbidden finding types, six claim verdicts and six evidence-gap expectations. It was written before new provider outputs. Stephen reviews `GOLD-REVIEW.md`; the exact quotes and machine-readable records are in `gold.json`. Approval saves a hash of the reviewed content, so subsequent edits invalidate approval. Exact source bytes and the brief are also pinned by hash.

Synthesis and claim checks receive the same approved gold evidence in all three arms. This isolates those stages from extraction differences. It does not pretend that generated findings have already been human-confirmed. End-to-end synthesis from each provider's own generated findings requires a later human review of those findings and an additional paid run; the controlled results do not stand in for it.

The controlled review probes have four supported and four unsupported cases across the two interviews. Negative probes retain real quotes but misstate their meaning, attribution or scope. A duplicated or missing review index receives no credit.

## Assumptions ledger

| Decision    | Default          | Check                 |
|-------------|------------------|-----------------------|
| Public site | Claude           | Deployment approval   |
| Sample      | Two interviews   | Pilot-only conclusion |
| Repetition  | One run per arm  | Later held-out tests  |
| Reasoning   | Match stage role | Record each request   |
| Downstream  | Fixed gold       | Human approval hash   |
| Spending    | $3 guard         | Per-call ledger       |
| Judgments   | Human, blinded   | No guessed scores     |

These defaults come from the handoff's controlled-pilot scope and the existing stage settings. If one run is too variable, add repetitions only after reviewing this run's results and costs. If the business question requires performance on generated evidence, complete the additional human-confirmed workflow rather than generalizing from controlled stage tests.

## Costs

Official list rates checked on September 9, 2026, in dollars per million tokens:

| Model    | Input | Cached input | Output |
|----------|-------|--------------|--------|
| Sonnet 5 | $2    | $0.20        | $10    |
| Terra    | $2    | $0.20        | $12    |
| Sol      | $4    | $0.40        | $20    |

[Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing) confirms that Sonnet 5's earlier introductory price is now its standard price. [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) and [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) rates therefore do not establish an automatic OpenAI cost saving.

The planning estimate is $1.192 for all three arms, assuming 65,000 input and 16,000 output tokens per arm. It is an assumption, not a measured result or billing quote. The default $3 guard reserves a conservative next-call amount from request byte length plus token overhead and the full output allowance before dispatch. Calls are sequential, with SDK retries disabled. Uncertain billing halts further calls. No provider returns an invoice amount in a generation response; reported actual-run dollars are calculated from provider-reported token usage and the saved list prices.

Normalized input tokens include cached and cache-created tokens; output tokens already include reasoning. The estimator does not charge reasoning twice. Anthropic does not report reasoning tokens separately in this interface, so that field remains unknown. Raw usage is preserved for audit. No new Anthropic prompt-cache writes are requested by this pilot.

## Commands

Run from the `live` directory. `.venv-pilot` is ignored by Git and contains the pinned OpenAI and Anthropic SDKs plus JSON Schema validation. Provider keys are loaded safely from `~/.config/secrets.env` and, if present, `.env.local`. The pilot key is centralized in the shared secrets file as `INTERVIEW_OPENAI_API_KEY`; it takes precedence over the existing general-purpose `OPENAI_API_KEY`. No credentials appear in reports.

```bash
.venv-pilot/bin/python dev/benchmark/run.py validate
.venv-pilot/bin/python dev/benchmark/run.py estimate
.venv-pilot/bin/python dev/benchmark/run.py preflight
```

`preflight` performs model-availability lookups, not generation. Only after Stephen has actually reviewed and approved the answer key:

```bash
.venv-pilot/bin/python dev/benchmark/run.py approve-gold --reviewer Stephen
.venv-pilot/bin/python dev/benchmark/run.py run \
  --output dev/benchmark/runs/harbor-pilot-01 --max-cost-usd 3
.venv-pilot/bin/python dev/benchmark/report.py dev/benchmark/runs/harbor-pilot-01
```

The `approve-gold` command records a real human review; it must never be used to manufacture approval. The `run` command checks that approval before loading credentials or creating a run directory.

## Stopping, retrying and returning

Each stage saves its status and result immediately. `calls.jsonl` records dispatch before the request and completion afterward, with usage and raw outputs even when structured parsing fails. Successful tasks are skipped by `--resume`. Do not delete a partial run to reset its accounting.

```bash
.venv-pilot/bin/python dev/benchmark/run.py run \
  --output dev/benchmark/runs/harbor-pilot-01 --max-cost-usd 3 --resume
```

An unfinished or failed task requires inspection and explicit `--resume --retry-failed`; this preserves its previous result in `history/` and counts all previous billed calls. A transport interruption or a dispatched call without a completion record has uncertain billing, so the runner refuses automatic resume even with that flag. Reconcile that call with the provider dashboard before deciding on a new paid run. A cut-off structured response with recorded usage remains a measured failure; it is not silently repaired or removed from the comparison.

No generated finding is automatically confirmed. A model-passed finding is merely eligible for a human decision. Review failures or unmatched quotes stay ineligible in both the HTTP app and the benchmark.

## Blinding and scoring

`manifest.json` stores randomized arm order, provider mapping, exact model IDs, prompt/schema/code hashes, SDK versions, prices and timestamps. It and `calls.jsonl` contain provider names. `gold.json` and `sources.json` preserve the frozen review inputs. Keep those provider metadata files closed while doing subjective review.

Give the reviewer `BLINDED-REVIEW.md` and `human-review.json`. Assign each candidate a support judgment and the gold evidence units it covers; combining or splitting findings does not earn duplicate recall credit. Source scope must match the expert. Review synthesis wording and evidence gaps separately. Set reviewer name and completion status only when the review is actually complete, then regenerate the report. Missing judgments remain null, never zero or automatically correct.

`COMPARISON.md` shows anonymous arms. `metrics.json` separates raw and eligible finding recall, finding precision, unsupported-finding rate, actual review accuracy, controlled review accuracy, claim verdicts, citation-ID validity, semantic synthesis judgments, evidence gaps, failures, usage, cost and latency. Quote matching and valid citation IDs do not prove that a conclusion is supported. A fluent summary does not make up for missing evidence.

The initial decision remains pending until those judgments exist. Two fictional interviews and one run per model can reveal obvious defects and the cost of this workload. They cannot establish general provider superiority or justify changing production by themselves.

## Verification

```bash
.venv-pilot/bin/python dev/check_providers.py
.venv-pilot/bin/python dev/check_benchmark.py
.venv-pilot/bin/python dev/check_brief.py
.venv-pilot/bin/python dev/check_entry.py
.venv-pilot/bin/python dev/check_schema.py
.venv-pilot/bin/python dev/sync_harbor.py --check
node dev/check_workspace.cjs
```

The provider checks cover unchanged Anthropic requests, OpenAI request fields, storage disabled, schema conversion, optional fields, refusal/truncation/malformed-output failures, quote location, review failure and duplicate-index gates, token normalization, server allowlists and citation checks. The benchmark checks run all 39 calls through offline fake SDKs, test the approval hash and money guard, block uncertain-billing resume, verify completed calls are not repeated, and keep unreviewed semantic metrics unknown. No paid test output is implied by those fixtures.
