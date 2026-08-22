# 🪤 Tripwire

> **AI Agent Evaluation and Reliability Engine** — CI/CD for autonomous AI agents.

Tripwire automatically generates realistic and adversarial test scenarios for a given AI agent, runs it in a sandboxed environment, scores failure modes, and produces a reliability report.

---

## 🔍 What it does

| Component | Description |
|---|---|
| **Scenario Generation Engine** | Reads an agent's tools, prompt & domain → generates realistic + adversarial test cases at scale using Gemini |
| **Sandboxed Execution Harness** | Runs the agent against generated scenarios with mocked tools, capturing traces for deterministic replay |
| **Failure Mode Classifier** | Categorises why a run failed — tool loops, hallucinated confidence, unsafe actions, goal drift |
| **Destructive Action Guardrail Tester** | Probes an agent's willingness to perform irreversible actions under pressure or ambiguous instruction |
| **Reliability Scorecard & Regression Tracker** | Scores and tracks agent reliability across versions and task categories |

---

## 🏗️ Tech Stack

- **Backend:** Python + FastAPI + LangChain + Google Gemini 2.0 Flash
- **Frontend:** React + Vite + TypeScript + Recharts
- **Database:** MongoDB (runs/traces/reports) + Redis (job queue)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB (local or Atlas)
- Redis (local or Upstash)
- Gemini API Key → [aistudio.google.com](https://aistudio.google.com)

### Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.sample .env          # Fill in your keys
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.sample .env.local    # Set VITE_API_URL=http://localhost:8000
npm run dev
```

---

## 📁 Project Structure

```
Tripwire/
├── backend/         # FastAPI + AI services
├── frontend/        # React + Vite dashboard
└── README.md
```

---

## 🧠 Problem Statement

*Theme: Agent Infrastructure, Testing and Failure Prediction*

Autonomous AI agents fail on ~70% of real-world tasks. Teams ship agents against a handful of manually written test prompts — so real failure modes surface only after deployment. Tripwire is the automated fix.
