# AI Contract Reviewer & Negotiation Copilot

> **Kaggle Agents Intensive Capstone Project - Enterprise Agents Track**

A production-ready multi-agent system built with **Google ADK** and **Gemini 2.0 Flash** for automated contract review, risk assessment, and negotiation preparation.

---

## 🎯 Problem

Contract review is a critical bottleneck in business operations:

- **Slow**: Days or weeks for complex contracts
- **Expensive**: Requires costly legal expertise
- **Inconsistent**: Different reviewers catch different risks
- **Error-prone**: Human fatigue leads to missed clauses

Small to medium businesses often lack dedicated legal teams, forcing them to accept risky terms or pay expensive external counsel.

---

## 💡 Solution

A **6-agent pipeline** that transforms contract review from days to minutes:

```
Contract → Ingestion → Extraction → Risk Scoring → Redlining → Summary → Audit
```

| Agent | Purpose |
|-------|---------|
| **Ingestion** | Parse PDF/text, extract metadata (parties, dates, jurisdiction) |
| **Extraction** | Identify and classify contract clauses |
| **Risk Scoring** | Assess risks with severity levels (low/medium/high) |
| **Redline** | Generate safer alternative language with rationale |
| **Summary** | Create negotiation materials and draft emails |
| **Audit** | Compile complete audit trail for compliance |

---

## ✨ Course Concepts Implemented

| Concept | Implementation |
|---------|----------------|
| ✅ **Multi-Agent System** | 6 sequential agents with orchestrator |
| ✅ **Tools** | PDF reader, risk rules, clause templates |
| ✅ **Sessions & Memory** | Memory Bank for persistent state between agents |
| ✅ **Observability** | Loguru structured logging + OpenTelemetry tracing
| ✅ **Agent Deployment** | Docker, Docker Compose, Cloud Run ready |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

### Setup

```bash
# Clone repository
git clone https://github.com/amitgoesbrr/contract-copilot.git
cd contract-copilot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

# Start API server
python run_api.py
```

### Access

- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health

### Start UI

```bash
cd ui
npm install
npm run dev
# Visit http://localhost:3000
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                          │
│         Next.js UI  │  API Clients  │  A2A Agents       │
└────────────────────────────┬────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────┐
│              API Layer (FastAPI)                         │
│    Auth  │  Rate Limiting  │  Security  │  A2A Mount    │
└────────────────────────────┬────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────┐
│            Orchestration Layer                           │
│    Orchestrator  │  Memory Bank  │  Observability       │
└────────────────────────────┬────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────┐
│              Agent Layer (Google ADK + Gemini)           │
│  Ingestion → Extraction → Risk → Redline → Summary → Audit
└─────────────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed technical documentation.

---

## 📁 Project Structure

```
contract-copilot/
├── adk/                    # Agent Development Kit
│   ├── agents/             # 6 specialized agents
│   ├── orchestrator.py     # Sequential agent execution
│   ├── models.py           # Data models (msgspec)
│   ├── observability.py    # Tracing & metrics
│   ├── a2a_wrapper.py      # A2A protocol support
│   ├── risk_rules.json     # Risk detection patterns
│   └── clause_templates.json # Redline templates
├── api/                    # FastAPI REST API
│   ├── main.py             # API endpoints
│   └── security.py         # Auth & rate limiting
├── tools/                  # Custom tools
│   ├── pdf_reader.py       # PDF text extraction
│   ├── risk_rule_lookup.py # Pattern matching
│   └── clause_template_lookup.py
├── memory/                 # Session & state management
│   ├── memory_bank.py      # Memory Bank integration
│   └── session_manager.py  # Session lifecycle
├── ui/                     # Next.js frontend
├── sample_contracts/       # Test contracts (NDA, MSA, SLA)
├── evaluation/             # Testing & evaluation
├── logs/                   # Application logs & traces
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md     # Technical architecture
│   └── DEPLOYMENT_GUIDE.md # Deployment instructions
├── docker-compose.yml      # Full stack deployment
├── Dockerfile              # Container image
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
└── run_api.py              # API startup script
```

---

## 🐳 Docker Deployment

```bash
# Configure environment
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

# Start all services
docker-compose up -d

# Access
# API: http://localhost:8000
# UI:  http://localhost:3000

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for Cloud deployment.

---

## 📊 Business Impact

| Metric | Value |
|--------|-------|
| Time Reduction | **95%** (days → minutes) |
| Cost Savings | **80%** for routine contracts |
| Consistency | Standardized risk assessment |
| Audit Trail | Complete traceability |

---

## 🔒 Security Features

- **No Default Persistence**: Contracts deleted after processing
- **HMAC Authentication**: Secure session tokens
- **Rate Limiting**: Abuse prevention
- **Security Headers**: XSS, CSRF protection
- **Audit Logging**: Complete event tracking

---

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md) - Technical design and components
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Setup and deployment instructions

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | Google ADK |
| LLM | Gemini 2.0 Flash |
| Backend | FastAPI |
| Frontend | Next.js |
| Validation | msgspec |
| Logging | Loguru |
| Tracing | OpenTelemetry |
| Database | SQLite / PostgreSQL |

---

## 📜 License

MIT License

---

**Built for Kaggle Agents Intensive Capstone Project**
**Track:** Enterprise Agents
**Framework:** Google ADK + Gemini 2.0 Flash
