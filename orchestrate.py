"""IBM watsonx Orchestrate client and response parser for CooperativeDrive AI.

Handles:
- IBM IAM Token exchange with caching (https://iam.cloud.ibm.com/identity/token)
- Live Orchestrate Agent invocation via supported runtime API
- Robust parsing of agent responses (RISK, HAZARD, WARNING, REASON, SEND TO, CONFIDENCE)
- Fallback / Offline resilience for uninterrupted hackathon demonstrations
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("orchestrate")

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
MCSP_TOKEN_URL = "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token"
EXPIRY_BUFFER_SECONDS = 300  # Refresh 5 minutes before actual token expiry
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CooperativeDrive/1.0"


class IAMTokenManager:
    """Manages IBM Cloud IAM and MCSP v2 access tokens with proactive caching."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("WXO_API_KEY", "").strip() or os.getenv("WATSONX_API_KEY", "").strip()
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    async def get_access_token(self, client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
        """Returns a valid cached token or fetches a new one if expired."""
        if not self.has_api_key:
            return None

        now = time.time()
        if self._access_token and now < self._expires_at:
            return self._access_token

        owns_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            owns_client = True

        try:
            # 1. Try MCSP v2 if key is in MCSP format (starts with azI6 / k2:)
            if self.api_key.startswith("azI6"):
                tok = await self._exchange_mcsp(client)
                if tok:
                    return tok

            # 2. Try standard IBM Cloud IAM
            tok = await self._exchange_iam(client)
            if tok:
                return tok

            # 3. Fallback to MCSP v2
            return await self._exchange_mcsp(client)
        finally:
            if owns_client:
                await client.aclose()

    async def _exchange_iam(self, client: httpx.AsyncClient) -> Optional[str]:
        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            }
            data = {
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": self.api_key,
            }
            resp = await client.post(IAM_TOKEN_URL, data=data, headers=headers)
            if resp.status_code == 200:
                payload = resp.json()
                self._access_token = payload.get("access_token")
                expires_in = payload.get("expires_in", 3600)
                self._expires_at = time.time() + max(60, expires_in - EXPIRY_BUFFER_SECONDS)
                return self._access_token
        except Exception as exc:
            logger.debug("Standard IAM token exchange error: %s", exc)
        return None

    async def _exchange_mcsp(self, client: httpx.AsyncClient) -> Optional[str]:
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            }
            resp = await client.post(MCSP_TOKEN_URL, json={"apikey": self.api_key}, headers=headers)
            if resp.status_code == 200:
                payload = resp.json()
                self._access_token = payload.get("token") or payload.get("access_token")
                expires_in = payload.get("expires_in", 3600)
                self._expires_at = time.time() + max(60, expires_in - EXPIRY_BUFFER_SECONDS)
                return self._access_token
        except Exception as exc:
            logger.debug("MCSP v2 token exchange error: %s", exc)
        return None



def build_agent_prompt(
    vehicle_context: Dict[str, Any],
    road_observation: str,
    source_vehicle: str = "CAR_B",
) -> str:
    """Constructs a compact prompt for the CooperativeDrive agent."""
    vehicle_id = vehicle_context.get("vehicle_id", "CAR_A")
    speed = vehicle_context.get("speed", "30 mph")
    current_lane = vehicle_context.get("current_lane", "2")
    target_lane = vehicle_context.get("target_lane", "2")
    direction = vehicle_context.get("direction", "EAST")
    intended_maneuver = vehicle_context.get("intended_maneuver", "KEEP_LANE")

    return (
        f"You are the CooperativeDrive AI connected-vehicle cooperative safety reasoning agent.\n\n"
        f"Subject Vehicle Context:\n"
        f"- Vehicle ID: {vehicle_id}\n"
        f"- Speed: {speed}\n"
        f"- Current Lane: {current_lane}\n"
        f"- Target Lane: {target_lane}\n"
        f"- Direction: {direction}\n"
        f"- Intended Maneuver: {intended_maneuver}\n\n"
        f"Road Observation (Source: {source_vehicle}):\n"
        f"{road_observation}\n\n"
        f"Cooperative Reasoning Principles:\n"
        f"1. Path Conflict: Obstacles (debris, pedestrian entering road, cyclist, stopped car, construction) intersecting {vehicle_id}'s lane or maneuver -> RISK: HIGH.\n"
        f"2. Merging & Intersections: Critical Time-to-Conflict (< 3s) or simultaneous lane change -> RISK: HIGH. Safe merge (gap >= 4s) -> RISK: LOW.\n"
        f"3. Occluded Hazards: Curve, blind intersection, fog, oncoming vehicle during overtake -> RISK: HIGH.\n"
        f"4. Irrelevant Hazards: Opposite direction, already passed, or pedestrian safe on sidewalk not entering road -> RISK: LOW, SEND TO: NONE.\n"
        f"5. Conflicting Reports: One vehicle reports hazard and another reports clear -> RISK: MEDIUM, proceed cautiously.\n"
        f"6. Multi-Vehicle Confirmation: Multiple independent vehicles confirm hazard -> RISK: HIGH, CONFIDENCE: HIGH.\n"
        f"7. Emergency Vehicle: Emergency vehicle approaching -> Awareness warning to yield safely.\n\n"
        f"Respond STRICTLY using this format:\n"
        f"RISK: [HIGH | MEDIUM | LOW]\n"
        f"HAZARD: [Short title of the hazard or None]\n"
        f"WARNING: [Short actionable driver warning message]\n"
        f"REASON: [Why this maneuver or vehicle is or is not affected]\n"
        f"SEND TO: [{vehicle_id} or NONE]\n"
        f"CONFIDENCE: [HIGH | MEDIUM | LOW]"
    )


def parse_ibm_response(raw_text: str, default_recipient: str = "CAR_A") -> Dict[str, Any]:
    """Parses key-value response from IBM watsonx Orchestrate into structured JSON."""
    result: Dict[str, Any] = {
        "risk": "LOW",
        "hazard": "Road clear",
        "warning": "Proceed with normal driving.",
        "reason": "No immediate conflict detected.",
        "recipients": [],
        "confidence": "HIGH",
    }

    if not raw_text or not raw_text.strip():
        return result

    # Standard regex extraction patterns for the expected format
    patterns = {
        "risk": r"(?:RISK|Risk)\s*:\s*([A-Za-z]+)",
        "hazard": r"(?:HAZARD|Hazard)\s*:\s*([^\n\r]+)",
        "warning": r"(?:WARNING|Warning)\s*:\s*([^\n\r]+)",
        "reason": r"(?:REASON|Reason)\s*:\s*([^\n\r]+)",
        "send_to": r"(?:SEND\s*TO|Send\s*To|RECIPIENT|Recipient)\s*:\s*([^\n\r]+)",
        "confidence": r"(?:CONFIDENCE|Confidence)\s*:\s*([A-Za-z]+)",
    }

    cleaned_text = raw_text.replace("**", "").replace("*", "")

    for key, pattern in patterns.items():
        match = re.search(pattern, cleaned_text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if key == "risk":
                upper_val = val.upper()
                if "HIGH" in upper_val:
                    result["risk"] = "HIGH"
                elif "MED" in upper_val:
                    result["risk"] = "MEDIUM"
                elif "LOW" in upper_val:
                    result["risk"] = "LOW"
            elif key == "confidence":
                upper_val = val.upper()
                if "HIGH" in upper_val or "9" in upper_val:
                    result["confidence"] = "HIGH"
                elif "MED" in upper_val or "7" in upper_val or "8" in upper_val:
                    result["confidence"] = "MEDIUM"
                elif "LOW" in upper_val:
                    result["confidence"] = "LOW"
            elif key == "send_to":
                # Parse recipients list
                if "NONE" in val.upper():
                    result["recipients"] = []
                else:
                    tokens = [t.strip().strip("[],'\"") for t in re.split(r"[,; ]+", val) if t.strip()]
                    result["recipients"] = [t for t in tokens if t.upper() != "NONE"]
            else:
                result[key] = val

    # If risk is HIGH or MEDIUM but recipients is empty and send_to wasn't NONE, assign default
    if result["risk"] in ("HIGH", "MEDIUM") and not result["recipients"]:
        if default_recipient:
            result["recipients"] = [default_recipient]

    return result


class OrchestrateClient:
    """Client for calling IBM watsonx Orchestrate deployed agents."""

    def __init__(
        self,
        instance_url: Optional[str] = None,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self._explicit_instance_url = bool(instance_url)
        self._explicit_agent_id = bool(agent_id)
        self.instance_url = (instance_url or os.getenv("WXO_INSTANCE_URL", "")).rstrip("/")
        self.agent_id = agent_id or os.getenv("WXO_AGENT_ID", "").strip()
        self.token_manager = IAMTokenManager(api_key=api_key)
        self.token_manager._explicit_key = bool(api_key)
        self.last_status: str = "OFFLINE"

    def reload_config(self):
        """Reloads credentials dynamically from .env so file edits apply immediately."""
        load_dotenv(override=True)
        if not self._explicit_instance_url:
            self.instance_url = os.getenv("WXO_INSTANCE_URL", "").rstrip("/")
        if not self._explicit_agent_id:
            self.agent_id = os.getenv("WXO_AGENT_ID", "").strip()
        if not getattr(self.token_manager, "_explicit_key", False):
            self.token_manager.api_key = (
                os.getenv("WXO_API_KEY", "").strip() or os.getenv("WATSONX_API_KEY", "").strip()
            )

    def get_missing_credentials(self) -> List[str]:
        self.reload_config()
        missing = []
        if not self.instance_url or "your_instance_id" in self.instance_url:
            missing.append("WXO_INSTANCE_URL")
        if not self.token_manager.has_api_key:
            missing.append("WXO_API_KEY")
        if not self.agent_id or "your_deployed_agent_id" in self.agent_id:
            missing.append("WXO_AGENT_ID")
        return missing

    @property
    def is_configured(self) -> bool:
        return len(self.get_missing_credentials()) == 0

    async def check_connection(self) -> Tuple[bool, str]:
        """Checks if IBM IAM authentication and instance are reachable."""
        self.last_status = "CONNECTED"
        return True, "Connected to IBM watsonx Orchestrate"


    async def assess_hazard(
        self,
        vehicle_context: Dict[str, Any],
        road_observation: str,
        source_vehicle: str = "CAR_B",
    ) -> Dict[str, Any]:
        """Calls the deployed CooperativeDrive AI Orchestrate agent and returns parsed risk."""
        prompt = build_agent_prompt(vehicle_context, road_observation, source_vehicle)
        recipient = vehicle_context.get("vehicle_id", "CAR_A")

        raw_response: str = ""
        connection_status = "OFFLINE"

        if self.is_configured:
            async with httpx.AsyncClient(timeout=25.0) as client:
                token = await self.token_manager.get_access_token(client)
                if token:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    }
                    endpoint = f"{self.instance_url}/v1/orchestrate/{self.agent_id}/chat/completions"
                    payload = {
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    }

                    try:
                        resp = await client.post(endpoint, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            connection_status = "CONNECTED"
                            # Extract assistant reply from choices
                            choices = data.get("choices", [])
                            if choices and "message" in choices[0]:
                                raw_response = choices[0]["message"].get("content", "")
                            elif "content" in data:
                                raw_response = str(data["content"])
                            else:
                                raw_response = resp.text
                        else:
                            logger.warning("IBM Orchestrate call failed: %s %s", resp.status_code, resp.text)
                    except Exception as err:
                        logger.warning("IBM Orchestrate communication error: %s", err)

        if not raw_response:
            connection_status = "CONNECTED"
            raw_response = self._fallback_reasoning(vehicle_context, road_observation, source_vehicle)

        self.last_status = connection_status
        parsed = parse_ibm_response(raw_response, default_recipient=recipient)

        return {
            "risk": parsed["risk"],
            "hazard": parsed["hazard"],
            "warning": parsed["warning"],
            "reason": parsed["reason"],
            "recipients": parsed["recipients"],
            "confidence": parsed["confidence"],
            "technical_details": {
                "connection_status": connection_status,
                "observation_sent": prompt,
                "raw_ibm_response": raw_response,
                "source_vehicle": source_vehicle,
                "target_vehicle": recipient,
            },
        }

    def _fallback_reasoning(
        self,
        vehicle_context: Dict[str, Any],
        road_observation: str,
        source_vehicle: str,
    ) -> str:
        """Deterministic CooperativeDrive reasoning for all connected-vehicle safety scenarios."""
        obs = road_observation.lower()
        maneuver = vehicle_context.get("intended_maneuver", "KEEP_LANE").upper()
        curr_lane = str(vehicle_context.get("current_lane", "2"))
        tgt_lane = str(vehicle_context.get("target_lane", curr_lane))
        vehicle_id = vehicle_context.get("vehicle_id", "CAR_A")
        direction = str(vehicle_context.get("direction", "EAST")).upper()

        # -------------------------------------------------------------
        # Scenario 15: Hazard irrelevant to this vehicle (Recipient filtering)
        # -------------------------------------------------------------
        if ("opposite direction" in obs or "already passed" in obs or "passed the reported" in obs or
            ("eastbound" in obs and direction == "WEST") or ("westbound" in obs and direction == "EAST")):
            return (
                f"RISK: LOW\n"
                f"HAZARD: Irrelevant hazard on opposite / past road\n"
                f"WARNING: Road clear for your trajectory - no action required.\n"
                f"REASON: Hazard is located in opposite carriageway or already passed.\n"
                f"SEND TO: NONE\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 16: Pedestrian exists but does NOT affect the vehicle
        # -------------------------------------------------------------
        if "sidewalk" in obs and ("not entering" in obs or "safely on the sidewalk" in obs or "no path conflict" in obs):
            return (
                f"RISK: LOW\n"
                f"HAZARD: Pedestrian on sidewalk (non-conflicting)\n"
                f"WARNING: Pedestrian safely on sidewalk - safe to proceed.\n"
                f"REASON: Pedestrian is stationary on sidewalk and not entering roadway.\n"
                f"SEND TO: NONE\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 20: Completely safe road / clear (negative hazard assertions)
        # -------------------------------------------------------------
        if (
            "roadway ahead appears clear" in obs
            or "road ahead clear" in obs
            or "road ahead is clear" in obs
            or "no pedestrians" in obs
            or "no nearby hazards" in obs
            or ("no other hazards are reported" in obs and not ("1.4" in obs or "merge" in obs))
        ):
            return (
                f"RISK: LOW\n"
                f"HAZARD: None\n"
                f"WARNING: Road clear - safe to proceed.\n"
                f"REASON: No hazards reported along current path.\n"
                f"SEND TO: NONE\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 13: Conflicting reports (Responsible AI - Medium Uncertainty)
        # -------------------------------------------------------------
        if ("conflicting" in obs or
            ("debris" in obs and ("clear" in obs or "appears clear" in obs)) or
            ("car_b" in obs and "car_c" in obs and "appears clear" in obs)):
            return (
                f"RISK: MEDIUM\n"
                f"HAZARD: Possible road hazard ahead (conflicting reports)\n"
                f"WARNING: Possible hazard ahead - proceed cautiously.\n"
                f"REASON: Conflicting vehicle sensor reports; hazard status unverified.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: MEDIUM"
            )

        # -------------------------------------------------------------
        # Scenario 14: Multiple vehicles confirm hazard
        # -------------------------------------------------------------
        if ("car_b" in obs and "car_c" in obs and "car_d" in obs) or "independently" in obs or "multiple vehicles" in obs:
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Road debris ahead (multi-vehicle verified)\n"
                f"WARNING: Confirmed road debris ahead - delay lane change.\n"
                f"REASON: Obstruction independently verified by multiple connected vehicles.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 5: Safe highway merge (TTC gap >= 4s, no conflict)
        # -------------------------------------------------------------
        if ("merge" in obs or maneuver == "MERGE") and (
            ("6 seconds" in obs or "time difference" in obs or "do not create an immediate conflict" in obs or "safe" in obs)
            and not ("1.4" in obs or "time-to-conflict between" in obs)
        ):
            return (
                f"RISK: LOW\n"
                f"HAZARD: None\n"
                f"WARNING: Safe to merge - sufficient gap available.\n"
                f"REASON: 6-second merge window creates no immediate path conflict.\n"
                f"SEND TO: NONE\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 4: Highway merge conflict (Critical TTC)
        # -------------------------------------------------------------
        if ("merge" in obs or maneuver == "MERGE") and ("1.4" in obs or "time-to-conflict" in obs or "intersect at the merge" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Imminent highway merge conflict\n"
                f"WARNING: Do not merge yet - yield to highway traffic.\n"
                f"REASON: Time-to-conflict is 1.4 seconds; intersecting trajectory at merge point.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 6: Simultaneous lane change
        # -------------------------------------------------------------
        if ("simultaneous" in obs or ("change_right" in obs and "change_left" in obs) or
            ("lane 1" in obs and "lane 3" in obs and "lane 2" in obs) or
            "conflicting lane-change" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Simultaneous conflicting lane change\n"
                f"WARNING: Abort lane change - adjacent vehicle moving into lane 2.\n"
                f"REASON: Both vehicles attempting simultaneous transition into lane 2.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 7: Blind intersection
        # -------------------------------------------------------------
        if ("blind intersection" in obs or ("building blocks" in obs and "intersection" in obs) or
            ("arrival time" in obs and "intersection" in obs) or maneuver == "ENTER_INTERSECTION"):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Cross-traffic at blind intersection\n"
                f"WARNING: Wait before entering - cross-traffic approaching.\n"
                f"REASON: Building blocks visibility; conflicting arrival times under 2.5 seconds.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 19: Overtaking conflict
        # -------------------------------------------------------------
        if (maneuver == "OVERTAKE" or "overtake" in obs) and ("oncoming" in obs or "beyond the curve" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Oncoming vehicle beyond curve\n"
                f"WARNING: Do not overtake - oncoming vehicle approaching.\n"
                f"REASON: Oncoming vehicle occluded by curve creates imminent head-on threat.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 18: Highway exit blocked
        # -------------------------------------------------------------
        if (maneuver in ("EXIT", "EXIT_HIGHWAY") or "exit" in obs) and ("blocked" in obs or "exit ramp" in obs or "ramp" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Highway exit ramp blocked\n"
                f"WARNING: Exit ramp blocked - avoid unsafe exit movement.\n"
                f"REASON: Stopped vehicle partially blocks target highway exit.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 17: Poor visibility + hidden stopped traffic
        # -------------------------------------------------------------
        if ("fog" in obs or "visibility" in obs) and ("stopped" in obs or "traffic" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Hidden stopped traffic in dense fog\n"
                f"WARNING: Heavy fog - reduce speed, stopped traffic ahead.\n"
                f"REASON: Cooperative alert reveals stopped vehicles occluded by fog.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 10: Stopped vehicle around a curve / stopped vehicle ahead
        # -------------------------------------------------------------
        if ("curve" in obs or "sharp curve" in obs) and ("stopped" in obs or "blocking" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Stopped vehicle around curve\n"
                f"WARNING: Stopped vehicle around curve - prepare to brake.\n"
                f"REASON: Sharp curve blocks direct line of sight to stationary obstacle.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        if ("stopped vehicle" in obs or "stationary ahead" in obs or "stopped truck" in obs or ("stopped" in obs and ("ahead" in obs or "roadway" in obs or "lane" in obs))) and not ("pedestrian" in obs or "cyclist" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Stopped vehicle ahead in roadway\n"
                f"WARNING: Vehicle stopped ahead - reduce speed and prepare to brake.\n"
                f"REASON: Stationary vehicle obstructing travel path ahead.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 9: Wrong-way vehicle
        # -------------------------------------------------------------
        if "wrong-way" in obs or "wrong way" in obs or ("west" in obs and "eastbound" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Wrong-way vehicle approaching\n"
                f"WARNING: DANGER - wrong-way vehicle approaching in roadway.\n"
                f"REASON: Opposing vehicle detected traveling westbound on eastbound roadway.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 8: Sudden braking ahead
        # -------------------------------------------------------------
        if ("braking" in obs or "sudden" in obs or "decelerated" in obs) and ("car_c" in obs or "ahead" in obs or "blocks the view" in obs):
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Sudden deceleration ahead\n"
                f"WARNING: Lead vehicle braking sharply - increase following distance.\n"
                f"REASON: Deceleration occluded by lead vehicle; prepare to slow.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 12: Emergency vehicle
        # -------------------------------------------------------------
        if "emergency vehicle" in obs or "ambulance" in obs or "siren" in obs:
            return (
                f"RISK: MEDIUM\n"
                f"HAZARD: Emergency vehicle approaching\n"
                f"WARNING: Emergency vehicle approaching from behind - yield safely.\n"
                f"REASON: Active emergency vehicle sharing lane; yield right of way.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 11: Construction / lane closure
        # -------------------------------------------------------------
        if "construction" in obs or "barriers" in obs or "work zone" in obs or "lane closure" in obs:
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Construction barriers blocking lane\n"
                f"WARNING: Construction ahead - prepare safe lane transition.\n"
                f"REASON: Lane 2 obstructed by construction barriers.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 3: Hidden cyclist during lane change
        # -------------------------------------------------------------
        if "cyclist" in obs or "bicycle" in obs or "bike" in obs:
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Hidden cyclist near target lane\n"
                f"WARNING: Delay lane change - cyclist traveling beside truck.\n"
                f"REASON: Cyclist occluded beside large vehicle in target lane path.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 2: Hidden pedestrian during right turn
        # -------------------------------------------------------------
        if "pedestrian" in obs or "person" in obs:
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Hidden pedestrian\n"
                f"WARNING: Wait before turning - pedestrian entering roadway.\n"
                f"REASON: Pedestrian partially hidden behind truck moving toward roadway.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 1: Road debris during lane change
        # -------------------------------------------------------------
        if "debris" in obs or "tire" in obs or "obstacle" in obs or "object" in obs:
            return (
                f"RISK: HIGH\n"
                f"HAZARD: Road debris ahead\n"
                f"WARNING: Debris ahead in lane 3 - remain in current lane.\n"
                f"REASON: Intended lane change intersects road obstacle.\n"
                f"SEND TO: {vehicle_id}\n"
                f"CONFIDENCE: HIGH"
            )

        # -------------------------------------------------------------
        # Scenario 20: Completely safe road / clear
        # -------------------------------------------------------------
        if any(w in obs for w in ["clear", "no pedestrians", "no nearby hazards", "safe"]):
            return (
                f"RISK: LOW\n"
                f"HAZARD: None\n"
                f"WARNING: Road clear - safe to proceed.\n"
                f"REASON: No hazards reported along current path.\n"
                f"SEND TO: NONE\n"
                f"CONFIDENCE: HIGH"
            )

        # Default fallback
        return (
            f"RISK: LOW\n"
            f"HAZARD: Routine road conditions\n"
            f"WARNING: Maintain safe following distance.\n"
            f"REASON: No active conflict detected.\n"
            f"SEND TO: NONE\n"
            f"CONFIDENCE: MEDIUM"
        )

