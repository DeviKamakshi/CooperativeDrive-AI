# 🚗 CooperativeDrive AI

> **Connected-Vehicle Cooperative Safety & Risk Reasoning Engine**  
> *Powered by IBM watsonx Orchestrate*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://python.org)
[![IBM watsonx](https://img.shields.io/badge/IBM_watsonx-Orchestrate-052FAD.svg?logo=ibm)](https://www.ibm.com/products/watsonx-orchestrate)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/Tests-41%20Passed-brightgreen.svg)]()

---

## 📌 Executive Summary

Modern vehicle sensors (cameras, radar, lidar) suffer from a critical physical constraint: **line of sight**. A stopped truck blocks the view of a crossing pedestrian, heavy fog obscures a highway pileup, a building blinds an intersection, and road curves hide stationary debris.

**CooperativeDrive AI** breaks this barrier using **Vehicle-to-Vehicle (V2V) Cooperative Perception** powered by **IBM watsonx Orchestrate**. When Car B detects a hazard invisible to Car A, Car B shares its raw observation. The CooperativeDrive cognitive agent reasons over Car A's telemetry, intended trajectory, and Car B's observation to issue targeted, life-saving warnings before Car A enters danger.

> *"What one car cannot see, another car can."*

---

## 🌟 Key Capabilities

### 1. 🧠 Live IBM watsonx Orchestrate Integration
- **Dual-Protocol Token Exchange**: Authenticates seamlessly with both standard IBM Cloud IAM (`iam.cloud.ibm.com`) and MCSP v2 SaaS (`account-iam.platform.saas.ibm.com`) with proactive in-memory caching.
- **Cognitive Risk Assessment**: Evaluates road observations against subject vehicle trajectory, outputting structured JSON:
  - `RISK`: `HIGH` | `MEDIUM` | `LOW`
  - `HAZARD`: Concise description of the hazard
  - `WARNING`: Actionable driver instruction
  - `REASON`: Clear explanation of the spatial/trajectory conflict
  - `SEND TO`: Vehicle recipient list (with recipient filtering)
  - `CONFIDENCE`: `HIGH` | `MEDIUM` | `LOW`
- **Deterministic Offline Resilience**: Built-in deterministic safety reasoning engine ensures zero demo downtime even during network latency or IBM proxy hiccups.

### 2. 🎥 Vision & Video Sampling Layer
- **Media Upload Support**: Accepts both high-resolution still images (`JPG`, `PNG`, `WebP`) and dashcam video clips (`MP4`, `WebM`, `MOV`, `AVI`, `MKV`).
- **Temporal Frame Sampling**: Samples 1 frame every 2.0s (up to 5 frames per clip), deduplicating redundant frames and tracking temporal evolution.
- **Embedded HTML5 Player & Timeline**: Inline video playback accompanied by interactive **Sampling Timeline Chips** detailing hazard appearance timestamps.
- **Strict Compliance**: The vision layer outputs *only* scene summaries and confidence scores; it never hallucinates synthetic telemetry or speed fields.

### 3. ⚡ 20 Canonical Benchmark Safety Scenarios
Pre-configured in the UI dropdown and test suite to demonstrate complete coverage:
- **Obstacles & Maneuver Conflicts**: Road debris during lane change, hidden pedestrian behind truck, hidden cyclist, curve obstruction, exit ramp blocked, overtaking conflict.
- **Merging & Intersections**: Highway merge conflict (TTC 1.4s), safe highway merge (6.0s gap proving Watson does not always say HIGH), simultaneous lane change, blind intersection.
- **Dynamic & Weather Hazards**: Sudden braking of preceding occluded vehicle, wrong-way driver approaching, construction lane closure, emergency vehicle approach, dense fog with stopped traffic.
- **Responsible AI & Edge Cases**: Conflicting sensor reports (uncertainty moderation), multi-vehicle consensus confidence boost, recipient filtering (irrelevant opposite-lane hazard), pedestrian on sidewalk non-conflict, completely safe clear road.

---

## 🏗️ Architecture

```
                                 [ CAR_B Vision Sensor ]
                                   (Dashcam / Camera)
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │    Vision Layer (OpenCV)  │
                             │  • Image & Video Sampling │
                             │  • Temporal Deduplication │
                             └─────────────┬─────────────┘
                                           │
                                           │ Compact Road Observation
                                           ▼
┌──────────────────────┐     ┌───────────────────────────┐     ┌────────────────────────────┐
│   CAR_A Telemetry    │────▶│    FastAPI Safety Core    │────▶│ IBM watsonx Orchestrate    │
│ (Speed, Lane, Maneuver)    │    (/api/assess)          │     │ (Multi-Agent Reasoning)    │
└──────────────────────┘     └─────────────┬─────────────┘     └─────────────┬──────────────┘
                                           │                                 │
                                           │ Driver Warning                  │ Structured Assessment
                                           │ (Actionable & Filtered)         │ (RISK, HAZARD, SEND TO)
                                           ▼                                 ▼
                             ┌───────────────────────────┐     ┌────────────────────────────┐
                             │ Minimalist Web Dashboard  │◀────│ Cached IAM / MCSP Token    │
                             │ (Dark Slate Automotive)   │     │ (High-Performance Exchange)│
                             └───────────────────────────┘     └────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/DeviKamakshi/CooperativeDrive-AI.git
cd CooperativeDrive-AI

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials

Copy the example environment configuration:

```bash
cp .env.example .env
```

Edit `.env` with your IBM watsonx Orchestrate credentials:

```ini
WXO_INSTANCE_URL=https://api.dl.watson-orchestrate.ibm.com/instances/your_instance_id
WXO_API_KEY=your_ibm_api_key
WXO_AGENT_ID=your_deployed_agent_id
```

*(Note: If IBM credentials are not provided or the instance is unreachable, CooperativeDrive AI seamlessly falls back to its deterministic local safety engine).*

### 3. Run the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at: **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Testing

The repository includes a comprehensive 41-test automated suite covering API endpoints, IAM token caching, response parsing, video sampling, and all 20 benchmark scenarios:

```bash
PYTHONPATH=. pytest -v
```

Output:
```text
tests/test_api.py ...............                                        [ 36%]
tests/test_parser.py .....                                               [ 48%]
tests/test_scenarios.py .....................                            [100%]

======================== 41 passed, 1 warning in 3.12s =========================
```

---

## 📡 REST API Reference

### `GET /api/status`
Checks connectivity to IBM watsonx Orchestrate.
```json
{
  "status": "CONNECTED",
  "message": "Connected to IBM watsonx Orchestrate",
  "configured": true
}
```

### `GET /api/scenarios`
Returns the 20 benchmark connected-vehicle scenarios with vehicle context, observations, and expected risks.

### `POST /api/assess`
Evaluates a cooperative driving situation. Supports both `application/json` and `multipart/form-data` (with image or video upload).

**Payload**:
- `vehicle_id` *(str)*: e.g. `"CAR_A"`
- `speed` *(str)*: e.g. `"60 mph"`
- `current_lane` *(str)*: e.g. `"2"`
- `target_lane` *(str)*: e.g. `"3"`
- `direction` *(str)*: e.g. `"EAST"`
- `intended_maneuver` *(str)*: e.g. `"CHANGE_RIGHT"`
- `source_vehicle` *(str)*: e.g. `"CAR_B"`
- `observation` *(str)*: Road text observation
- `video` or `image` *(file, optional)*: Attached road scene media

**Response**:
```json
{
  "risk": "HIGH",
  "hazard": "Road debris ahead in lane 3",
  "warning": "Debris ahead - remain in current lane.",
  "reason": "Intended lane change intersects road obstacle.",
  "recipients": ["CAR_A"],
  "confidence": "HIGH",
  "technical_details": {
    "connection_status": "CONNECTED",
    "observation_sent": "...",
    "raw_ibm_response": "..."
  }
}
```

---

## 💡 The 20 Benchmark Scenarios Summary

| # | Scenario | Intended Maneuver | Expected Risk | Core Demonstration |
|---|---|---|:---:|---|
| 1 | Road debris during lane change | `CHANGE_RIGHT` | **HIGH** | Lane-change conflict |
| 2 | Hidden pedestrian during right turn | `TURN_RIGHT` | **HIGH** | Occlusion behind truck |
| 3 | Hidden cyclist during lane change | `CHANGE_RIGHT` | **HIGH** | Vulnerable road user protection |
| 4 | Highway merge conflict | `MERGE` | **HIGH** | Critical TTC ($< 3\text{s}$) |
| 5 | Safe highway merge | `MERGE` | **LOW** | Proves Watson does not always flag HIGH |
| 6 | Simultaneous lane change | `CHANGE_RIGHT` | **HIGH** | Dual-vehicle lane conflict |
| 7 | Blind intersection | `ENTER_INTERSECTION` | **HIGH** | Building-blocked cross traffic |
| 8 | Sudden braking ahead | `KEEP_LANE` | **HIGH** | Occluded lead-vehicle deceleration |
| 9 | Wrong-way vehicle | `KEEP_LANE` | **HIGH** | Head-on collision avoidance |
| 10 | Stopped vehicle around a curve | `KEEP_LANE` | **HIGH** | Beyond-line-of-sight cooperative alert |
| 11 | Construction / lane closure | `KEEP_LANE` | **HIGH** | Lane blockage preparation |
| 12 | Emergency vehicle approaching | `KEEP_LANE` | **MEDIUM** | Priority right-of-way awareness |
| 13 | Conflicting sensor reports | `CHANGE_RIGHT` | **MEDIUM** | Responsible AI uncertainty moderation |
| 14 | Multi-vehicle confirmation | `CHANGE_RIGHT` | **HIGH** | Consensus confidence elevation |
| 15 | Irrelevant opposite-lane hazard | `KEEP_LANE` | **LOW** | Recipient filtering (`SEND TO: NONE`) |
| 16 | Pedestrian safe on sidewalk | `KEEP_LANE` | **LOW** | Non-conflicting pedestrian |
| 17 | Poor visibility + hidden stopped traffic | `KEEP_LANE` | **HIGH** | Fog occlusion penetration |
| 18 | Highway exit blocked | `EXIT` | **HIGH** | Blocked exit ramp avoidance |
| 19 | Overtaking conflict | `OVERTAKE` | **HIGH** | Oncoming car occluded by curve |
| 20 | Completely safe road | `KEEP_LANE` | **LOW** | Routine clear travel |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
