# Simple UI

A dead-simple, single-file web client for the Tripwire backend. **No build step,
no npm, no framework, no chart library, no animations** — just one `index.html`
with plain HTML, a little CSS, and vanilla `fetch`.

It's an alternative to the full React app in `../frontend/`. Use whichever you
prefer; this one is for when you just want to click through the API quickly.

## Use it

1. **Start the backend** (needs MongoDB, Redis, and a Gemini key — see
   `../backend`):
   ```bash
   cd ../backend
   uvicorn app.main:app --reload --port 8000
   ```
2. **Open the UI** — just double-click `index.html`, or serve the folder:
   ```bash
   python -m http.server 5500
   ```
   then visit `http://localhost:5500`. (The backend allows all CORS origins, so
   opening the file directly works too.)
3. In the page: set **API base URL** (default `http://localhost:8000/api`),
   click **Test connection**, then:
   - **Agents** — create an agent (or pick one), set it active.
   - **Scenarios** — generate scenarios for the agent, or load existing ones.
   - **Runs** — start a run (all scenarios in the sandbox), then click any run to
     see its trace. Flagged/unsafe steps are marked in red.
   - **Guardrails** — run the safety probes and see the pass rate.
   - **Scorecard** — the reliability score, pass rate, and failure breakdown.

The active agent and API URL are remembered in the browser (localStorage).

## What it talks to

| Feature | Endpoint |
|---|---|
| List / create / delete agents | `/api/agents` |
| Generate / list scenarios | `/api/scenarios/generate`, `/api/scenarios/{agent_id}` |
| Start run / list runs / one run | `/api/runs/start/{id}`, `/api/runs/agent/{id}`, `/api/runs/{run_id}` |
| Guardrail probes | `/api/guardrails/run/{id}`, `/api/guardrails/agent/{id}` |
| Scorecard | `/api/scorecard/{id}` |
