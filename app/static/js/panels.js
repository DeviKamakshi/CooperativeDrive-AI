/* jshint esversion: 6 */
/**
 * panels.js — Panel Renderers
 * Updates all non-map panels from ScenarioFrame data.
 */

/* ================================================================== */
/*  Badge helpers                                                       */
/* ================================================================== */

/**
 * Returns HTML for an information-source badge.
 * @param {string|null} source  - InformationSource enum value from the server
 */
function sourceBadge(source) {
  if (!source) return '';
  const map = {
    'VISION_DERIVED':    ['badge-vision',    'VISION-DERIVED'],
    'TELEMETRY_DERIVED': ['badge-telemetry', 'TELEMETRY-DERIVED'],
    'SYNTHETIC_SCENARIO':['badge-synthetic', 'SYNTHETIC/SCENARIO-DERIVED'],
  };
  const [cls, label] = map[source] || ['badge-muted', source];
  return `<span class="badge ${cls}">${label}</span>`;
}

/**
 * Returns HTML for a message priority badge.
 */
function priorityBadge(priority) {
  const map = {
    'URGENT':        'badge-danger',
    'HIGH_PRIORITY': 'badge-warning',
    'NORMAL':        'badge-info',
    'LOW_PRIORITY':  'badge-muted',
  };
  return `<span class="badge ${map[priority] || 'badge-muted'}">${priority || ''}</span>`;
}

/* ================================================================== */
/*  Risk Panel                                                          */
/* ================================================================== */

function updateRiskPanel(riskResult) {
  if (!riskResult) return;

  // --- Risk level indicator ---
  const level = riskResult.risk || 'LOW';
  const el    = document.getElementById('risk-level-display');
  el.textContent = level;
  el.className   = `risk-level risk-${level.toLowerCase()}`;

  // --- Confidence ---
  const pct = ((riskResult.confidence || 0) * 100).toFixed(0);
  document.getElementById('risk-confidence').innerHTML =
    `Confidence: <strong>${pct}%</strong>`;

  // --- Time to conflict ---
  const ttcEl  = document.getElementById('risk-ttc');
  ttcEl.textContent = riskResult.ttc_seconds != null
    ? `Time to conflict: ${riskResult.ttc_seconds.toFixed(1)} s`
    : '';

  // --- Reason codes ---
  const reasonEl = document.getElementById('risk-reasons');
  reasonEl.innerHTML = (riskResult.reason_codes || [])
    .map(r => `<span class="reason-code">${r}</span>`)
    .join('');

  // --- Recommendation ---
  document.getElementById('risk-recommendation').textContent =
    riskResult.recommendation
      ? `▶ ${riskResult.recommendation.replace(/_/g, ' ')}`
      : '';

  // --- Explanation ---
  const explEl = document.getElementById('risk-explanation');
  explEl.textContent = riskResult.watsonx_explanation
    ? riskResult.watsonx_explanation
    : 'Awaiting explanation…';

  // --- Explanation source badge ---
  const src     = riskResult.explanation_source || 'DETERMINISTIC_FALLBACK';
  const srcEl   = document.getElementById('explanation-source-badge');
  srcEl.innerHTML = src === 'WATSONX'
    ? '<span class="badge badge-vision">IBM watsonx</span>'
    : '<span class="badge badge-synthetic">DETERMINISTIC FALLBACK</span>';

  // --- Fallback banner ---
  const bannerExpl = document.getElementById('banner-explanation');
  if (bannerExpl) {
    bannerExpl.style.display = (src === 'DETERMINISTIC_FALLBACK') ? 'block' : 'none';
  }

  // --- watsonx status chips in header ---
  const wxText = document.getElementById('wx-text-status');
  if (wxText) {
    if (src === 'WATSONX') {
      wxText.textContent = 'watsonx: online';
      wxText.className   = 'badge badge-telemetry';
    } else {
      wxText.textContent = 'watsonx: offline';
      wxText.className   = 'badge badge-warning';
    }
  }
}

/* ================================================================== */
/*  Camera Panel                                                        */
/* ================================================================== */

// Scenarios that have a real frame image
const SCENARIO_IMAGES = {
  's01': '/static/assets/images/s01/frame_001.jpg',
  's02': '/static/assets/images/s02/frame_001.jpg',
  's07': '/static/assets/images/s07/frame_001.jpg',
  's08': '/static/assets/images/s08/frame_001.jpg',
};

function updateCameraPanel(frame) {
  const imgEl      = document.getElementById('camera-image');
  const placeholder = document.getElementById('camera-placeholder');

  const imgPath = SCENARIO_IMAGES[frame.scenario_id];
  if (imgPath) {
    // Only update src once (avoid re-loading same image every tick)
    if (imgEl.src !== window.location.origin + imgPath) {
      imgEl.src = imgPath;
    }
    imgEl.style.display      = 'block';
    placeholder.style.display = 'none';

    // Update vision status badge
    const wxVision = document.getElementById('wx-vision-status');
    if (wxVision) {
      wxVision.textContent = 'Vision: image loaded';
      wxVision.className   = 'badge badge-vision';
    }

    // Show vision fallback banner (images are placeholder stills, not live watsonx)
    const bannerVision = document.getElementById('banner-vision');
    if (bannerVision) bannerVision.style.display = 'block';
  } else {
    imgEl.style.display      = 'none';
    placeholder.style.display = 'block';

    const wxVision = document.getElementById('wx-vision-status');
    if (wxVision) {
      wxVision.textContent = 'Vision: no image';
      wxVision.className   = 'badge badge-muted';
    }

    const bannerVision = document.getElementById('banner-vision');
    if (bannerVision) bannerVision.style.display = 'none';
  }

  // Scene description — prefer VISION_DERIVED hazards, fall back to SYNTHETIC
  const sceneEl = document.getElementById('scene-description');
  const visionH = (frame.active_hazards || []).filter(h =>
    h.source === 'VISION_DERIVED' || h.source === 'SYNTHETIC_SCENARIO'
  );
  if (visionH.length) {
    const h = visionH[0];
    sceneEl.innerHTML = `<span>${h.description || 'Scene analyzed'}</span>&nbsp;${sourceBadge(h.source)}`;
  } else {
    sceneEl.textContent = '';
  }
}

/* ================================================================== */
/*  Vehicle State Panel                                                 */
/* ================================================================== */

function updateVehicleStatePanel(vehicles, egoId) {
  const container = document.getElementById('vehicle-state-table');
  if (!vehicles) { container.innerHTML = ''; return; }

  const sorted = Object.values(vehicles).sort((a, b) => {
    // Ego vehicle first
    if (a.vehicle_id === egoId) return -1;
    if (b.vehicle_id === egoId) return 1;
    return a.vehicle_id.localeCompare(b.vehicle_id);
  });

  container.innerHTML = sorted.map(v => {
    const isEgo = v.vehicle_id === egoId;
    const speed = v.speed_mph != null ? `${v.speed_mph.toFixed(1)} mph` : '— mph';
    const lane  = v.lane      != null ? `Lane ${v.lane}` : '';
    const maneuver = v.intended_maneuver || '';
    const dir      = v.direction          || '';
    const inZone   = v.in_maneuver_zone
      ? '<span class="badge badge-vision">IN ZONE</span>'
      : '';

    return `
      <div class="vehicle-row ${isEgo ? 'vehicle-ego' : ''}">
        <div class="vehicle-id">${v.vehicle_id}${isEgo ? ' 👤' : ''}</div>
        <div class="vehicle-details">
          <span>${speed}</span>
          ${lane  ? `<span>${lane}</span>`    : ''}
          ${maneuver ? `<span>${maneuver.replace(/_/g, ' ')}</span>` : ''}
          ${dir   ? `<span>${dir}</span>`     : ''}
          ${inZone}
          ${sourceBadge(v.source)}
        </div>
      </div>`;
  }).join('');
}

/* ================================================================== */
/*  Communications Log                                                  */
/* ================================================================== */

const commsLog = [];
const MAX_COMMS = 30;

function appendCommsEntry(msg) {
  // Deduplicate within this tick (same source + type + first recipient)
  const key = `${msg.source_vehicle}|${msg.message_type}|${(msg.intended_recipients || [])[0]}|${msg.timestamp}`;
  if (commsLog.length && commsLog[0]._key === key) return;

  commsLog.unshift({ ...msg, _key: key });
  if (commsLog.length > MAX_COMMS) commsLog.pop();
  renderCommsLog();
}

function renderCommsLog() {
  const container = document.getElementById('comms-log');
  if (!container) return;
  if (!commsLog.length) {
    container.innerHTML = '<div style="padding:10px;color:#57606a;font-size:0.8rem;font-style:italic">No messages yet</div>';
    return;
  }

  container.innerHTML = commsLog.map(msg => {
    const recipients = (msg.intended_recipients || []).join(', ') || 'broadcast';
    const age        = msg.timestamp ? _timeSince(msg.timestamp) : '';
    return `
      <div class="comms-entry priority-${msg.priority}">
        <span class="comms-src">${msg.source_vehicle}</span>
        <span class="comms-arrow">→</span>
        <span class="comms-dst">${recipients}</span>
        <span class="comms-type">${msg.message_type || ''}</span>
        ${priorityBadge(msg.priority)}
        <span class="comms-age">${age}</span>
      </div>`;
  }).join('');
}

/* ================================================================== */
/*  Hazard Registry                                                     */
/* ================================================================== */

function updateHazardPanel(hazards) {
  const tbody = document.getElementById('hazard-tbody');
  if (!hazards || !hazards.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="muted" style="padding:10px 10px">No active hazards</td></tr>';
    return;
  }

  tbody.innerHTML = hazards.map(h => {
    const conf    = h.confidence != null ? `${(h.confidence * 100).toFixed(0)}%` : '—';
    const age     = h.timestamp  ? _timeSince(h.timestamp) : '—';
    const confirms = h.confirmation_count != null ? h.confirmation_count : 1;
    const conflicts = h.conflict_count    != null ? h.conflict_count     : 0;
    const lane    = h.lane != null ? h.lane : '—';

    return `
      <tr>
        <td>${h.hazard_type || '—'}</td>
        <td>${h.source_vehicle || '—'}</td>
        <td>${lane}</td>
        <td>${conf}</td>
        <td>${age}</td>
        <td>${confirms} / ${conflicts}</td>
        <td class="status-${h.status || ''}">${h.status || '—'}</td>
        <td>${sourceBadge(h.source)}</td>
      </tr>`;
  }).join('');
}

/* ================================================================== */
/*  Scenario Buttons                                                    */
/* ================================================================== */

const SCENARIO_LABELS = {
  's01': '1. Hidden Pedestrian',
  's02': '2. Hwy Merge',
  's03': '3. Sim. Lane Change',
  's04': '4. Blind Intersection',
  's05': '5. Sudden Braking',
  's06': '6. Wrong-Way Vehicle',
  's07': '7. Road Debris',
  's08': '8. Conflicting Reports',
};

function renderScenarioButtons(scenarios) {
  const container = document.getElementById('scenario-buttons');
  if (!container) return;
  container.innerHTML = scenarios.map(s => {
    const label = SCENARIO_LABELS[s.id] || s.name || s.id;
    return `<button class="scenario-btn" data-scenario="${s.id}" onclick="startScenario('${s.id}')">${label}</button>`;
  }).join('');
}

/* ================================================================== */
/*  Clear all panels (called on scenario switch)                        */
/* ================================================================== */

function clearPanels() {
  // Risk panel
  const rld = document.getElementById('risk-level-display');
  if (rld) { rld.textContent = 'LOW'; rld.className = 'risk-level risk-low'; }

  const safeSet = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = val;
  };
  safeSet('risk-confidence', '');
  safeSet('risk-ttc', '');
  safeSet('risk-reasons', '');
  safeSet('risk-recommendation', '');
  safeSet('risk-explanation', 'Awaiting scenario…');
  safeSet('explanation-source-badge', '');

  // Camera
  const imgEl = document.getElementById('camera-image');
  if (imgEl) { imgEl.src = ''; imgEl.style.display = 'none'; }
  const ph = document.getElementById('camera-placeholder');
  if (ph) ph.style.display = 'block';
  safeSet('scene-description', '');

  // Vehicle state
  safeSet('vehicle-state-table', '');

  // Comms
  commsLog.length = 0;
  safeSet('comms-log', '');

  // Hazards
  safeSet('hazard-tbody', '');

  // Banners
  const bv = document.getElementById('banner-vision');
  const be = document.getElementById('banner-explanation');
  if (bv) bv.style.display = 'none';
  if (be) be.style.display = 'none';
}

/* ================================================================== */
/*  Private helpers                                                     */
/* ================================================================== */

function _timeSince(isoString) {
  try {
    const d = new Date(isoString);
    const s = Math.floor((Date.now() - d.getTime()) / 1000);
    if (s < 2)  return 'just now';
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ago`;
  } catch (_) {
    return '';
  }
}
