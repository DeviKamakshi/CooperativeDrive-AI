# CooperativeDrive AI

**SpartHill Hacks 2026 — IBM AI Challenge**

A cooperative vehicle awareness research prototype demonstrating how vehicles can share observations, hazards, and driving intentions so other vehicles can know about risks beyond their own field of view.

> **What one vehicle cannot see, another vehicle can.**

---

## ⚠ Important Notice

All vehicle telemetry is **synthetic simulated data**. This is a research/hackathon prototype — not production autonomous-driving software. No real vehicle hardware is used. The system does not control any vehicle.

---

## Core Architecture

```
  [Vehicle A]          [Vehicle B]          [Vehicle C]
  Telemetry            Telemetry            Telemetry
  Vision (watsonx)     Intent signals       Hazard reports
       │                    │                    │
       ▼                    ▼                    ▼
  ┌─────────────────────────────────────────────────┐
  │              VehicleAgent                        │
  │  Braking detector · Intent tracker · Zone check │
  └───────────────────────┬─────────────────────────┘
                          │  CooperativeMessages
                          ▼
  ┌─────────────────────────────────────────────────┐
  │           RelevanceFilter                        │
  │  Segment · Distance · Lane · Direction · Zone   │
  └───────────────────────┬─────────────────────────┘
                          │  Filtered messages
                          ▼
  ┌─────────────────────────────────────────────────┐
  │           EvidenceFusion                         │
  │  Confirmation chain · Conflict detection        │
  │  Reliability-weighted confidence               │
  └───────────────────────┬─────────────────────────┘
                          │  HazardRecord
                          ▼
  ┌─────────────────────────────────────────────────┐
  │    RiskEngine  (DETERMINISTIC — always runs)    │
  │  TTC · severity · freshness · intent conflict   │
  │  → LOW / MEDIUM / HIGH                         │
  └───────────────────────┬─────────────────────────┘
                          │  RiskResult
                          ▼
  ┌─────────────────────────────────────────────────┐
  │    watsonx Explainer  (ENHANCEMENT — optional)  │
  │  Natural-language explanation of risk result    │
  │  → Falls back to deterministic text if offline │
  └───────────────────────┬─────────────────────────┘
                          │
                          ▼
              ┌───────────────────┐
              │   FastAPI + WS    │
              │  Dashboard (SPA)  │
              └───────────────────┘
```

---

## Key Design Principles

1. **Deterministic safety classification** — The risk engine always produces LOW/MEDIUM/HIGH. IBM watsonx.ai never overrides it.
2. **Targeted cooperative communication** — Vehicles only communicate when relevant (in a ManeuverZone or during an active maneuver). Messages are filtered to affected vehicles only.
3. **Evidence fusion** — Multiple vehicle reports are combined transparently. Conflicting evidence is retained and shown — not hidden or averaged away.
4. **Responsible AI** — Uncertainty is displayed. Sources are labelled. Human driver remains responsible.
5. **Graceful degradation** — The system functions fully if watsonx Vision or the explanation API is unavailable.

---

## Quick Start

### Requirements

- Python 3.11+
- pip

### Setup

```bash
git clone <repo>
cd cooperative-drive
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your IBM watsonx credentials (optional — fallbacks active without them)
python scripts/generate_placeholder_images.py
python run.py
```

Open: http://localhost:8000

### IBM watsonx Configuration (optional)

Edit `.env`:

```
WATSONX_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

Without credentials, the system uses deterministic fallbacks for all AI features.

---

## 8 Priority Demonstrations

| # | Scenario | Key Concept | Expected Risk |
|---|----------|-------------|---------------|
| 1 | Hidden Pedestrian | Vision + occlusion detection | HIGH |
| 2 | Highway Merge | TTC-based conflict detection | HIGH |
| 3 | Simultaneous Lane Change | Intent sharing (no visual hazard) | HIGH |
| 4 | Blind Intersection | Cooperative awareness beyond LoS | HIGH |
| 5 | Sudden Braking Chain | Real-time event propagation | HIGH |
| 6 | Wrong-Way Vehicle | Directional relevance filtering | HIGH |
| 7 | Road Debris | Multi-vehicle confirmation chain | HIGH |
| 8 | Conflicting Reports | Responsible AI / uncertainty | MEDIUM |

---

## Dashboard Guide

The dashboard shows six panels:

- **Bird's-Eye Map** — Real-time vehicle positions, maneuver zones, hazard markers, message arcs
- **Camera View** — Prerecorded road image with scene analysis (Demo 1, 2, 7, 8)
- **Vehicle State** — Position, speed, lane, intended maneuver
- **Risk Panel** — Current LOW/MEDIUM/HIGH determination with confidence and TTC
- **watsonx Explanation** — Natural-language explanation (or deterministic fallback)
- **Cooperative Communications** — Live message log with source, recipient, priority
- **Hazard Registry** — Active hazards with confirmation chain and status

### Information Source Badges

Every data point is labelled:
- 🔵 **VISION-DERIVED** — from image analysis
- 🟢 **TELEMETRY-DERIVED** — from vehicle sensors/telemetry
- 🟡 **SYNTHETIC/SCENARIO-DERIVED** — injected by scenario definition

---

## Architecture

### Modules

| Module | Responsibility |
|--------|---------------|
| `core/ttc.py` | Time-to-conflict mathematics |
| `core/hazard_expiry.py` | Freshness decay and expiry |
| `core/reliability_tracker.py` | Per-vehicle reliability scores |
| `core/maneuver_zone.py` | Cooperative sharing zone logic |
| `core/evidence_fusion.py` | Multi-vehicle confirmation and conflict |
| `core/risk_engine.py` | **Deterministic LOW/MEDIUM/HIGH** |
| `core/relevance_filter.py` | Which vehicles receive a message |
| `core/vehicle_agent.py` | Per-vehicle communication decisions |
| `core/scene_analyzer.py` | Vision dispatch + fallback |
| `watsonx/client.py` | IBM watsonx.ai REST client |
| `watsonx/vision.py` | Road image analysis |
| `watsonx/explainer.py` | Natural-language explanation |
| `scenarios/` | Simulation framework + 8 demos |
| `api/` | FastAPI endpoints + WebSocket |
| `static/` | Single-page dashboard |

---

## Running Tests

```bash
pytest tests/ -v
```

135 tests across: TTC math, hazard expiry, reliability, evidence fusion, risk engine, relevance filter, vehicle agent, scene analyzer, watsonx explainer, watsonx vision, all 8 scenarios, API layer.

---

## Responsible AI

- Human driver remains responsible — system provides awareness only
- No vehicle actuation or steering control
- Deterministic safety classification — watsonx cannot change risk level
- Uncertainty displayed — confidence shown on every hazard
- Conflicting evidence retained and shown
- Stale information removed (configurable expiry)
- Evidence sources labelled on every data point
- Privacy-conscious — compact structured messages only, no raw video
- Graceful degradation — fully functional without watsonx

---

## Configuration

All thresholds configurable via `.env` (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `RISK_HIGH_THRESHOLD` | Score threshold for HIGH risk |
| `RISK_MEDIUM_THRESHOLD` | Score threshold for MEDIUM risk |
| `HAZARD_FULL_FRESHNESS_SECONDS` | Age below which freshness=1.0 |
| `HAZARD_EXPIRY_SECONDS` | Age at which hazard is expired |
| `BRAKING_THRESHOLD_G` | Deceleration threshold for sudden-braking detection |
| `CONFLICT_WINDOW_SECONDS` | Time window for intent-conflict detection |
| `MANEUVER_ZONE_RADIUS_METERS` | Radius of cooperative sharing zone |
| `RELEVANCE_FILTER_MAX_DISTANCE` | Maximum distance for message relevance |
| `TTC_LOOKAHEAD_SECONDS` | Look-ahead horizon for TTC computation |

---

## Technology Stack

- **Python 3.11**, **FastAPI**, **Pydantic v2**, **uvicorn**
- **IBM watsonx.ai** (text generation + vision)
- **Vanilla HTML/CSS/JavaScript** (no frontend framework)
- **HTML5 Canvas** (bird's-eye map)
- **WebSocket** (real-time dashboard updates)
