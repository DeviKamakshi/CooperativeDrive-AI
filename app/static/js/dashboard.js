/* jshint esversion: 6 */
/**
 * dashboard.js — Main Controller
 *
 * Responsibilities:
 *   - Connect to the WebSocket and handle reconnection
 *   - Load scenario list and populate buttons (via panels.js)
 *   - Start/stop scenarios and drive the 1.2 s auto-tick loop
 *   - Receive ScenarioFrame payloads and dispatch to panel renderers
 */

const WS_URL          = `ws://${location.host}/ws`;
const API_BASE        = '';
const TICK_INTERVAL_MS = 1200;

let ws            = null;
let currentScenario  = null;
let tickInterval   = null;
let wsReconnecting = false;

/* ================================================================== */
/*  Bootstrap                                                           */
/* ================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  loadScenarios();
  connectWebSocket();
});

/* ================================================================== */
/*  WebSocket                                                           */
/* ================================================================== */

function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('[WS] connected');
    wsReconnecting = false;
  };

  ws.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch (_) {
      return;
    }

    if (msg.type === 'scenario_frame') {
      renderFrame(msg.payload);
    } else if (msg.type === 'message') {
      appendCommsEntry(msg.payload);
    } else if (msg.type === 'hazard_cleared') {
      // No action needed — next tick will re-render hazard table
    }
  };

  ws.onerror = () => {
    // Silently ignored; onclose will trigger reconnect
  };

  ws.onclose = () => {
    if (!wsReconnecting) {
      wsReconnecting = true;
      console.log('[WS] disconnected, reconnecting in 2 s…');
      setTimeout(connectWebSocket, 2000);
    }
  };
}

/* ================================================================== */
/*  Scenario management                                                 */
/* ================================================================== */

async function loadScenarios() {
  try {
    const res       = await fetch(`${API_BASE}/api/scenarios/`);
    const scenarios = await res.json();
    renderScenarioButtons(scenarios);
  } catch (err) {
    console.error('[dashboard] Failed to load scenarios:', err);
  }
}

/**
 * Called by onclick on each scenario button (rendered by panels.js).
 * Global so the onclick attribute works.
 */
async function startScenario(id) {
  // Stop any running tick loop
  if (tickInterval) {
    clearInterval(tickInterval);
    tickInterval = null;
  }

  currentScenario = id;

  // Mark button active
  document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`[data-scenario="${id}"]`);
  if (btn) btn.classList.add('active');

  // Clear all panels for a fresh start
  clearPanels();

  // Start scenario on the server
  try {
    await fetch(`${API_BASE}/api/scenarios/${id}/start`, { method: 'POST' });
  } catch (err) {
    console.error('[dashboard] Failed to start scenario:', err);
    return;
  }

  // First tick immediately so something renders right away
  await advanceTick();

  // Auto-advance every TICK_INTERVAL_MS
  tickInterval = setInterval(advanceTick, TICK_INTERVAL_MS);
}

async function advanceTick() {
  if (!currentScenario) return;
  try {
    await fetch(`${API_BASE}/api/scenarios/${currentScenario}/tick`, { method: 'POST' });
    // The server broadcasts the frame over WebSocket; renderFrame() handles it.
  } catch (err) {
    console.warn('[dashboard] Tick failed:', err);
  }
}

/* ================================================================== */
/*  Frame rendering — dispatches to panel renderers in panels.js/map.js*/
/* ================================================================== */

function renderFrame(frame) {
  if (!frame) return;

  updateMapPanel(
    frame.vehicles,
    frame.zones,
    frame.active_hazards,
    frame.messages_this_tick
  );

  updateCameraPanel(frame);
  updateVehicleStatePanel(frame.vehicles, frame.ego_vehicle_id);
  updateRiskPanel(frame.risk_result);
  updateHazardPanel(frame.active_hazards);

  // Append communications messages emitted this tick
  (frame.messages_this_tick || []).forEach(m => appendCommsEntry(m));
}
