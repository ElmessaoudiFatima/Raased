# Raased (راصد) — AI Agent for Logistics Corridor Resilience

> **Raased** means *"observer"* or *"watcher"* in Arabic. It is an autonomous AI agent that turns
> mobile network signals into an early-warning and corrective system for critical freight moving
> through MENA logistics corridors.

Built for the **GSMA MENA Ignite Hackathon** — GSMA Open Gateway Innovation Challenge, Theme 7
(Open Innovation).

---

## 1. Problem

Logistics platforms operating in MENA's highest-risk corridors face two compounding issues:

1. **Blind spots : ** Traditional data feeds (road-traffic sensors, GPS, weather) are delayed,
   incomplete, or simply unavailable in isolated, contested, or remote border zones.
2. **No fast corrective lever :** Even when a disruption is eventually detected, logistics
   platforms have no immediate way to protect the shipments already in transit through the
   affected corridor.

## 2. What Raased Does

Raased treats the **mobile network itself as a real-time risk sensor** — not just a
communication pipe — by continuously consuming CAMARA telecom APIs, and acts as an autonomous
decision-making agent rather than a passive dashboard:

1. **Ingests** real-time congestion signals for trackers moving through monitored corridors.
2. **Contextualizes** each signal against geospatial data and historical baselines, to tell a
   genuine disruption (security incident, road blockage, local crisis) apart from ordinary
   crowding (a stadium event, routine urban density).
3. **Classifies** the situation: `normal → event → incident → crisis`.
4. **Verifies trust**: runs Number Verification / SIM Swap / Device Swap checks so the agent
   never acts on a compromised or spoofed tracker signal.
5. **Acts autonomously**, within guardrails:
   - Alerts logistics operators with a plain-language, auditable explanation.
   - Suggests alternative routing.
   - Requests **Quality on Demand (QoD)** to secure tracking telemetry for critical cargo.
   - Requests **Network Slicing** for the most severe (crisis-level) cases.
   - Escalates to a human for approval whenever trust checks fail or the situation is
     classified as `crisis`.

---

## 3. Architecture

```
                         ┌────────────────────────────┐
                         │   Driver / Administrator   │
                         │  (Next.js dashboard, web)  │
                         └──────────────┬─────────────┘
                                        │ HTTPS
                                        ▼
                       ┌──────────────────────────────────┐
                       │        FastAPI Backend           │
                       │  (Auth, RBAC, orgs, corridors,   │
                       │   trackers, alerts, audit log)   │
                       └───────┬────────────────┬─────────┘
                               │                │
                 ┌─────────────┘                └─────────────┐
                 ▼                                            ▼
    ┌───────────────────────────┐                 ┌──────────────────────────────┐
    │     Verification Layer    │                 │        Agent Layer           │
    │ Number Verification / SIM │◄───────────────►│  LangGraph pipeline:         │
    │ Swap / Device Swap checks │                 │  fetch congestion → location │
    └────────────┬──────────────┘                 │  → geospatial context →      │
                 │                                │  trust checks → rules engine │
                 ▼                                │  → LLM explanation → act     │
    ┌────────────────────────────┐                └───────────────┬──────────────┘
    │   CAMARA / Nokia Network-  │                                │
    │   as-Code Integration      │◄───────────────────────────────┘
    │ Congestion Insights,       │
    │ Location Retrieval,        │
    │ Geofencing, QoD, Slicing   │
    └────────────┬───────────────┘
                 │ webhooks / REST
                 ▼
    ┌───────────────────────────┐        ┌───────────────────────────┐
    │   Data & Spatial Layer    │        │   Compliance & Audit Log  │
    │ PostgreSQL + PostGIS      │        │ Append-only, hashed,      │
    │ (corridors, risk zones,   │        │ timestamped decision trail│
    │  trackers, events)        │        └───────────────────────────┘
    └───────────────────────────┘
```

## 4. How the AI Agent Works

/* To be completed later */

## 5. CAMARA APIs Used

### Core situational-awareness APIs

| API | Used For | Why the Agent Needs It |
|---|---|---|
| **Congestion Insights** | Detecting a risk of connectivity degradation for a tracker. | Returns a congestion level + confidence score, used as the primary early-warning signal — often before road-traffic or weather data shows anything. |
| **Location Retrieval** | Obtaining an approximate network-based location. | Returns a location *area*, not exact GPS; the agent cross-references it against corridor risk zones to judge proximity to danger. |
| **Geofencing** | Triggering alerts when a tracker enters a sensitive zone. | Pushes a real-time event (port, border, customs, incident area) instead of requiring the agent to poll location repeatedly. |
| **Quality on Demand (QoD)** | Temporarily prioritizing a tracker's connectivity. | Once risk is confirmed on critical cargo, secures more reliable telemetry reporting exactly when it matters most. |
| **Network Slicing** | Reserving dedicated network resources. | For crisis-level cases, guarantees service continuity beyond what QoD alone provides. |

### Trust & security layer

| API | Used For | Why the Agent Needs It |
|---|---|---|
| **Number Verification** | Confirming the declared MSISDN matches the expected tracker. | Prevents fraudulently associating a shipment with the wrong mobile line at enrollment. |
| **SIM Swap** | Detecting a recent SIM change. | Flags a potential compromise before the agent trusts data reported by that tracker. |
| **Device Swap** | Detecting a physical device replacement. | Adds a safeguard against hardware spoofing or unauthorized terminal replacement. |


---

## 6. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React) + TailwindCSS |
| Backend | FastAPI (Python)|
| Agent orchestration | LangGraph |
| LLM reasoning | /* To be completed later */ |
| Database | PostgreSQL + PostGIS  |
| External APIs | CAMARA (via Nokia Network-as-Code sandbox) |
| Infra | Docker Compose (db, backend, frontend), GitHub Actions CI |

---

## 7. Repository Structure

```
raased/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI entrypoint
│   │   ├── core/config.py         # Settings (env-driven)
│   │   ├── api/v1/                # Routers: health, agent/assess
│   │   ├── agent/                 # Rules engine, LLM reasoning
│   │   ├── camara/                # CAMARA API wrappers (congestion, location, geofencing,
│   │   │                          #   qod, slicing, trust/number/sim/device)
│   │   ├── services/               # Geospatial context, network actions, audit log
│   │   ├── models/                 # SQLAlchemy models (corridors, trackers, events, alerts)
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   └── db/                     # Async session + declarative base
│   ├── tests/                      # Pytest suite (rules engine covered)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/                        # Next.js App Router (dashboard page, layout)
│   ├── components/                 # AlertBadge, etc.
│   ├── lib/api.ts                  # Typed API client
│   ├── package.json
│   └── tailwind.config.ts
├── infra/
│   ├── docker/                     # Backend + frontend Dockerfiles
│   └── docker-compose.yml
├── docs/                           # Additional documentation, diagrams
├── 
└── README.md
```

---

## 8. Running Locally

### With Docker Compose (recommended)

```bash
cd infra
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:3000
- PostgreSQL+PostGIS: `localhost:5432`

### Manually

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your CAMARA_API_KEY and an LLM provider key
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

---

## 9. Team — Novatech

| Name | Role |
|---|---|
| Jihan Abiad | Project Manager & Frontend/Website Developer |
| Fatima Elmessaoudi | Backend Developer — API integration & system functionality |
| Safae Charuiti | Cybersecurity Specialist |
| Mohamed Errahmouni | Data Specialist |
| Nachda Nourouddine | Network Specialist |

---


