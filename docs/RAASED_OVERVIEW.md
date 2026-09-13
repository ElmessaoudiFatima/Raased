# Raased (راصد) — Complete Project Overview

> **Raased** means *"observer"* or *"watcher"* in Arabic. It is an autonomous AI agent that turns mobile network signals into an early-warning and corrective system for critical freight moving through MENA logistics corridors.

Built for the **GSMA MENA Ignite Hackathon** — Open Gateway Innovation Challenge, Theme 7 (Open Innovation).  
Team: **Novatech** | Platform: **https://app.raased.ma**

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [What Raased Does](#2-what-raased-does)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Component Breakdown](#4-component-breakdown)
   - 4.1 [Frontend — Next.js Dashboard](#41-frontend--nextjs-dashboard)
   - 4.2 [Platform API — Flask](#42-platform-api--flask)
   - 4.3 [Agent Engine — FastAPI + LangGraph](#43-agent-engine--fastapi--langgraph)
   - 4.4 [CAMARA / Nokia Network-as-Code Integration](#44-camara--nokia-network-as-code-integration)
   - 4.5 [Databases](#45-databases)
5. [AI Agent Pipeline (Deep Dive)](#5-ai-agent-pipeline-deep-dive)
6. [Technology Stack](#6-technology-stack)
7. [Repository Structure](#7-repository-structure)
8. [How to Run the Project](#8-how-to-run-the-project)
   - 8.1 [With Docker Compose (recommended)](#81-with-docker-compose-recommended)
   - 8.2 [Manually — Platform (Flask + Next.js)](#82-manually--platform-flask--nextjs)
   - 8.3 [Manually — Agent Engine (FastAPI)](#83-manually--agent-engine-fastapi)
9. [Environment Variables](#9-environment-variables)
10. [Demo Accounts](#10-demo-accounts)
11. [Team](#11-team)

---

## 1. Problem Statement

Logistics platforms operating in MENA's highest-risk corridors face two compounding issues:

1. **Blind spots** — Traditional data feeds (road-traffic sensors, GPS, weather) are delayed, incomplete, or unavailable in isolated, contested, or remote border zones.
2. **No fast corrective lever** — Even when a disruption is eventually detected, logistics platforms have no immediate way to protect shipments already in transit through the affected corridor.

---

## 2. What Raased Does

Raased treats the **mobile network itself as a real-time risk sensor** — not just a communication pipe — by continuously consuming CAMARA telecom APIs. It acts as an **autonomous decision-making agent**, not a passive dashboard.

The agent pipeline:

1. **Ingests** real-time congestion signals for trackers moving through monitored corridors.
2. **Contextualizes** each signal against geospatial data and historical baselines, distinguishing a genuine disruption (security incident, road blockage) from ordinary crowding (stadium event, rush hour).
3. **Classifies** the situation: `normal → event → incident → crisis`.
4. **Verifies trust** — runs Number Verification / SIM Swap / Device Swap checks so the agent never acts on a compromised or spoofed tracker signal.
5. **Acts autonomously**, within guardrails:
   - Alerts logistics operators with a plain-language, auditable explanation.
   - Suggests alternative routing.
   - Requests **Quality on Demand (QoD)** to secure tracking telemetry for critical cargo.
   - Requests **Network Slicing** for the most severe (crisis-level) cases.
   - Escalates to a human for approval whenever trust checks fail or the situation is classified as `crisis`.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Driver / Manager / Admin                            │
│            (Next.js 14 web dashboard)                            │
└─────────────────────────┬────────────────────────────────────────┘
                          │ HTTP  (port 3000)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│              Flask Platform API  (port 5000)                     │
│  Auth · RBAC · Org management · Drivers · Cargos · Alerts       │
│  Live map · Invitation flow · Document upload                    │
└──────────┬───────────────────────────────────────────────────────┘
           │ internal calls
           ▼
┌──────────────────────────────────────────────────────────────────┐
│              FastAPI Agent Engine  (port 8000)                   │
│                 SENTRY — LangGraph pipeline                      │
│                                                                  │
│  load_context → [camara_perception] → [trust_checks]            │
│    → check_weather → fuse_context → rules                       │
│    → search_similar → llm_reasoning → persist_assessment        │
│    → [network_action] → memory                                   │
└──────┬────────────────────────────────┬────────────────────────--┘
       │                                │
       ▼                                ▼
┌──────────────────┐       ┌────────────────────────────────────┐
│  PostgreSQL      │       │  CAMARA / Nokia Network-as-Code    │
│  + PostGIS       │       │  Congestion Insights               │
│  (agent DB)      │       │  Location Retrieval                │
│                  │       │  Geofencing                        │
│  PostgreSQL      │       │  Quality on Demand (QoD)           │
│  (platform DB)   │       │  Network Slicing                   │
│                  │       │  Number Verification               │
│  ChromaDB        │       │  SIM Swap · Device Swap            │
│  (vector memory) │       └────────────────────────────────────┘
└──────────────────┘
```

---

## 4. Component Breakdown

### 4.1 Frontend — Next.js Dashboard

**Location:** `frontend/`  
**Port:** 3000  
**Stack:** Next.js 14 (App Router) · React · TailwindCSS · Leaflet/OpenStreetMap · Recharts · Axios

The frontend serves three distinct role-based interfaces:

| Role | Pages |
|---|---|
| **Admin** | Pending company registrations, document review, approve/reject, stats |
| **Manager** | Overview, drivers, invite co-manager, cargos, trackers, alerts, live map, AI decisions |
| **Driver** | Active trip, live map position, delivery history, alerts |

Key pages (`frontend/app/`):
- `/login`, `/register` (5-step company onboarding), `/forgot-password`, `/set-password`
- `/dashboard/overview` — fleet summary
- `/dashboard/map` — real-time convoy positions on corridors
- `/dashboard/cargos`, `/dashboard/trackers`, `/dashboard/drivers`
- `/dashboard/alerts`, `/dashboard/ai-decisions`
- `/dashboard/observatory` — corridor and risk zone monitoring
- `/dashboard/admin` — registration management (admin only)

---

### 4.2 Platform API — Flask

**Location:** `flask_api/`  
**Port:** 5000  
**Stack:** Flask 3 · SQLAlchemy 2 · bcrypt · PyJWT · PostgreSQL (or SQLite fallback)

This API is the main layer consumed by the Next.js frontend. It handles:

- **Authentication**: login, 5-step registration with email OTP, forgot-password flow, secure invitation links for drivers and co-managers.
- **Admin space**: review and validate company registrations, download uploaded documents.
- **Manager space**: manage fleet (drivers, trackers, cargos), view alerts, live map data.
- **Driver space**: view assigned trip, real-time position, delivery history, alerts.
- **Live map**: simulated real-time convoy positions on corridors and risk zones.

Key source files:

| File | Responsibility |
|---|---|
| `app.py` | Flask factory, blueprints registration, DB initialization |
| `models.py` | All SQLAlchemy models (users, orgs, cargos, trackers, alerts, corridors, …) |
| `security.py` | bcrypt password hashing, JWT generation/validation, role decorators |
| `service.py` | OTP generation, invitation management, code validation |
| `auth.py` | Registration, login, verification, password reset, invitation endpoints |
| `admin.py` | Organization approval, document access |
| `manager.py` | Fleet management endpoints |
| `driver.py` | Driver-facing endpoints |
| `map_data.py` | Live map data aggregation |
| `map_tools.py` | Simulated convoy position calculation along routes |
| `seed.py` | Pre-seeded demo data (companies, users, cargos, corridors) |

---

### 4.3 Agent Engine — FastAPI + LangGraph

**Location:** `backend/`  
**Port:** 8000  
**Stack:** FastAPI · LangGraph · asyncpg · SQLAlchemy (async) · Alembic · Pydantic

This is the SENTRY AI agent — the core of the project. It exposes a REST API (`POST /api/v1/agent/assess`) that triggers one full assessment cycle for a given tracker.

**Graph structure** (`backend/app/agent/graph.py`):

```
START
  └─► load_context
        ├─► camara_perception  (if congestion or location requested)
        │     └─► trust_checks / rules
        ├─► trust_checks        (if trust checks requested, no perception)
        │     └─► check_weather
        └─► rules               (direct, if no CAMARA calls needed)
              └─► (from check_weather →) fuse_context → rules
                    └─► search_similar
                          └─► llm_reasoning
                                └─► persist_assessment
                                      ├─► network_action  (if approved + QoD/Slice needed)
                                      │     └─► memory
                                      └─► memory
                                            └─► END
```

**LangGraph nodes** (`backend/app/agent/nodes.py`):

| Node | What it does |
|---|---|
| `load_context` | Loads tracker, cargo, position (PostGIS), congestion event, corridor, risk zone, historical baseline, known context, security alerts from PostgreSQL |
| `camara_perception` | Calls CAMARA Congestion Insights and Location Retrieval APIs |
| `trust_checks` | Calls CAMARA Number Verification, SIM Swap, Device Swap |
| `check_weather` | Fetches weather data from Open-Meteo for the tracker's corridor |
| `fuse_context` | Merges all data sources (CAMARA + weather + DB) into a unified state |
| `rules` | Deterministic rules engine — classifies risk level without LLM |
| `search_similar` | Queries ChromaDB for semantically similar past situations |
| `llm_reasoning` | Google Gemini LLM generates a plain-language auditable explanation |
| `persist_assessment` | Saves RiskAssessment, AgentDecision, Alert, and audit log to PostgreSQL |
| `network_action` | Executes CAMARA QoD or Network Slice if approved |
| `memory` | Stores decision summary in ChromaDB for future recall |

**State** (`backend/app/agent/state.py`): A `TypedDict` (`AgentState`) with `total=False` flows through every node. Key principle: `None` means "data not available" — the agent never fabricates missing data. Reducers `merge_missing` (deduplication) and `merge_trace` (chronological accumulation) handle repeated writes.

---

### 4.4 CAMARA / Nokia Network-as-Code Integration

**Location:** `backend/app/camara/`

All CAMARA calls route through Nokia's Network-as-Code sandbox (`https://network-as-code.p-eu.apihub.nokia.io`).

| Module | API | Purpose |
|---|---|---|
| `congestion.py` | Congestion Insights | Primary risk signal — congestion level + confidence score for a tracker MSISDN |
| `location.py` | Location Retrieval | Network-based location area, cross-referenced with corridor risk zones via PostGIS |
| `geofencing.py` | Geofencing | Webhook-based alerts when a tracker enters a sensitive zone |
| `qod.py` | Quality on Demand | Prioritizes tracker connectivity once risk is confirmed on critical cargo |
| `slicing.py` | Network Slicing | Reserves dedicated resources for crisis-level cases |
| `trust.py` | Number Verification + SIM Swap + Device Swap | Full trust chain verification before any action is taken |
| `client.py` | Base HTTP client | Shared request logic, error handling (`CamaraAPIError`) |

---

### 4.5 Databases

| Database | Engine | Purpose |
|---|---|---|
| **Agent DB** | PostgreSQL 16 + PostGIS 3.4 | Corridors, risk zones, trackers, cargos, congestion events, risk assessments, agent decisions, audit logs, network actions, security checks |
| **Platform DB** | PostgreSQL 16 (plain) | Users, organizations, invitations, OTP codes, documents, alerts (platform layer) |
| **Vector Memory** | ChromaDB | Episodic agent memory — semantic search of past decisions for contextual recall |

PostGIS enables spatial queries: tracker positions are stored as `POINT` geometry, corridors as `POLYGON`/`LINESTRING`, and risk zones as `POLYGON`. The agent queries whether a tracker is inside a risk zone using native PostGIS `ST_Within` / `ST_Distance` functions.

Database migrations for the agent DB are managed by **Alembic** (`backend/migrations/`).

---

## 5. AI Agent Pipeline (Deep Dive)

A full assessment cycle for one tracker proceeds as follows:

### Step 1 — Context Loading (`load_context`)
The agent queries PostgreSQL to load:
- The tracker record and its current GPS position
- The associated cargo (type, criticality, deadline, driver)
- The active corridor the tracker is on
- Any risk zones along that corridor
- The historical congestion baseline for that corridor (what is "normal")
- Known context events (planned public events, road works, border closures)
- Active security alerts in the area

### Step 2 — CAMARA Network Perception (`camara_perception`)
Conditional — only runs if the assessment request includes a `camara_requests` plan:
- **Congestion Insights**: returns the current congestion level (0–1) and a confidence score for the tracker's MSISDN.
- **Location Retrieval**: returns a network-based location radius, stored as a PostGIS geometry and compared to corridor risk zone polygons.

### Step 3 — Trust Verification (`trust_checks`)
Before acting on any signal, three CAMARA trust checks run:
- **Number Verification**: is the active MSISDN the one enrolled for this tracker?
- **SIM Swap**: was the SIM recently changed? → potential compromise.
- **Device Swap**: was the physical device recently replaced? → potential hardware spoofing.

If any check fails, `requires_human_approval = True` is set in the state.

### Step 4 — Weather Context (`check_weather`)
Open-Meteo is queried for the corridor's weather conditions (wind speed, precipitation, visibility). Cached for 20 minutes.

### Step 5 — Context Fusion (`fuse_context`)
All data sources (database, CAMARA, weather) are merged into a single unified state for the rules engine and LLM. Missing data is recorded explicitly in `missing_information[]`.

### Step 6 — Deterministic Rules Engine (`rules`)
`backend/app/agent/rules.py` runs a fully deterministic evaluation:
- Compares congestion level against the corridor's historical baseline.
- Applies configured thresholds (`CONGESTION_ALERT_THRESHOLD = 0.7`, `CONGESTION_CONFIDENCE_MIN = 0.6`).
- Considers cargo criticality, known context events, and trust check results.
- Outputs one of: `normal`, `event`, `incident`, `crisis`.
- Sets `qod_required` or `network_slice_required` flags accordingly.

The LLM never participates in the classification — only in the explanation.

### Step 7 — Similar Cases Search (`search_similar`)
ChromaDB is queried with a text summary of the current situation. The top-k most similar past decisions are retrieved and passed to the LLM as context, enabling the agent to learn from history.

### Step 8 — LLM Reasoning (`llm_reasoning`)
Google Gemini (`gemini-2.5-flash`) receives:
- The full agent state (risk level, congestion data, cargo details, trust results, weather)
- Retrieved similar past cases from ChromaDB
- A structured prompt requesting a plain-language explanation

The LLM outputs:
- A human-readable explanation of the decision
- The reasoning behind the risk classification
- A note on what data was unavailable (`missing_information`)

This output is auditable, never actionable — only the rules engine classifies risk.

### Step 9 — Persist & Audit (`persist_assessment`)
The following records are written to PostgreSQL:
- `RiskAssessment` — the full assessment snapshot
- `AgentDecision` — the decision with LLM explanation
- `Alert` — if risk level ≥ `incident`, an alert is created for the manager dashboard
- Audit log entry — append-only, hashed, timestamped

### Step 10 — Network Action (`network_action`)
Conditional — only runs if:
- The decision requires QoD or Network Slicing, **AND**
- Human approval has been granted (or is not required)

Calls the appropriate CAMARA API and records the `NetworkAction` in PostgreSQL.

### Step 11 — Episodic Memory (`memory`)
A text summary of the situation and decision is embedded and stored in ChromaDB, making it available for `search_similar` in future assessment cycles.

---

## 6. Technology Stack

| Layer | Technology | Version / Notes |
|---|---|---|
| **Frontend** | Next.js | 14 (App Router) |
| **UI Styling** | TailwindCSS | — |
| **Map** | Leaflet + OpenStreetMap | via `react-leaflet` |
| **Charts** | Recharts | — |
| **HTTP Client** | Axios | — |
| **Platform API** | Flask | 3 |
| **Platform ORM** | SQLAlchemy | 2 |
| **Platform Auth** | bcrypt + PyJWT | — |
| **Agent API** | FastAPI | — |
| **Agent Orchestration** | LangGraph | StateGraph with conditional edges |
| **LLM Reasoning** | Google Gemini | `gemini-2.5-flash` via `google-generativeai` SDK |
| **LLM Alternatives** | Groq / OpenAI | Configurable via `LLM_PROVIDER` env var |
| **Agent DB ORM** | SQLAlchemy (async) | asyncpg driver |
| **Migrations** | Alembic | — |
| **Spatial DB** | PostgreSQL + PostGIS | 16 + 3.4 |
| **Platform DB** | PostgreSQL | 16 |
| **Vector Memory** | ChromaDB | Episodic agent memory |
| **External APIs** | CAMARA | via Nokia Network-as-Code sandbox |
| **Weather** | Open-Meteo | Free, no API key required |
| **Rate Limiting** | slowapi | — |
| **Infrastructure** | Docker Compose | 5 services: db, platform-db, flask-api, backend, frontend |
| **CI** | GitHub Actions | — |

---

## 7. Repository Structure

```
raased/
├── backend/                      ← FastAPI agent engine (SENTRY)
│   ├── app/
│   │   ├── main.py               ← FastAPI entry point, CORS, rate limiting
│   │   ├── core/
│   │   │   └── config.py         ← All settings (env-driven, pydantic-settings)
│   │   ├── agent/
│   │   │   ├── graph.py          ← LangGraph StateGraph definition
│   │   │   ├── nodes.py          ← 11 async node functions
│   │   │   ├── state.py          ← AgentState TypedDict + reducers + utilities
│   │   │   ├── rules.py          ← Deterministic risk classification engine
│   │   │   ├── reasoning.py      ← Google Gemini LLM integration
│   │   │   └── memory.py         ← ChromaDB read/write
│   │   ├── camara/
│   │   │   ├── client.py         ← Base HTTP client + CamaraAPIError
│   │   │   ├── congestion.py     ← Congestion Insights
│   │   │   ├── location.py       ← Location Retrieval
│   │   │   ├── geofencing.py     ← Geofencing webhooks
│   │   │   ├── qod.py            ← Quality on Demand
│   │   │   ├── slicing.py        ← Network Slicing
│   │   │   └── trust.py          ← Number Verification + SIM Swap + Device Swap
│   │   ├── db/
│   │   │   ├── session.py        ← Async SQLAlchemy session factory
│   │   │   ├── base.py           ← Declarative base
│   │   │   └── models/           ← One file per table
│   │   ├── api/v1/               ← REST endpoints (health, agent/assess)
│   │   └── services/
│   │       └── audit.py          ← Append-only audit log writer
│   ├── migrations/               ← Alembic migration scripts
│   ├── tests/                    ← Pytest suite
│   ├── requirements.txt
│   └── .env.example
│
├── flask_api/                    ← Platform API (consumed by Next.js)
│   ├── app.py                    ← Flask factory
│   ├── models.py                 ← SQLAlchemy models
│   ├── security.py               ← bcrypt + JWT + role decorators
│   ├── auth.py                   ← Registration, login, OTP, invitation
│   ├── admin.py                  ← Company validation
│   ├── manager.py                ← Fleet management
│   ├── driver.py                 ← Driver interface
│   ├── map_data.py               ← Live map aggregation
│   ├── map_tools.py              ← Simulated convoy positions
│   ├── seed.py                   ← Demo data seeding
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                     ← Next.js 14 web application
│   ├── app/                      ← App Router pages
│   │   ├── login/ register/ forgot-password/ set-password/
│   │   └── dashboard/
│   │       ├── admin/            ← Company approval (admin only)
│   │       ├── map/              ← Live convoy map
│   │       ├── cargos/ trackers/ drivers/ alerts/
│   │       ├── ai-decisions/     ← Agent decision audit trail
│   │       └── observatory/      ← Corridor risk monitoring
│   ├── components/               ← Shared UI components
│   ├── lib/
│   │   ├── api.ts                ← Axios instance
│   │   └── auth.ts               ← Session management
│   ├── package.json
│   └── tailwind.config.ts
│
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile
│   │   ├── flask-api.Dockerfile
│   │   └── frontend.Dockerfile
│   └── docker-compose.yml        ← 5 services: db, platform-db, flask-api, backend, frontend
│
└── docs/
    ├── raased_database_design.md ← Full DB schema documentation
    └── database_setup_guide.md   ← Alembic migration guide
```

---

## 8. How to Run the Project

### 8.1 With Docker Compose (recommended)

This starts all 5 services in one command.

```bash
# 1. Clone the repository
git clone <repo-url>
cd raased

# 2. Set up the agent backend environment
cp backend/.env.example backend/.env
# Edit backend/.env and fill in:
#   GEMINI_API_KEY=your_key
#   CAMARA_API_KEY=your_key

# 3. Start everything
cd infra
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Platform API (Flask) | http://localhost:5000 |
| Agent API (FastAPI) | http://localhost:8000 — Swagger at http://localhost:8000/docs |
| Agent DB (PostgreSQL+PostGIS) | localhost:5432 |
| Platform DB (PostgreSQL) | localhost:5433 |

The Flask API seeds demo data automatically on first start.

---

### 8.2 Manually — Platform (Flask + Next.js)

**Flask API (port 5000):**

```bash
cd flask_api
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DATABASE_URL (PostgreSQL or SQLite)

python app.py
# DB is created and seeded automatically on first start
```

**Next.js frontend (port 3000):**

```bash
cd frontend
npm install
npm run dev
```

---

### 8.3 Manually — Agent Engine (FastAPI)

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env — required keys below

# Run database migrations
alembic upgrade head

# Start the agent API
uvicorn app.main:app --reload
# Swagger UI: http://localhost:8000/docs
```

---

## 9. Environment Variables

Key variables for `backend/.env`:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://raased:raased@localhost:5432/raased` |
| `GEMINI_API_KEY` | Google Gemini API key (required for LLM reasoning) | — |
| `LLM_PROVIDER` | LLM backend: `gemini` / `groq` / `openai` | `gemini` |
| `GROQ_API_KEY` | Groq API key (if using Groq) | — |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | — |
| `CAMARA_API_KEY` | Nokia Network-as-Code API key | `CHANGE_ME` |
| `CAMARA_BASE_URL` | CAMARA API base URL | Nokia sandbox URL |
| `CAMARA_SANDBOX_MODE` | Use sandbox mode | `true` |
| `CONGESTION_ALERT_THRESHOLD` | Congestion level above which risk is raised | `0.7` |
| `CONGESTION_CONFIDENCE_MIN` | Minimum confidence score to trust a congestion reading | `0.6` |
| `SECRET_KEY` | JWT signing key | `CHANGE_ME_IN_PRODUCTION` |

Key variables for `flask_api/.env`:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL or SQLite connection string |
| `SECRET_KEY` | JWT signing key |
| `SMTP_HOST` | SMTP server (leave empty → OTP codes printed to console in dev) |

---

## 10. Demo Accounts

Pre-seeded by the Flask API on first start:

| Role | Email | Password |
|---|---|---|
| Admin | admin@raased.ma | Admin@123 |
| Manager (LogiTrans) | manager@logitrans.ma | Manager@123 |
| Manager (MediCargo) | manager@medicargo.ma | Manager@123 |
| Driver (LogiTrans) | driver@logitrans.ma | Driver@123 |
| Driver (MediCargo) | driver@medicargo.ma | Driver@123 |

Pending invitation accounts (for testing the activation flow):
- `salma.idrissi@logitrans.ma` — driver, no password yet
- `rachid.naciri@logitrans.ma` — manager, no password yet

---

## 11. Team

| Name | Role |
|---|---|
| Jihan Abiad | Project Manager & Frontend / Website Developer |
| Fatima Elmessaoudi | Backend Developer — API integration & system functionality |
| Safae Charuiti | Cybersecurity Specialist |
| Mohamed Errahmouni | Data Specialist |
| Nachda Nourouddine | Network Specialist |
