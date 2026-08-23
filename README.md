# Tripwire

Tripwire is a CI/CD testing platform for autonomous AI agents. It evaluates agents by generating adversarial scenarios, executing them in a mocked sandbox, and scoring their reliability to catch failure modes before deployment.

## Demo Video

A walkthrough of the full pipeline: agent configuration, scenario generation,
sandboxed execution, failure classification, guardrail probes, and the
reliability scorecard.

[Watch the demo](docs/demo.mp4) (30 MB, 4:17)

## Architecture & Workflow

Tripwire evaluates agents through a fully automated, 5-step pipeline:

1. **Scenario Generation:** Takes an agent's prompt and toolset, and generates realistic, ambiguous, and adversarial (L0-L5) test cases.
2. **Sandboxed Execution:** Runs the agent against scenarios in a mocked environment. Destructive actions are intercepted and logged without executing.
3. **Failure Classification:** Analyzes the execution trace to detect goal drift, tool looping, and unsafe operations.
4. **Guardrail Testing:** Probes the agent with adversarial safety prompts to ensure it correctly refuses out-of-bounds requests.
5. **Reliability Scorecard:** Aggregates test results into a unified regression report and a 0-100 reliability score.

## Tech Stack

- **Backend:** Python, FastAPI, Motor (Async MongoDB), Google Gemini 3.6 Flash
- **Frontend:** React, TypeScript, Vite, Recharts
- **Infrastructure:** MongoDB Atlas, Redis (for caching and job tracking)

## Local Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB instance (local or Atlas)
- Redis instance (local or Upstash)
- Gemini API Key

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
GEMINI_API_KEY=your_gemini_api_key
MONGO_URI=your_mongodb_connection_string
REDIS_URL=your_redis_connection_string
DB_NAME=tripwire
```

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

## Repository Structure

```text
Tripwire/
├── backend/
│   ├── app/
│   │   ├── models/          # Pydantic schemas (Agent, Scenario, RunResult)
│   │   ├── routers/         # REST API endpoints
│   │   ├── services/        # Core business logic (Sandbox, Classifier, Engine)
│   │   └── utils/           # LLM client wrappers and logging
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
