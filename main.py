"""CooperativeDrive AI — Minimal Hackathon Application Backend.

Provides:
- POST /api/assess: Assess road risk using vehicle context + text/image observation via IBM Orchestrate
- GET /api/status: Check live IBM watsonx Orchestrate connection state
- Static file serving for minimalist frontend UI
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from orchestrate import OrchestrateClient
from scenarios import BENCHMARK_SCENARIOS
from vision import vision_analyzer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cooperativedrive")

app = FastAPI(
    title="CooperativeDrive AI",
    description="Connected-vehicle road hazard & cooperative risk assessment powered by IBM watsonx Orchestrate",
    version="1.0.0",
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate the live Orchestrate client
orchestrate_client = OrchestrateClient()

# Ensure uploads / temp dirs exist
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


class VehicleContext(BaseModel):
    vehicle_id: str = Field(default="CAR_A")
    speed: str = Field(default="30 mph")
    current_lane: str = Field(default="2")
    target_lane: str = Field(default="2")
    direction: str = Field(default="EAST")
    intended_maneuver: str = Field(default="KEEP_LANE")
    source_vehicle: str = Field(default="CAR_B")


class AssessRequest(BaseModel):
    vehicle_id: str = "CAR_A"
    speed: str = "30 mph"
    current_lane: str = "2"
    target_lane: str = "2"
    direction: str = "EAST"
    intended_maneuver: str = "KEEP_LANE"
    source_vehicle: str = "CAR_B"
    observation: str


@app.get("/api/status")
async def get_connection_status():
    """Returns the live connection state of IBM watsonx Orchestrate."""
    connected, msg = await orchestrate_client.check_connection()
    return {
        "status": "CONNECTED" if connected else "OFFLINE",
        "message": msg,
        "configured": orchestrate_client.is_configured,
    }


@app.get("/api/scenarios")
async def get_benchmark_scenarios():
    """Returns the 20 canonical cooperative connected-vehicle safety scenarios."""
    return {"scenarios": BENCHMARK_SCENARIOS}


@app.post("/api/assess")
async def assess(
    request: Request,
    vehicle_id: Optional[str] = Form(None),
    speed: Optional[str] = Form(None),
    current_lane: Optional[str] = Form(None),
    target_lane: Optional[str] = Form(None),
    direction: Optional[str] = Form(None),
    intended_maneuver: Optional[str] = Form(None),
    source_vehicle: Optional[str] = Form(None),
    observation: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    media: Optional[UploadFile] = File(None),
):
    """Processes vehicle context + road observation (text or uploaded image/video)
    and evaluates hazard risk using the IBM watsonx Orchestrate agent.
    """
    # Support both multipart/form-data and raw JSON bodies
    content_type = request.headers.get("content-type", "")
    vision_meta: Optional[Dict[str, Any]] = None
    image_preview_b64: Optional[str] = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            v_id = body.get("vehicle_id", "CAR_A")
            v_spd = body.get("speed", "30 mph")
            v_cur_lane = str(body.get("current_lane", "2"))
            v_tgt_lane = str(body.get("target_lane", v_cur_lane))
            v_dir = body.get("direction", "EAST")
            v_maneuver = body.get("intended_maneuver", "KEEP_LANE")
            v_src = body.get("source_vehicle", "CAR_B")
            obs_text = body.get("observation", "").strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON request body: {str(e)}")
    else:
        # Form data
        v_id = vehicle_id or "CAR_A"
        v_spd = speed or "30 mph"
        v_cur_lane = str(current_lane or "2")
        v_tgt_lane = str(target_lane or v_cur_lane)
        v_dir = direction or "EAST"
        v_maneuver = intended_maneuver or "KEEP_LANE"
        v_src = source_vehicle or "CAR_B"
        obs_text = (observation or "").strip()

        # Handle video or image upload if provided (supports field names: video, media, image)
        uploaded = video or media or image
        if uploaded and uploaded.filename:
            content = await uploaded.read()
            if content:
                ext = os.path.splitext(uploaded.filename.lower())[1]
                is_video = (
                    ext in vision_analyzer.supported_video_types
                    or (uploaded.content_type and uploaded.content_type.startswith("video/"))
                )

                if is_video:
                    try:
                        frames = vision_analyzer.sample_video_frames(content, filename=uploaded.filename)
                        if frames:
                            # Prioritize frame detecting a new hazard or first frame
                            hazards = [f for f in frames if f.get("is_hazard")]
                            new_hazards = [f for f in frames if f.get("is_new_hazard") and f.get("is_hazard")]
                            crit_frame = new_hazards[0] if new_hazards else (hazards[0] if hazards else frames[0])

                            vision_meta = {
                                "media_type": "video",
                                "filename": uploaded.filename,
                                "scene_summary": crit_frame.get("scene_summary", ""),
                                "confidence": crit_frame.get("confidence", 0.9),
                                "total_frames_sampled": len(frames),
                                "sampled_timeline": [
                                    {
                                        "sec": f.get("timestamp_sec", 0.0),
                                        "summary": f.get("scene_summary", ""),
                                        "is_new_hazard": f.get("is_new_hazard", False),
                                        "confidence": f.get("confidence", 0.9),
                                    }
                                    for f in frames
                                ],
                            }
                            if crit_frame.get("preview_b64"):
                                image_preview_b64 = f"data:image/jpeg;base64,{crit_frame['preview_b64']}"

                            conf_pct = int(crit_frame.get("confidence", 0.9) * 100)
                            obs_text = f"{crit_frame.get('scene_summary', '')} Observation confidence: {conf_pct}%."
                    except ValueError as ve:
                        raise HTTPException(status_code=400, detail=str(ve))
                    except Exception as ex:
                        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(ex)}")
                else:
                    try:
                        vision_res = vision_analyzer.analyze_image(content, filename=uploaded.filename)
                        vision_meta = vision_res
                        vision_meta["media_type"] = "image"
                        conf_pct = int(vision_res.get("confidence", 0.9) * 100)
                        scene_summary = vision_res.get("scene_summary", "")
                        obs_text = f"{scene_summary} Observation confidence: {conf_pct}%."
                        mime = uploaded.content_type or "image/jpeg"
                        image_preview_b64 = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
                    except ValueError as ve:
                        raise HTTPException(status_code=400, detail=str(ve))
                    except Exception as ex:
                        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(ex)}")

    if not obs_text:
        raise HTTPException(
            status_code=400,
            detail="Road observation is required (enter text observation or upload a road image or video).",
        )

    vehicle_context = {
        "vehicle_id": v_id,
        "speed": v_spd,
        "current_lane": v_cur_lane,
        "target_lane": v_tgt_lane,
        "direction": v_dir,
        "intended_maneuver": v_maneuver,
    }

    # Call Orchestrate agent
    try:
        assessment = await orchestrate_client.assess_hazard(
            vehicle_context=vehicle_context,
            road_observation=obs_text,
            source_vehicle=v_src,
        )
    except Exception as exc:
        logger.error("Error during hazard assessment: %s", exc)
        raise HTTPException(status_code=500, detail="Hazard assessment failed.")

    # Attach observation and vision metadata to response
    assessment["observation_used"] = obs_text
    if vision_meta:
        assessment["vision_result"] = vision_meta
    if image_preview_b64:
        assessment["image_preview"] = image_preview_b64

    return assessment


# Serve static directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    """Serves the minimal single-page web UI."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "CooperativeDrive AI backend is running. static/index.html not found."})


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
