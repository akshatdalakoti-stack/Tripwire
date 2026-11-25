# Tripwire

Tripwire is a CI/CD testing platform for autonomous AI agents. It evaluates agents by generating adversarial scenarios, executing them in a mocked sandbox, and scoring their reliability to catch failure modes before deployment.

**🚀 Live Website:** [https://tripwire-sigma.vercel.app/](https://tripwire-sigma.vercel.app/)

> [!WARNING]
> **Public Demo Notice:** The live deployment is provided for demonstration purposes only. It currently does not have user authentication enabled, meaning anyone can access, create, edit, or delete data on the platform. Please feel free to test it out, but do not enter any sensitive or private information!

## Demo Video

A walkthrough of the full pipeline: agent configuration, scenario generation,
sandboxed execution, failure classification, guardrail probes, and the
reliability scorecard.

https://github.com/user-attachments/assets/f5f83888-8bb7-4b1b-aeda-2fe8d559e1e8

## Architecture & Workflow

Tripwire evaluates agents through a fully automated, 5-step pipeline:

1. **Scenario Generation:** Takes an agent's prompt and toolset, and generates realistic, ambiguous, and adversarial (L0-L5) test cases.
2. **Sandboxed Execution:** Runs the agent against scenarios in a mocked environment. Destructive actions are intercepted and logged without executing.
3. **Failure Classification:** Analyzes the execution trace to detect goal drift, tool looping, and unsafe operations.
4. **Guardrail Testing:** Probes the agent with adversarial safety prompts to ensure it correctly refuses out-of-bounds requests.
5. **Reliability Scorecard:** Aggregates test results into a unified regression report and a 0-100 reliability score.

## What's in v2

- **Live test runs.** Runs execute as background jobs and stream into the UI over Server-Sent Events, with a
  pass/fail progress bar and a cancel button. Reloading the page re-attaches to a run in progress. The old
  blocking `POST /api/runs/start` endpoint still works for scripts.
- **Real concurrency.** LLM calls use the async Gemini client (the old sync call blocked the event loop, so
  "concurrent" scenarios actually ran one at a time). Calls are bounded by a global semaphore and retried with
  exponential backoff on 429/5xx, with an optional fallback model.
- **Fewer LLM calls.** The failure classifier is skipped when the sandbox has already proven a failure
  (unsafe action, loop, timeout, hallucinated success), and infrastructure errors are not re-classified.
  Guardrail probes run in parallel and are graded by one batched LLM judge.
- **Sharper detection.** Hallucinated success is caught deterministically (the agent claims "done" after a tool
  failed or was still awaiting confirmation), calls to non-existent tools are flagged, tool-call parsing handles
  nested JSON, and the classifier's verdict now decides pass/fail (a GOAL_DRIFT run is no longer counted as passed).
- **Flakiness and N trials.** Run each scenario 1-10 times from the UI; the report lists flaky scenarios.
- **Version regression tracking.** Edit an agent and bump its version; the report scores each version separately
  and diffs which scenarios regressed or improved.
- **Richer report.** Letter grade, score components, robustness by pressure level (L0-L5), pass rate by scenario
  type, guardrail results by attack category, and concrete "what to fix next" recommendations.
- **Scenario management.** Generate more scenarios with an optional focus (titles are de-duplicated), write your
  own (including prompt injection through a chosen tool), delete scenarios, run a single scenario, or re-run only
  the failures.
- **CI/CD gate and exports.** `GET /api/scorecard/{id}/gate` returns pass/fail against thresholds (HTTP 412 in
  strict mode), and reports export as Markdown or JSON.
- **Offline mock mode.** `MOCK_LLM=1` runs the whole pipeline with no API key, for demos, CI and tests.
- **Housekeeping.** MongoDB indexes, cascade deletes, clean 400s for bad ids, gzip responses, UTC-aware
  timestamps, code-split frontend routes, optional Redis, and a pytest suite.

## Known limitations

Tripwire has real limits, and they are measured rather than guessed. For example, the Gemini free tier allows only
20 requests per day per model (about 4-5 scenario runs), and a 10-run suite can't tell a 50% agent from a 90% one.
See [LIMITATIONS.md](LIMITATIONS.md) for the numbers, the scripts that produce them, and what would fix each one.

## Tech Stack

- **Backend:** Python, FastAPI, Motor (Async MongoDB), Google Gemini 3.6 Flash
- **Frontend:** React, TypeScript, Vite, Recharts
- **Infrastructure:** MongoDB Atlas, Redis (optional)

## Local Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB instance (local or Atlas)
- Redis instance (optional)
- Gemini API Key (or set `MOCK_LLM=1` to try everything offline)

### 2. Backend Installation

Navigate to the backend directory and set up the Python environment:

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Unix/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuration

Copy the sample environment file and add your credentials:
```bash
cp .env.sample .env
```

Required environment variables in `.env`:
```
GEMINI_API_KEY=your_gemini_api_key      # or MOCK_LLM=1 for the offline mock model
MONGO_URI=your_mongodb_connection_string
DB_NAME=tripwire
CORS_ORIGINS=http://localhost:5173,https://tripwire-sigma.vercel.app
```

Optional tuning (see `.env.sample`): `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, `MAX_CONCURRENT_RUNS`,
`LLM_MAX_CONCURRENCY`, `LLM_MAX_RETRIES`, `CLASSIFY_PASSES`, `GUARDRAIL_LLM_JUDGE`, `REDIS_URL`.

### 4. Database Seeding

Seed the database with the baseline agent and fixture traces to ensure the dashboard has data to display:
```bash
python seed.py
```

### 5. Running the Application

Start the FastAPI backend:
```bash
uvicorn app.main:app --reload --port 8000
```

In a separate terminal, start the React frontend:
```bash
cd frontend
npm install
npm run dev
```

The application will be accessible at `http://localhost:5173`.

### 6. Tests

```bash
cd backend
pip install -r requirements-dev.txt
MOCK_LLM=1 python -m pytest -q
```

## Using Tripwire as a CI/CD gate

Fail a pipeline when an agent drops below the bar. Run the suite first (`POST /api/runs/start/{agent_id}`, which
waits for completion), then check the gate:

```bash
curl --fail "$TRIPWIRE_URL/api/scorecard/$AGENT_ID/gate?min_score=75&max_unsafe=0&min_guardrail_rate=0.9&strict=true"
```

`strict=true` returns HTTP 412 when any check fails, so `curl --fail` exits non-zero. The report page shows the
command ready to copy.

## API overview

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/agents` · `PUT /api/agents/{id}` · `POST /api/agents/{id}/clone` | Create, edit (bump `version`), clone |
| `POST` | `/api/scenarios/generate?agent_id=&count=&focus=` | Generate scenarios (de-duplicated) |
| `POST` | `/api/scenarios` · `DELETE /api/scenarios/item/{id}` | Hand-written scenarios |
| `POST` | `/api/runs/jobs/{agent_id}?trials=` | Start a background run (body: optional `scenario_ids`) |
| `GET` | `/api/runs/jobs/{job_id}/events` | Live Server-Sent Events: `run`, `progress`, `done` |
| `POST` | `/api/runs/jobs/{job_id}/cancel` | Cancel a run |
| `GET` | `/api/runs/variance/{agent_id}` · `/api/runs/compare/{agent_id}` | Flakiness, version diff |
| `POST` | `/api/guardrails/run/{agent_id}` | Safety probes (body: optional `extra_probes`) |
| `GET` | `/api/scorecard/{agent_id}?version=` | Scorecard for one version |
| `GET` | `/api/scorecard/{agent_id}/gate` · `/export?format=md\|json` | CI gate, report export |

Interactive docs are at `http://localhost:8000/docs`.

## Repository Structure

```text
Tripwire/
├── backend/
│   ├── app/
│   │   ├── models/          # Pydantic schemas (Agent, Scenario, RunResult)
│   │   ├── routers/         # REST API endpoints
│   │   ├── services/        # Sandbox, classifier, scenario engine, guardrails, jobs, scorecard
│   │   └── utils/           # Async LLM client (+ offline mock), id helpers, trace logging
│   ├── tests/               # pytest suite (runs offline with MOCK_LLM=1)
│   ├── seed_data/           # Raw trace fixtures, scenarios, and mock tools
│   └── seed.py              # CLI script to load test data into MongoDB
├── frontend/                
│   └── src/                 # React SPA, routing, and Recharts components
└── cli_harness/             # Legacy CLI harness and raw python scripts
```

## Troubleshooting

- **MongoDB Timeout:** Ensure your IP address is whitelisted in your MongoDB Atlas network access settings.
- **Frontend Build Errors:** Ensure you are running `npm install` inside the `frontend` directory before running the dev server.
- **Missing Traces:** If the dashboard is empty, ensure you ran `python seed.py` with valid MongoDB credentials.
