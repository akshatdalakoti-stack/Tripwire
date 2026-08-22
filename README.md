# 🪤 Tripwire

> **AI Agent Evaluation and Reliability Engine** — Automated CI/CD for autonomous AI agents.

Tripwire generates realistic and adversarial test scenarios for any AI agent, runs them in a sandboxed environment, classifies failure modes, tests safety guardrails, and produces a reliability score — functioning as a continuous integration system for AI agents.

---

## 🔍 Core Features

| Component | What it does |
|---|---|
| **Scenario Generation Engine** | Reads an agent's tools, prompt & domain → generates realistic + adversarial test cases using Gemini |
| **Sandboxed Execution Harness** | Runs the agent against each scenario with mocked tools, capturing full execution traces |
| **Failure Mode Classifier** | Uses Gemini to classify why a run failed: Tool Loop, Hallucinated Confidence, Unsafe Action, Goal Drift, Timeout |
| **Guardrail Tester** | Probes the agent with 10+ adversarial safety prompts to test refusal behaviour |
| **Reliability Scorecard** | Scores agent reliability 0–100 and tracks regression across versions |

---

## 🏗️ Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · Google Gemini 2.0 Flash |
| Frontend | React · Vite · TypeScript · Recharts |
| Database | MongoDB Atlas · Redis (Upstash) |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- [MongoDB Atlas](https://www.mongodb.com/atlas) free cluster
- [Upstash Redis](https://upstash.com) free instance
- [Gemini API Key](https://aistudio.google.com) (free)

### 1. Clone & configure
```bash
git clone https://github.com/Harshcodes04/Tripwire.git
cd Tripwire
```

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt

cp .env.sample .env
# Fill in GEMINI_API_KEY, MONGO_URI, REDIS_URL in .env

python seed.py                 # Load demo agent
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

### 4. Demo
1. Open `http://localhost:5173`
2. The **Customer Support Bot** demo agent is pre-loaded
3. Click **Run Tests** → watch scenarios run through the sandbox
4. Click **Report** → see the reliability score + failure breakdown + guardrail results

---

## 📁 Structure

```
Tripwire/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entry point
│   │   ├── config.py             # Environment settings
│   │   ├── database.py           # MongoDB + Redis connections
│   │   ├── models/               # Pydantic schemas
│   │   ├── routers/              # API endpoints
│   │   ├── services/             # Core AI services
│   │   └── utils/                # Gemini client + trace logger
│   ├── seed.py                   # Demo agent loader
│   └── requirements.txt
└── frontend/
    └── src/
        ├── pages/                # Dashboard, AgentConfig, RunView, FailureReport
        ├── components/           # Navbar, TraceViewer, FailureBadge, ReliabilityChart
        ├── api/                  # Typed Axios client
        └── types/                # Shared TypeScript interfaces
```

---

## 🧠 Problem Statement

*Theme: Agent Infrastructure, Testing and Failure Prediction*

Autonomous AI agents fail on ~70% of real-world tasks. Teams ship agents against a handful of manually written prompts — real failure modes only surface after deployment. **Tripwire is the automated fix.**
