# Handoff: OpenAI Provider Pilot for Interview Extraction

Date: September 9, 2026

## Next-chat prompt

Continue the OpenAI provider pilot and Claude-versus-OpenAI benchmark described in this handoff. Work only on the Interview Extraction application. Do not modify the Credit Waiver Agent. Begin by reading this document, `/Users/stephenlese/AGENTS.md`, the repository `README.md`, and the applicable OpenAI API-key and official-documentation skills. Preserve all existing work and inspect the current branch before editing.

## User's objective

Stephen wants to explore moving the Interview Extraction application from the Anthropic API to the OpenAI API and determine whether an OpenAI model is accurate enough for the task.

The immediate objective is not to replace Claude blindly. It is to:

1. Preserve the existing Interview Extraction workflow.
2. Add OpenAI as a second model provider.
3. Run identical fictional Harbor inputs through Claude, GPT-5.6 Terra, and preferably GPT-5.6 Sol.
4. Compare extraction and claim-checking quality, source fidelity, cost, and latency.
5. Change the production/public provider only if the evidence supports doing so.

Leave the Credit Waiver Agent unchanged. It is more deeply coupled to Anthropic and is explicitly out of scope.

## Plain-language terminology

Stephen was understandably concerned by the phrase "use the Responses API rather than the Codex coding agent." Explain it this way:

- The **Responses API is the phone line** the application uses to reach OpenAI.
- **Terra or Sol is the model that answers the phone** and performs the reasoning.
- **Codex is a software-development agent** that combines an OpenAI model with a terminal, filesystem access, and coding tools so it can build and edit software.

The Interview Extraction application needs an OpenAI model through the OpenAI Responses API. It does not need to embed the complete Codex coding environment. In casual conversation Stephen may call this "switching to Codex," but the accurate product description is "adding an OpenAI model provider" or "using the OpenAI API."

Concrete flow:

```text
Current:
Browser -> Python backend -> Anthropic API -> Claude -> deterministic checks -> browser

Pilot:
Browser -> Python backend -> provider adapter -> Claude or OpenAI model
                                      -> deterministic checks -> browser
```

The application, source files, schemas, quote verification, human confirmation, synthesis rules, and user interface should remain substantially the same.

## Model recommendation

Do not assume Terra is good enough. Test it.

Recommended first pilot:

- **Claude Sonnet 5:** current control.
- **GPT-5.6 Terra:** economical OpenAI candidate.
- **GPT-5.6 Sol:** stronger OpenAI candidate that helps distinguish a provider limitation from a model-tier limitation.

Suggested decision rule:

- Choose Terra if it has no material regression in unsupported-claim rate, quote accuracy, extraction coverage, or claim-check verdicts and offers a meaningful cost or latency benefit.
- Choose Sol if Terra misses important evidence but Sol matches or exceeds Claude.
- Keep Claude if neither OpenAI candidate meets the quality bar.
- A mixed-provider design is acceptable if one provider is materially better at a particular stage.

Current official OpenAI documentation reviewed on September 9, 2026 says Terra and Sol both support the Responses API, function calling, structured outputs, and reasoning controls. Current listed text-token prices were $2 input / $12 output per million tokens for Terra and $4 / $20 for Sol. Recheck current official documentation before implementing because pricing and model availability can change.

Official references:

- https://developers.openai.com/api/docs/models/gpt-5.6-terra
- https://developers.openai.com/api/docs/models/gpt-5.6-sol
- https://developers.openai.com/api/reference/cli/resources/responses/methods/create

## Exact project and repository state

Project root:

```text
/Users/stephenlese/dev/AI Projects/projects/career/companies/interviews/synquery/Case Study/prototype/live
```

Git state at handoff creation:

```text
Branch: codex/interview-project-brief
Tracking: origin/codex/interview-project-brief
Status: ahead by 2 commits
```

Recent local commits:

```text
d1595bb Align interview demo with portfolio workflow
9bccad6 Clarify interview demo setup flow
7ce0df3 Start portfolio visitors at Harbor intake (remote branch tip at inspection time)
```

The two local commits must be preserved. Inspect current disk and Git state again because it may have changed after this handoff was written.

No OpenAI migration code was written in this conversation. No API key was created or saved. No paid comparison call was made.

## Current application behavior

The public application uses a controlled fictional Harbor scenario:

- One fictional Harbor project brief.
- David Okafor interview, Operations.
- Maria Castellanos interview, Sales.
- Visitors deliberately load the brief and select one or both interviews.
- Extraction makes live model calls.
- Arbitrary uploads and modified briefs are rejected.

The fixed inputs are helpful for a reproducible provider comparison, but two interviews are only enough for an initial smoke test. They are not enough to support a broad claim that one provider is generally more accurate.

Current model and dependency:

```text
Model: claude-sonnet-5
Python dependency: anthropic==0.108.0
```

Primary files:

- `api/extract.py` constructs the Anthropic client and routes extraction, synthesis, and claim checks.
- `api/_brief.py` performs Harbor finding extraction and a separate model review.
- `api/_pipeline.py` contains the structured extraction, synthesis, and claim-check calls.
- `api/_harbor.py` is the server-side source of truth for the fictional Harbor brief and transcripts.
- `README.md` documents the workflow, validation, deployment, and existing smoke-test evidence.

The current pipeline uses Anthropic-specific forced tool calls to obtain structured payloads such as `emit_findings`, `review_findings`, `emit_themes`, and `emit_verdict`. Some stages use Anthropic adaptive thinking.

Important existing controls to preserve:

- Exact source bytes are selected on the server.
- Returned quotes are normalized and matched against the source deterministically.
- Unmatched quotes are withheld from human confirmation.
- Humans confirm or reject extracted findings.
- Synthesis only receives confirmed findings.
- Theme citations are checked against the confirmed finding set.
- Incomplete structured responses fail rather than appearing successful.

## Credential status and blocker

Safe checks found no usable `OPENAI_API_KEY` in:

- The current process environment.
- The project's `.env.local` file.

The same checks did not find an Anthropic key in those two locations. The deployed Vercel project may still have its own server-side Anthropic secret; this was not inspected during the handoff turn.

The secure OpenAI Platform target-selection panel was opened twice but returned no completed selection. A fallback local-destination confirmation for `.env.local` was then canceled or not approved. Therefore:

- No OpenAI key was created.
- No secret was written.
- No plaintext credential was exposed.

The next chat should restart the secure OpenAI API-key setup flow. Do not request that Stephen paste a plaintext key into chat, and never print `.env` contents.

The user approved creating an OpenAI key and wants a small paid comparison. Keep the first run small and report estimated/actual cost before expanding the benchmark.

## Recommended implementation

Do not replace Anthropic calls directly. The comparison requires both providers to remain available.

Create a narrow provider interface that normalizes only what this application needs, for example:

```text
generate_structured(
    provider,
    model,
    instructions,
    input,
    schema,
    reasoning_effort,
) -> normalized payload + normalized usage
```

Then:

1. Wrap the existing Anthropic calls behind the interface without changing current behavior.
2. Add an OpenAI implementation using `responses.create` and structured JSON output or function calling.
3. Set OpenAI response storage deliberately. For this controlled demo, prefer `store: false`; revisit retention and contractual controls before real client documents are used.
4. Normalize usage into input tokens, cached-input tokens where available, output/reasoning tokens, elapsed time, provider, and model.
5. Keep provider/model selection server-side. Do not expose API keys or arbitrary model access in the browser.
6. Keep the public site on the existing provider until the pilot is verified.

Likely compatibility work:

- Anthropic system prompts become OpenAI `instructions`.
- Anthropic `messages.create` calls become OpenAI `responses.create` calls.
- Forced Anthropic tool payloads become OpenAI Structured Outputs or forced function calls.
- Anthropic tool-use parsing becomes OpenAI response-output parsing.
- Adaptive thinking becomes an explicit OpenAI reasoning-effort setting.
- Usage, exceptions, rate limits, retries, and output-limit handling need provider-specific adapters.

Do not rewrite the prompts aggressively during the first comparison. First keep task instructions and output schemas as equivalent as the provider formats allow. Otherwise the test will compare two different application designs rather than two model providers.

## Benchmark design

### First pilot

Use the same Harbor brief and both Harbor transcripts for all three arms:

```text
Arm A: current Claude Sonnet 5 pipeline
Arm B: GPT-5.6 Terra with equivalent prompts and schemas
Arm C: GPT-5.6 Sol with equivalent prompts and schemas
```

Record model identifiers, parameters, prompt versions, timestamps, latency, and usage. Save raw outputs in provider-labeled artifacts without changing the public demo.

### Establish the answer key before judging outputs

Create a human-reviewed gold set from the fictional sources before looking at provider names. At minimum, label:

- Expected factual findings.
- The exact supporting quote or source span for each finding.
- Findings that must not be made because the source does not support them.
- Expected supported/unsupported verdicts for selected test claims.
- Evidence gaps the synthesis should acknowledge.

If the gold set is created after seeing outputs, it can accidentally favor whichever answer sounded more persuasive.

### Metrics

Score the following separately:

1. **Finding precision:** Of the findings produced, how many are supported?
2. **Finding recall:** Of the gold findings, how many were found?
3. **Exact quote location:** Did the quote appear in the source? This remains deterministic.
4. **Unsupported-claim rate:** How often did the model add a conclusion the source could not justify?
5. **Review quality:** Did the second model review accept supported findings and reject unsupported ones?
6. **Claim-check accuracy:** Did supported and unsupported test claims receive the correct verdict?
7. **Synthesis grounding:** Did themes cite valid confirmed findings and avoid rejected ones?
8. **Evidence-gap quality:** Did the model identify what the panel could not establish?
9. **Completeness and failure rate:** Were structured outputs complete, valid, and usable?
10. **Latency and cost:** Wall-clock time and provider-reported usage/cost per interview and full workflow.

Do not collapse all of these into one subjective "best answer" score. A fluent synthesis can conceal missed evidence or unsupported claims.

### Blinding

Where human judgment is required, hide provider and model labels. Randomize answer order. Use deterministic checks for exact quote matching and schema completeness. Human review should focus on whether findings and conclusions are supported, not whether the prose sounds polished.

### Claims allowed after the pilot

Two fictional interviews and one run per provider can support a statement such as:

> "In an initial controlled Harbor pilot, we compared Claude, GPT-5.6 Terra, and GPT-5.6 Sol on identical fictional inputs and measured grounding, coverage, cost, and latency."

It cannot support:

> "OpenAI is generally more accurate than Claude" or "the system consistently beats Claude."

A stronger claim requires more held-out interviews, repeated runs where nondeterminism matters, and independently reviewed answer keys.

## Suggested order for the next chat

1. Read this handoff and recheck Git status.
2. Complete secure `OPENAI_API_KEY` setup.
3. Confirm how the existing Claude test calls will obtain credentials without exposing secrets.
4. Create the human-reviewed Harbor gold set before examining new provider outputs.
5. Add the minimal provider interface and preserve current Anthropic behavior.
6. Implement Terra and Sol through the OpenAI Responses API.
7. Run offline tests and structural checks.
8. Estimate the three-arm pilot cost and keep it small.
9. Run identical inputs through all three arms.
10. Produce a provider-blinded comparison table and a candid conclusion.
11. Do not alter or deploy the public demo until Stephen reviews the evidence and explicitly approves deployment.

## Product and communication constraints

- Explain technical decisions in plain language with one concrete workflow example.
- Do not call the production integration a "Codex API" without clarifying that it is the OpenAI API and an OpenAI model.
- Do not claim superiority before the benchmark supports it.
- Do not expose API keys, transcript secrets, or `.env` contents.
- Do not touch the Credit Waiver Agent.
- Preserve current local commits and unrelated work.
- Stop before deployment or any other outward-facing change unless Stephen explicitly approves it.
