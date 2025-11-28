# Architecture Documentation

**AI Contract Reviewer & Negotiation Copilot**

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ Next.js  │  │   API    │  │   A2A    │                       │
│  │    UI    │  │ Clients  │  │  Agents  │                       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
└───────┼─────────────┼─────────────┼─────────────────────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   Auth   │  │   Rate   │  │ Security │  │   A2A    │        │
│  │Middleware│  │ Limiting │  │ Headers  │  │ Endpoint │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                           │
│  ┌────────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │    Orchestrator    │  │  Memory Bank   │  │ Observability │  │
│  │ (Sequential Flow)  │  │ (State Store)  │  │   Manager     │  │
│  └─────────┬──────────┘  └───────┬────────┘  └───────────────┘  │
└────────────┼─────────────────────┼──────────────────────────────┘
             │                     │
             ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Layer                               │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │Ingestion │─▶│Extraction│─▶│   Risk   │                       │
│  │  Agent   │  │  Agent   │  │  Agent   │                       │
│  └──────────┘  └──────────┘  └────┬─────┘                       │
│                                   │                              │
│  ┌──────────┐  ┌──────────┐  ┌────▼─────┐                       │
│  │  Audit   │◀─│ Summary  │◀─│ Redline  │                       │
│  │  Agent   │  │  Agent   │  │  Agent   │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│                                                                  │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Tool Layer                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   PDF    │  │   Risk   │  │  Clause  │  │  Google  │        │
│  │  Reader  │  │  Rules   │  │Templates │  │  Search  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        LLM Layer                                 │
│              ┌─────────────────────────┐                        │
│              │   Gemini 2.0 Flash      │                        │
│              │   (via Google ADK)      │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Pipeline

### Sequential Processing Flow

```
1. INGESTION AGENT
   Input:  Raw contract file (PDF/TXT)
   Output: Normalized text + metadata (parties, dates, jurisdiction)
   Tools:  PDF Reader, Text Normalizer

2. EXTRACTION AGENT
   Input:  Normalized text from Memory Bank
   Output: Classified clauses with locations
   Tools:  Pattern matching + LLM classification

3. RISK SCORING AGENT
   Input:  Extracted clauses
   Output: Risk assessments with severity (low/medium/high)
   Tools:  Risk Rules lookup + LLM reasoning

4. REDLINE AGENT
   Input:  High/medium risk clauses
   Output: Alternative language with rationale
   Tools:  Clause Templates + LLM generation

5. SUMMARY AGENT
   Input:  All analysis results
   Output: Negotiation materials, draft email
   Tools:  LLM summarization

6. AUDIT AGENT
   Input:  Complete session data
   Output: Audit bundle with full traceability
   Tools:  Trace compilation
```

---

## Memory Bank State Evolution

```json
// Initial State (after upload)
{
  "session_id": "uuid",
  "filename": "contract.pdf",
  "user_id": "user123"
}

// After Ingestion Agent
{
  "contract_metadata": {
    "parties": ["Company A", "Company B"],
    "date": "2025-01-15",
    "jurisdiction": "Delaware"
  },
  "normalized_text": "..."
}

// After Extraction Agent
{
  "extracted_clauses": [
    {"id": "c1", "type": "confidentiality", "text": "..."},
    {"id": "c2", "type": "indemnification", "text": "..."}
  ]
}

// After Risk Agent
{
  "risk_assessments": [
    {"clause_id": "c1", "severity": "high", "explanation": "..."}
  ]
}

// After Redline Agent
{
  "redline_proposals": [
    {"clause_id": "c1", "original": "...", "proposed": "...", "rationale": "..."}
  ]
}

// After Summary Agent
{
  "negotiation_summary": {
    "executive_summary": "...",
    "priority_issues": [...],
    "draft_email": "..."
  }
}

// After Audit Agent
{
  "audit_bundle": {
    "agent_traces": [...],
    "timestamps": {...},
    "compliance_report": "..."
  }
}
```

---

## Key Components

### Orchestrator (`adk/orchestrator.py`)
- Manages sequential agent execution
- Handles error recovery and graceful degradation
- Coordinates Memory Bank reads/writes
- Tracks execution with OpenTelemetry

### Memory Bank (`memory/memory_bank.py`)
- Persistent state storage between agents
- Session resume capability
- Efficient serialization with msgspec

### Observability (`adk/observability.py`)
- Structured logging with Loguru
- OpenTelemetry tracing
- Metrics collection

### Security (`api/security.py`)
- HMAC authentication
- Rate limiting
- Security headers
- Audit logging

---

## Data Models (`adk/models.py`)

```python
class Clause(Struct):
    id: str
    type: str
    text: str
    start_line: int
    end_line: int

class RiskAssessment(Struct):
    clause_id: str
    severity: Literal["low", "medium", "high"]
    risk_type: str
    explanation: str

class RedlineProposal(Struct):
    clause_id: str
    original_text: str
    proposed_text: str
    rationale: str
```
---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Google ADK | Agent orchestration |
| LLM | Gemini 2.0 Flash | Reasoning & generation |
| Backend | FastAPI | REST API |
| Frontend | Next.js | Demo UI |
| Validation | msgspec | Fast serialization |
| Logging | Loguru | Structured logs |
| Tracing | OpenTelemetry | Observability |
| Database | SQLite/PostgreSQL | Session storage |
