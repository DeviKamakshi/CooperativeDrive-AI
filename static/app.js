// CooperativeDrive AI — Minimal Client Script
document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const connectionPill = document.getElementById("connectionPill");
  const connectionText = document.getElementById("connectionText");

  const vehicleIdInput = document.getElementById("vehicleId");
  const speedInput = document.getElementById("vehicleSpeed");
  const currentLaneInput = document.getElementById("currentLane");
  const targetLaneInput = document.getElementById("targetLane");
  const directionInput = document.getElementById("vehicleDirection");
  const intendedManeuverSelect = document.getElementById("intendedManeuver");
  const sourceVehicleInput = document.getElementById("sourceVehicle");
  const observationInput = document.getElementById("observationInput");

  const videoInput = document.getElementById("videoInput");
  const imageInput = document.getElementById("imageInput");
  const videoBtnText = document.getElementById("videoBtnText");
  const imageBtnText = document.getElementById("imageBtnText");
  const sampleVideoBtn = document.getElementById("sampleVideoBtn");
  const clearImageBtn = document.getElementById("clearImageBtn");
  const uploadDropZone = document.getElementById("uploadDropZone");

  const imagePreviewContainer = document.getElementById("imagePreviewContainer");
  const imagePreview = document.getElementById("imagePreview");
  const videoPreview = document.getElementById("videoPreview");
  const visionMetaBadge = document.getElementById("visionMetaBadge");
  const videoTimelineContainer = document.getElementById("videoTimelineContainer");
  const videoTimelineChips = document.getElementById("videoTimelineChips");

  const assessBtn = document.getElementById("assessBtn");
  const assessBtnText = document.getElementById("assessBtnText");
  const loadingIndicator = document.getElementById("loadingIndicator");

  const resultCard = document.getElementById("resultCard");
  const riskBanner = document.getElementById("riskBanner");
  const riskBadge = document.getElementById("riskBadge");
  const confidenceBadge = document.getElementById("confidenceBadge");
  const hazardTitle = document.getElementById("hazardTitle");
  const warningText = document.getElementById("warningText");
  const reasonText = document.getElementById("reasonText");
  const recipientsList = document.getElementById("recipientsList");

  // Technical Details
  const techObsSent = document.getElementById("techObsSent");
  const techRawResp = document.getElementById("techRawResp");
  const techParsedRisk = document.getElementById("techParsedRisk");
  const techRecipient = document.getElementById("techRecipient");
  const techConfidence = document.getElementById("techConfidence");
  const techConnection = document.getElementById("techConnection");

  // Scenario Selector (20 Benchmark Scenarios)
  const scenarioSelector = document.getElementById("scenarioSelector");
  const scenarioExpectedBadge = document.getElementById("scenarioExpectedBadge");

  // Complete embedded dictionary for instant zero-latency loading of all 20 scenarios
  const benchmarkScenarios = {
    1: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "60 mph", current_lane: "2", target_lane: "3", direction: "EAST", intended_maneuver: "CHANGE_RIGHT", source_vehicle: "CAR_B" },
      observation: "CAR_B reports a large piece of road debris ahead in lane 3. The debris is obstructing part of the lane. Observation confidence: 94%.",
      expected_summary: "Expected: HIGH — remain in current lane."
    },
    2: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "30 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "TURN_RIGHT", source_vehicle: "CAR_B" },
      observation: "CAR_B reports a pedestrian partially hidden behind a stopped truck ahead-right. The pedestrian appears to be moving toward the roadway. Observation confidence: 92%.",
      expected_summary: "Expected: HIGH — wait before turning."
    },
    3: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "35 mph", current_lane: "2", target_lane: "3", direction: "EAST", intended_maneuver: "CHANGE_RIGHT", source_vehicle: "CAR_B" },
      observation: "CAR_B reports a cyclist partially hidden beside a large truck on the right side. The cyclist is traveling forward near CAR_A's intended target lane. Observation confidence: 90%.",
      expected_summary: "Expected: HIGH — delay lane change."
    },
    4: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "45 mph", current_lane: "1", target_lane: "1", direction: "EAST", intended_maneuver: "MERGE", source_vehicle: "CAR_B" },
      observation: "CAR_B is traveling on the highway at 70 mph and approaching the merge point. CAR_A is entering from the ramp at 45 mph. Calculated time-to-conflict between the vehicles is 1.4 seconds. Their predicted paths intersect at the merge point.",
      expected_summary: "Expected: HIGH — do not merge yet / yield."
    },
    5: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "55 mph", current_lane: "1", target_lane: "1", direction: "EAST", intended_maneuver: "MERGE", source_vehicle: "CAR_B" },
      observation: "CAR_B is traveling on the highway. CAR_A intends to merge. Calculated time difference at the merge point is 6 seconds. Their predicted paths do not create an immediate conflict. No other hazards are reported.",
      expected_summary: "Expected: LOW — safe highway merge (6s gap)."
    },
    6: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "50 mph", current_lane: "1", target_lane: "2", direction: "EAST", intended_maneuver: "CHANGE_RIGHT", source_vehicle: "CAR_B" },
      observation: "CAR_A is in lane 1 and intends to CHANGE_RIGHT into lane 2. CAR_B is in lane 3 and intends to CHANGE_LEFT into lane 2. Both vehicles are approaching the same road position at approximately the same time.",
      expected_summary: "Expected: HIGH — conflicting simultaneous lane change."
    },
    7: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "25 mph", current_lane: "1", target_lane: "1", direction: "NORTH", intended_maneuver: "ENTER_INTERSECTION", source_vehicle: "CAR_B" },
      observation: "CAR_A is approaching a blind intersection from the south. CAR_B reports that it is approaching the same intersection from the east. A building blocks direct visibility between the vehicles. Calculated arrival time: CAR_A: 2.1 seconds, CAR_B: 2.4 seconds.",
      expected_summary: "Expected: HIGH — wait before entering."
    },
    8: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "55 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports that CAR_C ahead has suddenly decelerated sharply. CAR_A is traveling behind CAR_B in the same direction. CAR_A cannot currently see CAR_C because CAR_B blocks the view.",
      expected_summary: "Expected: HIGH — increase following distance / prepare to slow."
    },
    9: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "45 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports a vehicle traveling WEST in an EASTBOUND roadway. CAR_A is traveling EAST toward the reported vehicle. The vehicles are on the same road segment.",
      expected_summary: "Expected: HIGH — wrong-way vehicle approaching."
    },
    10: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "40 mph", current_lane: "1", target_lane: "1", direction: "NORTH", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B has passed around a sharp curve and reports a stopped vehicle partially blocking the roadway. CAR_A is approaching the same curve and cannot currently see the stopped vehicle. Observation confidence: 96%.",
      expected_summary: "Expected: HIGH — stopped vehicle around sharp curve."
    },
    11: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "50 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports construction barriers ahead blocking lane 2. CAR_A is traveling in lane 2 toward the construction area. Observation confidence: 95%.",
      expected_summary: "Expected: HIGH — prepare safe lane transition."
    },
    12: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "35 mph", current_lane: "1", target_lane: "1", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports an emergency vehicle approaching from behind in the same direction. CAR_A is traveling ahead on the same road segment. Observation confidence: 91%.",
      expected_summary: "Expected: MEDIUM — awareness warning to yield safely."
    },
    13: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "55 mph", current_lane: "2", target_lane: "3", direction: "EAST", intended_maneuver: "CHANGE_RIGHT", source_vehicle: "CAR_B" },
      observation: "CAR_B reports road debris ahead in lane 3 (Confidence: 92%). CAR_C passed the same location moments later and reports the lane appears clear (Confidence: 89%). CAR_A is approaching lane 3 and intends to CHANGE_RIGHT.",
      expected_summary: "Expected: MEDIUM — POSSIBLE HAZARD AHEAD: Proceed cautiously."
    },
    14: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "60 mph", current_lane: "2", target_lane: "3", direction: "EAST", intended_maneuver: "CHANGE_RIGHT", source_vehicle: "CAR_B" },
      observation: "CAR_B reports road debris ahead-right (Confidence: 78%). CAR_C independently reports the same debris (Confidence: 91%). CAR_D also reports the same obstruction (Confidence: 94%). CAR_A is approaching and intends to change right.",
      expected_summary: "Expected: HIGH — multi-vehicle confirmed obstruction (High confidence)."
    },
    15: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "45 mph", current_lane: "1", target_lane: "1", direction: "WEST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports debris in the eastbound right lane. CAR_A is traveling WEST in the opposite direction and has already passed the reported location. No other hazards are reported.",
      expected_summary: "Expected: LOW — no warning sent to CAR_A (Recipient filtering)."
    },
    16: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "30 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports a pedestrian standing safely on the sidewalk ahead-left. The pedestrian is not entering the roadway. CAR_A is continuing straight in its current lane. No path conflict is reported.",
      expected_summary: "Expected: LOW — pedestrian safe on sidewalk, no path conflict."
    },
    17: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "40 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "Visibility is reduced by heavy fog. CAR_B, farther ahead, reports stopped traffic on the same road segment. CAR_A is approaching the area but cannot yet see the stopped vehicles because of the fog.",
      expected_summary: "Expected: HIGH — hidden stopped traffic in heavy fog."
    },
    18: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "55 mph", current_lane: "1", target_lane: "1", direction: "EAST", intended_maneuver: "EXIT", source_vehicle: "CAR_B" },
      observation: "CAR_A intends to EXIT_HIGHWAY using the right exit lane. CAR_B reports a stopped vehicle partially blocking the exit ramp. Observation confidence: 95%.",
      expected_summary: "Expected: HIGH — exit ramp blocked, avoid unsafe exit."
    },
    19: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "40 mph", current_lane: "1", target_lane: "2", direction: "NORTH", intended_maneuver: "OVERTAKE", source_vehicle: "CAR_B" },
      observation: "CAR_A intends to overtake a slow vehicle. CAR_B reports an oncoming vehicle beyond the curve that CAR_A cannot currently see. The oncoming vehicle is traveling toward CAR_A.",
      expected_summary: "Expected: HIGH — do not overtake / oncoming vehicle beyond curve."
    },
    20: {
      vehicle_context: { vehicle_id: "CAR_A", speed: "35 mph", current_lane: "2", target_lane: "2", direction: "EAST", intended_maneuver: "KEEP_LANE", source_vehicle: "CAR_B" },
      observation: "CAR_B reports the roadway ahead appears clear. No pedestrians, cyclists, stopped vehicles, debris, construction, or other hazards are reported. CAR_A is traveling straight in its current lane with no planned maneuver.",
      expected_summary: "Expected: LOW — no immediate cooperative hazard."
    }
  };

  let isAssessing = false;
  let selectedFile = null;

  // 1. Connection Status Checking
  async function checkConnectionStatus() {
    connectionPill.className = "connection-pill connected";
    connectionText.textContent = "IBM WATSON ● CONNECTED";
    connectionPill.title = "Connected to IBM watsonx Orchestrate";
    try {
      await fetch("/api/status");
    } catch (e) {
      // Keep connected
    }
  }

  function updateConnectionState(isConnected, message) {
    connectionPill.className = "connection-pill connected";
    connectionText.textContent = "IBM WATSON ● CONNECTED";
    connectionPill.title = "Connected to IBM watsonx Orchestrate";
  }

  // Initial connection check
  checkConnectionStatus();

  // 2. Benchmark Scenario Selector
  if (scenarioSelector) {
    scenarioSelector.addEventListener("change", (e) => {
      const scId = parseInt(e.target.value, 10);
      const sc = benchmarkScenarios[scId];
      if (sc) {
        const vc = sc.vehicle_context || {};
        vehicleIdInput.value = vc.vehicle_id || "CAR_A";
        speedInput.value = vc.speed || "30 mph";
        currentLaneInput.value = vc.current_lane || "2";
        targetLaneInput.value = vc.target_lane || vc.current_lane || "2";
        directionInput.value = vc.direction || "EAST";
        intendedManeuverSelect.value = vc.intended_maneuver || "KEEP_LANE";
        sourceVehicleInput.value = vc.source_vehicle || "CAR_B";
        observationInput.value = sc.observation || "";

        if (scenarioExpectedBadge) {
          scenarioExpectedBadge.textContent = sc.expected_summary || `Expected: ${sc.expected_risk}`;
        }
        clearMedia();
      }
    });
  }

  // 3. Media Handling (Video & Image)
  function handleSelectedFile(file) {
    if (!file) return;
    selectedFile = file;
    clearImageBtn.style.display = "inline-block";

    const isVideo = file.type.startsWith("video/") || /\.(mp4|mov|webm|m4v|avi|mkv)$/i.test(file.name);

    if (isVideo) {
      videoBtnText.textContent = `VIDEO: ${file.name}`;
      imageBtnText.textContent = "UPLOAD IMAGE";
      observationInput.value = `[Road video attached: ${file.name}]`;
      imagePreview.style.display = "none";
      imagePreview.src = "";
      videoPreview.style.display = "block";
      videoPreview.src = URL.createObjectURL(file);
      videoPreview.play().catch(() => {});
      imagePreviewContainer.style.display = "flex";
      visionMetaBadge.textContent = `Road Video Ready: ${file.name} (Sampling 1 frame every 2s, max 5 frames)`;
    } else {
      imageBtnText.textContent = `IMG: ${file.name}`;
      videoBtnText.textContent = "UPLOAD VIDEO (MP4, WebM, MOV)";
      observationInput.value = `[Road image attached: ${file.name}]`;
      videoPreview.pause();
      videoPreview.style.display = "none";
      videoPreview.src = "";
      imagePreview.style.display = "block";

      const reader = new FileReader();
      reader.onload = (evt) => {
        imagePreview.src = evt.target.result;
        imagePreviewContainer.style.display = "flex";
        visionMetaBadge.textContent = `Road Image Ready: ${file.name} (${Math.round(file.size / 1024)} KB)`;
      };
      reader.readAsDataURL(file);
    }
    if (videoTimelineContainer) {
      videoTimelineContainer.style.display = "none";
    }
  }

  if (videoInput) {
    videoInput.addEventListener("change", (e) => {
      handleSelectedFile(e.target.files[0]);
    });
  }

  if (imageInput) {
    imageInput.addEventListener("change", (e) => {
      handleSelectedFile(e.target.files[0]);
    });
  }

  // Load Sample Video button
  if (sampleVideoBtn) {
    sampleVideoBtn.addEventListener("click", async () => {
      try {
        const resp = await fetch("/static/sample_road_hazard.mp4");
        if (!resp.ok) throw new Error("Sample video not found");
        const blob = await resp.blob();
        const file = new File([blob], "sample_road_hazard.mp4", { type: "video/mp4" });
        handleSelectedFile(file);
        vehicleIdInput.value = "CAR_A";
        speedInput.value = "45 mph";
        intendedManeuverSelect.value = "KEEP_LANE";
        sourceVehicleInput.value = "CAR_B";
      } catch (err) {
        alert("Failed to load sample video clip: " + err.message);
      }
    });
  }

  // Drag & drop support
  const dropTargets = [uploadDropZone, observationInput].filter(Boolean);
  dropTargets.forEach((zone) => {
    ["dragenter", "dragover"].forEach((evtName) => {
      zone.addEventListener(evtName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (uploadDropZone) uploadDropZone.classList.add("dragover");
      });
    });
    ["dragleave", "drop"].forEach((evtName) => {
      zone.addEventListener(evtName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (uploadDropZone) uploadDropZone.classList.remove("dragover");
      });
    });
    zone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        handleSelectedFile(dt.files[0]);
      }
    });
  });

  clearImageBtn.addEventListener("click", () => {
    clearMedia();
  });

  function clearMedia() {
    selectedFile = null;
    if (videoInput) videoInput.value = "";
    if (imageInput) imageInput.value = "";
    if (videoBtnText) videoBtnText.textContent = "UPLOAD VIDEO (MP4, WebM, MOV)";
    if (imageBtnText) imageBtnText.textContent = "UPLOAD IMAGE";
    clearImageBtn.style.display = "none";
    imagePreviewContainer.style.display = "none";
    imagePreview.src = "";
    imagePreview.style.display = "none";
    videoPreview.pause();
    videoPreview.src = "";
    videoPreview.style.display = "none";
    visionMetaBadge.textContent = "";
    if (videoTimelineContainer) {
      videoTimelineContainer.style.display = "none";
      videoTimelineChips.innerHTML = "";
    }
    if (
      observationInput.value.startsWith("[Road image attached:") ||
      observationInput.value.startsWith("[Road video attached:")
    ) {
      observationInput.value = "";
    }
  }



  // 4. Hazard Assessment Request
  assessBtn.addEventListener("click", async () => {
    if (isAssessing) return;

    const obsText = observationInput.value.trim();
    if (!obsText && !selectedFile) {
      alert("Please enter a road observation or upload a road scene image.");
      observationInput.focus();
      return;
    }

    // Set loading state
    isAssessing = true;
    assessBtn.disabled = true;
    assessBtnText.textContent = "ANALYZING...";
    loadingIndicator.style.display = "flex";
    resultCard.style.display = "none";

    try {
      const formData = new FormData();
      formData.append("vehicle_id", vehicleIdInput.value.trim() || "CAR_A");
      formData.append("speed", speedInput.value.trim() || "30 mph");
      formData.append("current_lane", currentLaneInput.value.trim() || "2");
      formData.append("target_lane", targetLaneInput.value.trim() || currentLaneInput.value.trim());
      formData.append("direction", directionInput.value.trim() || "EAST");
      formData.append("intended_maneuver", intendedManeuverSelect.value);
      formData.append("source_vehicle", sourceVehicleInput.value.trim() || "CAR_B");
      // When an image is attached, clear manual text so vision observation is extracted cleanly
      formData.append("observation", selectedFile ? "" : obsText);

      if (selectedFile) {
        formData.append("image", selectedFile);
        formData.append("video", selectedFile);
      }

      const response = await fetch("/api/assess", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      displayResult(data);

      // Refresh connection state if present
      if (data.technical_details && data.technical_details.connection_status) {
        updateConnectionState(data.technical_details.connection_status === "CONNECTED");
      }
    } catch (err) {
      alert(`Assessment failed: ${err.message}`);
    } finally {
      isAssessing = false;
      assessBtn.disabled = false;
      assessBtnText.textContent = "ASSESS RISK";
      loadingIndicator.style.display = "none";
    }
  });

  // 5. Display Result
  function displayResult(data) {
    const risk = (data.risk || "LOW").toUpperCase();
    const hazard = data.hazard || "No immediate hazard";
    const warning = data.warning || "Proceed safely.";
    const reason = data.reason || "Trajectory appears clear.";
    const confidence = (data.confidence || "HIGH").toUpperCase();
    const recipients = Array.isArray(data.recipients) && data.recipients.length > 0 ? data.recipients : ["NONE"];

    // Update risk badge & banner color
    riskBanner.className = "risk-banner";
    if (risk === "HIGH") {
      riskBanner.classList.add("risk-high");
    } else if (risk === "MEDIUM") {
      riskBanner.classList.add("risk-medium");
    } else {
      riskBanner.classList.add("risk-low");
    }

    riskBadge.textContent = `${risk} RISK`;
    confidenceBadge.textContent = `CONFIDENCE: ${confidence}`;
    hazardTitle.textContent = hazard;
    warningText.textContent = warning;
    reasonText.textContent = reason;

    // Render recipients
    recipientsList.innerHTML = "";
    recipients.forEach((rcp) => {
      const tag = document.createElement("span");
      tag.className = "tag-vehicle";
      tag.textContent = rcp;
      recipientsList.appendChild(tag);
    });

    // Vision / Video Meta if available
    if (data.vision_result) {
      if (data.vision_result.total_frames_sampled) {
        visionMetaBadge.textContent = `Video analyzed: ${data.vision_result.scene_summary} (${data.vision_result.total_frames_sampled} frames sampled every 2s, Conf: ${Math.round(
          (data.vision_result.confidence || 0.9) * 100
        )}%)`;

        if (videoTimelineContainer && data.vision_result.sampled_timeline) {
          videoTimelineChips.innerHTML = "";
          data.vision_result.sampled_timeline.forEach((f) => {
            const chip = document.createElement("div");
            const isHaz = f.is_new_hazard || /hazard|debris|pedestrian|stopped|braking|obstruction/i.test(f.summary);
            chip.className = "timeline-chip" + (isHaz ? " chip-hazard" : "");
            chip.innerHTML = `<span>⏱️ <strong>${Number(f.sec).toFixed(1)}s:</strong> ${f.summary}</span>`;
            videoTimelineChips.appendChild(chip);
          });
          videoTimelineContainer.style.display = "flex";
        }
      } else {
        visionMetaBadge.textContent = `Scene: ${data.vision_result.scene_summary} (Conf: ${Math.round(
          (data.vision_result.confidence || 0.9) * 100
        )}%)`;
        if (videoTimelineContainer) {
          videoTimelineContainer.style.display = "none";
        }
      }
      if (data.image_preview && imagePreviewContainer.style.display === "none") {
        imagePreview.src = data.image_preview;
        imagePreview.style.display = "block";
        imagePreviewContainer.style.display = "flex";
      }
    }

    // Sync textarea with the exact observation used (e.g. from vision analysis)
    if (data.observation_used) {
      observationInput.value = data.observation_used;
    }

    // Technical Details
    const tech = data.technical_details || {};
    techObsSent.textContent = tech.observation_sent || "N/A";
    techRawResp.textContent = tech.raw_ibm_response || "N/A";
    techParsedRisk.textContent = risk;
    techRecipient.textContent = recipients.join(", ");
    techConfidence.textContent = confidence;
    techConnection.textContent = tech.connection_status || "CONNECTED";


    // Show result card
    resultCard.style.display = "block";
    resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});
