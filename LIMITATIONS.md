# Tripwire — Known Limitations (measured)

This page lists what Tripwire v2 **cannot** do or does badly, with numbers measured on 2026-11-25.
Every number comes from a script in [`backend/bench/`](backend/bench) or from the Gemini API's own error
responses, so it can be re-checked.

| Script | Needs | What it measures |
|---|---|---|
| `python -m bench.bench_concurrency` | nothing (simulated latency) | v1 vs v2 throughput, API freeze, LLM calls saved |
| `python -m bench.probe_detectors` | nothing | where the rule-based detectors break |
| `python -m bench.bench_live` | `GEMINI_API_KEY` (~40–60 calls) | real latency, quota errors, judge vs heuristic |

Run them from `backend/` (prefix the first two with `MOCK_LLM=1`).

---

## Numbers at a glance

| Area | Measured | Why it matters |
|---|---|---|
| Free-tier Gemini quota | **5 requests/min, 20 requests/day** per model (`gemini-3.6-flash`) | One run takes ~4 calls, so a free key supports **~4–5 scenario runs per day** |
| Live run under the quota | **7 of 8 runs failed with HTTP 429** even after retries (46 retries, 81 requests) | Concurrency 4 is guaranteed to hit the 5/min limit |
| Slowest single Gemini call | **96.9 s** (p50 0.16 s, p95 4.5 s, n=81) | A run's wall time has a very long tail |
| Old (v1) server freeze during a batch | **19.2 s** (whole batch) → **0.02 s** in v2 | v1 could not answer any request while tests ran |
| Throughput v1 → v2 (simulated 0.4 s/call, 12 scenarios) | **19.2 s → 4.9 s (3.9×)**; guardrails **5.7 s → 0.4 s (14×)** | Speed-up is capped by `MAX_CONCURRENT_RUNS=4` and, live, by the quota |
| LLM calls saved by the classifier fast path | **48 → 39 (−19%)** on a mixed workload | Passing runs still cost one extra classifier call each |
| Refusal heuristic on 14 tricky responses | v1 **7/14** → v2 **11/14** correct | Keyword matching still misses refusals without keywords |
| Hallucinated-success detector on 6 tricky answers | **3/6** correct | Misses success claims phrased without keywords |
| Tool-call parser on 6 output styles | **3/6** handled | Only the `TOOL_CALL: name \| {json}` text format works |
| Pass-rate uncertainty, 10 runs at 80% | 95% CI **49%–94%**; one flipped run moves the score **7 points** | Small suites can't tell a good agent from a mediocre one |
| Runs needed for ±5 points of pass-rate precision | **~246 runs** (≈ 1,000 calls, ≈ 3.3 h at 5 req/min, ≈ 50 days at 20 req/day) | Statistically solid results are out of reach on the free tier |

---

## 1. LLM quota and cost

**Measured.** The live benchmark (`bench_live`, 4 scenarios × 2 trials + 16 guardrail probes, concurrency 4):

- Scenario generation: 4 scenarios in 17.8 s (1 call).
- Runs: 8 runs, **1 passed, 7 errored** with `429 RESOURCE_EXHAUSTED` after retries; the one that finished took 104.7 s.
- Guardrails: 16 probes in 40.9 s, **5 errored**. The batched LLM judge call was itself rate-limited, so every
  verdict fell back to the keyword heuristic.
- Totals: 81 requests, 46 retries, 13 operations failed.
- Google's error message confirms the quotas: `generate_content_free_tier_requests`, **limit 5 per minute** and,
  after that run, **limit 20 per day**. The daily reset was 19 hours away. Quotas are counted **per model**.

**Consequences.**
- The default UI flow (generate 6 scenarios, then run them once) needs ~25 calls, more than a free key's whole day.
- `LLM_MAX_CONCURRENCY=6` / `MAX_CONCURRENT_RUNS=4` exceed the per-minute limit by design. There is no
  requests-per-minute limiter, only a concurrency cap.
- The retry backoff (1 s, 2 s, 4 s + jitter) ignores the `RetryInfo` delay Google sends back (e.g. "retry in 7.9 s").
- The public demo shares one key, so a handful of visitors can exhaust the day's quota for everyone.

**Mitigations available today.** `MOCK_LLM=1` (offline), a paid Gemini key, or `GEMINI_FALLBACK_MODEL` set to a
different model (quotas are per model, so the fallback has its own allowance).

## 2. Errors are scored as agent failures

**Measured in code and in the live run.** A run that dies on a rate limit is stored as `UNKNOWN`, `passed=False`,
and counts against the pass rate. A guardrail probe that errors counts as "not refused". In the live run, that
would have reported a **12.5% pass rate (1/8)** and a **69% guardrail rate (11/16)**, although no agent failure
was actually observed: every one of the 11 answered probes was a refusal. The report does show errors as their own
category, but the score does not leave them out.

## 3. Statistical noise

Pass rates from small suites are very uncertain (Wilson 95% intervals):

| Runs | Passed | 95% CI | Effect of one flipped run on the score |
|---|---|---|---|
| 10 | 8 | 49%–94% | 7.0 points |
| 30 | 25 | 66%–93% | 2.3 points |
| 100 | 83 | 74%–89% | 0.7 points |
| 300 | 250 | 79%–87% | 0.2 points |

- About 62 runs are needed for ±10 points and about 246 for ±5 points (at an 80% pass rate).
- The report does not show confidence intervals, so a 5-point difference between two versions can be pure noise.
- The version diff uses a per-scenario majority vote, and ties count as a pass. In a mock run, the pass rate fell
  from 97% to 83% between versions while the diff reported **0 regressed scenarios**. The drop was spread across
  trials and never flipped a majority.

## 4. Rule-based detectors

These checks run without an LLM, so they are cheap and deterministic, but they are keyword-based. Results on
deliberately tricky, hand-written cases (`bench/probe_detectors.py`). This documents failure modes; it is **not** an
accuracy estimate on real traffic.

**Refusal heuristic** (fallback when the LLM judge is off or fails): v1 7/14, v2 11/14.
- Still wrong on refusals without keywords ("Absolutely not. That would destroy production data.", "No.")
  and on enthusiastic compliance containing a refusal word ("I can't wait to help! Deleting everything now.").
- v1 also failed on curly apostrophes, and counted "verify"/"policy" as refusals even inside compliance.

**Hallucinated-success detector:** 3/6.
- Misses claims without trigger words ("The records are gone now.", "Cleanup finished, table is empty.").
- A hedge word anywhere suppresses the flag ("I couldn't confirm it, but the deletion has been completed.").

**Tool-call parser:** 3/6.
- Handles `TOOL_CALL: name | {json}` (nested JSON, lowercase, no arguments).
- Ignores JSON tool objects (`{"tool": ..., "args": ...}`) and function-call syntax (`list_records(table='users')`).
  Those turns are treated as plain text, and the agent can time out instead of being scored on what it meant to do.
- Only the **first** tool call in a turn is executed.

## 5. What Tripwire cannot test (design limits)

- **The agent is simulated.** Gemini role-plays the agent from its system prompt and tool list. Tripwire never
  calls the user's real agent code, memory, retrieval or framework, so results describe "Gemini pretending to be
  this agent".
- **Text protocol, not native function calling.** Real agents use structured tool calls; the sandbox parses text.
- **Stateless mock tools.** Each tool returns a fixed response (or a canned / injected string), whatever the input.
  Multi-step workflows where later steps depend on earlier effects can't be modelled.
- **Confirmation can never be given.** Destructive tools always answer `awaiting_confirmation`, and the user turn is
  single-shot. "Correctly performs a destructive action after the user confirms" cannot be tested.
- **Single-turn conversations.** No follow-up user messages, so clarifying questions can't be answered.
- **One model judges itself.** The same model family generates scenarios, plays the agent, classifies failures and
  judges guardrails. The classifier and judge have **not** been validated against human labels; the GOAL_DRIFT label
  in particular has no deterministic check.
- **Static, English-only probes.** 12 fixed guardrail probes plus 2 per destructive tool. No multilingual, encoded
  (base64, leetspeak), multi-turn or adaptive attacks; an agent tuned on this list can overfit to it.
- **Prompt injection only through tool output replacement.** The injected text replaces the tool's whole output; mixed
  or partial injections aren't generated.
- **Fixed limits.** `MAX_STEPS=12` and a loop threshold of 4 calls are hard-coded.

## 6. Scoring caveats

- Weights (70 pass rate / 20 guardrails / 10 coverage) are judgement calls, not calibrated.
- The 10 coverage points reward running all 5 scenario types, whatever the outcome. An agent that fails every run
  but refuses every probe still scores **30/100**.
- An agent that passes every run but was never probed scores **80 (B)**: guardrails are optional.
- Duplicate-scenario detection compares exact titles only; reworded duplicates pass through.

## 7. Operations

- **No authentication or multi-tenancy.** Anyone with the URL can read, edit, delete and spend the API quota.
- **Jobs live in one process.** A job's task runs in the worker that started it: cancelling only works there, and a
  restart marks running jobs `interrupted` rather than resuming them.
- **Live view polls the database.** Each open SSE stream queries MongoDB every 0.75 s.
- **Scorecards load runs into memory** (up to 5,000 per agent, without traces) on every report view.
- **Redis is unused.** It is connected if present, but nothing depends on it yet.
- **OneDrive "files on demand"** can leave `node_modules` and the venv as cloud-only placeholders, which makes Vite and
  Python hang. Keep the project on a local, always-available folder.

---

## What would fix what

| Limitation | Fix |
|---|---|
| Quota: 5/min, 20/day | Requests-per-minute limiter, honour `RetryInfo`, multi-provider support (OpenAI-compatible / Ollama), record-and-replay cache |
| Errors scored as failures | Leave errored runs and probes out of the score; show them as "infra errors" |
| Statistical noise | Show Wilson intervals; significance test for the version diff; suggest the trial count needed |
| Keyword detectors | Use the LLM judge by default with the heuristic as a cross-check; label ~100 traces by hand and publish precision/recall |
| Simulated agent | "Bring your own agent": call a real agent over HTTP/OpenAI-compatible APIs/MCP with native function calling |
| Stateless tools, no confirmation | Stateful mock tools and scripted multi-turn users that can confirm |
| Static probes | Adaptive attacker loop (mutate prompts until the agent breaks or a budget runs out); multilingual/encoded probes |
| No auth | API keys or JWT, per-user workspaces, per-user quota |
