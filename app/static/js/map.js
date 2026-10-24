/* jshint esversion: 6 */
/**
 * map.js — Bird's-Eye Canvas Renderer
 * Draws vehicles, zones, hazards, and message arcs on the HTML5 canvas.
 */

const MAP_SCALE    = 0.55;   // pixels per metre
const MAP_OFFSET_X = 250;    // canvas logical centre x
const MAP_OFFSET_Y = 200;    // canvas logical centre y

const VEHICLE_COLORS = {
  CAR_A:        '#3b82f6',   // blue  — ego vehicle
  CAR_B:        '#16a34a',   // green
  CAR_C:        '#d97706',   // amber
  CAR_D:        '#7c5cd8',   // purple
  CAR_HIGHWAY:  '#16a34a',
  CAR_MERGE:    '#d97706',
  CAR_WRONG:    '#dc2626',   // red   — wrong-way vehicle
  default:      '#57606a',
};

const HAZARD_COLOR = '#dc2626';
const ZONE_COLOR   = 'rgba(59,130,246,0.10)';
const ZONE_STROKE  = '#3b82f6';

/* ------------------------------------------------------------------ */
/*  Public entry-point — called from dashboard.js on each frame        */
/* ------------------------------------------------------------------ */

/**
 * @param {Object} vehicles   - dict vehicle_id → VehicleState (already .model_dump'd)
 * @param {Array}  zones      - list of ManeuverZone dicts
 * @param {Array}  hazards    - list of HazardMessage dicts
 * @param {Array}  messages   - list of CooperativeMessage dicts sent this tick
 */
function updateMapPanel(vehicles, zones, hazards, messages) {
  const canvas = document.getElementById('map-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Background fill
  ctx.fillStyle = '#f9fafb';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  drawRoad(ctx);

  (zones    || []).forEach(z  => drawZone(ctx, z));
  (hazards  || []).forEach(h  => drawHazard(ctx, h));
  drawMessageArcs(ctx, messages, vehicles);

  Object.values(vehicles || {}).forEach(v => drawVehicle(ctx, v));
}

/* ------------------------------------------------------------------ */
/*  Coordinate transform                                                */
/* ------------------------------------------------------------------ */

function worldToCanvas(x, y) {
  return {
    cx: MAP_OFFSET_X + x * MAP_SCALE,
    cy: MAP_OFFSET_Y - y * MAP_SCALE,   // y-axis flipped (world y-up → canvas y-down)
  };
}

/* ------------------------------------------------------------------ */
/*  Road                                                                */
/* ------------------------------------------------------------------ */

function drawRoad(ctx) {
  const W = 500, H = 400;

  // Road surface bands (horizontal lane area)
  ctx.fillStyle = '#e2e8f0';
  ctx.fillRect(0, MAP_OFFSET_Y - 30, W, 60);
  // Vertical road for intersection scenarios
  ctx.fillStyle = '#e9eef4';
  ctx.fillRect(MAP_OFFSET_X - 30, 0, 60, H);

  // Lane centre-line (dashed yellow)
  ctx.save();
  ctx.setLineDash([10, 8]);
  ctx.strokeStyle = '#fbbf24';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(0, MAP_OFFSET_Y);
  ctx.lineTo(W, MAP_OFFSET_Y);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(MAP_OFFSET_X, 0);
  ctx.lineTo(MAP_OFFSET_X, H);
  ctx.stroke();
  ctx.restore();

  // Road edges (solid white)
  ctx.strokeStyle = '#94a3b8';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(0, MAP_OFFSET_Y - 30);
  ctx.lineTo(W, MAP_OFFSET_Y - 30);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(0, MAP_OFFSET_Y + 30);
  ctx.lineTo(W, MAP_OFFSET_Y + 30);
  ctx.stroke();

  // Compass label
  ctx.fillStyle = '#94a3b8';
  ctx.font = '9px sans-serif';
  ctx.fillText('N ↑', W - 26, 12);
}

/* ------------------------------------------------------------------ */
/*  Zones                                                               */
/* ------------------------------------------------------------------ */

function drawZone(ctx, zone) {
  if (!zone.center) return;
  const { cx, cy } = worldToCanvas(zone.center.x, zone.center.y);
  const r = (zone.radius_m || 40) * MAP_SCALE;

  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, 2 * Math.PI);
  ctx.fillStyle   = ZONE_COLOR;
  ctx.fill();
  ctx.strokeStyle = ZONE_STROKE;
  ctx.lineWidth   = 1;
  ctx.setLineDash([4, 4]);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = '#3b82d4';
  ctx.font      = '9px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(zone.zone_type || '', cx, cy + 4);
  ctx.textAlign = 'left';
}

/* ------------------------------------------------------------------ */
/*  Hazard markers                                                      */
/* ------------------------------------------------------------------ */

function drawHazard(ctx, hazard) {
  if (!hazard.position) return;
  const { cx, cy } = worldToCanvas(hazard.position.x, hazard.position.y);

  ctx.beginPath();
  ctx.arc(cx, cy, 9, 0, 2 * Math.PI);
  ctx.fillStyle = '#fee2e2';
  ctx.fill();
  ctx.strokeStyle = HAZARD_COLOR;
  ctx.lineWidth   = 2;
  ctx.stroke();

  ctx.fillStyle  = HAZARD_COLOR;
  ctx.font       = '11px sans-serif';
  ctx.textAlign  = 'center';
  ctx.fillText('⚠', cx, cy + 4);
  ctx.textAlign  = 'left';

  // Tiny label
  ctx.fillStyle  = HAZARD_COLOR;
  ctx.font       = '8px sans-serif';
  ctx.fillText(hazard.hazard_type || '', cx + 12, cy - 4);
}

/* ------------------------------------------------------------------ */
/*  Message arcs                                                        */
/* ------------------------------------------------------------------ */

function drawMessageArcs(ctx, messages, vehicles) {
  if (!messages || !vehicles) return;
  messages.forEach(msg => {
    const src = vehicles[msg.source_vehicle];
    if (!src || !msg.intended_recipients || !msg.intended_recipients.length) return;

    const s = worldToCanvas(src.position.x, src.position.y);
    const color = msg.priority === 'URGENT'        ? '#dc2626' :
                  msg.priority === 'HIGH_PRIORITY' ? '#d97706' : '#3b82d4';

    msg.intended_recipients.forEach(rid => {
      const dst = vehicles[rid];
      if (!dst) return;
      const d  = worldToCanvas(dst.position.x, dst.position.y);
      const mx = (s.cx + d.cx) / 2;
      const my = Math.min(s.cy, d.cy) - 28;

      ctx.beginPath();
      ctx.moveTo(s.cx, s.cy);
      ctx.quadraticCurveTo(mx, my, d.cx, d.cy);
      ctx.strokeStyle = color;
      ctx.lineWidth   = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrowhead near destination
      _drawArrow(ctx, mx, my, d.cx, d.cy, color);
    });
  });
}

function _drawArrow(ctx, fromX, fromY, toX, toY, color) {
  const angle  = Math.atan2(toY - fromY, toX - fromX);
  const aLen   = 6;
  const aWidth = 0.4;
  ctx.beginPath();
  ctx.moveTo(toX, toY);
  ctx.lineTo(toX - aLen * Math.cos(angle - aWidth), toY - aLen * Math.sin(angle - aWidth));
  ctx.lineTo(toX - aLen * Math.cos(angle + aWidth), toY - aLen * Math.sin(angle + aWidth));
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

/* ------------------------------------------------------------------ */
/*  Vehicles                                                            */
/* ------------------------------------------------------------------ */

function drawVehicle(ctx, vehicle) {
  if (!vehicle.position) return;
  const { cx, cy } = worldToCanvas(vehicle.position.x, vehicle.position.y);
  const color      = VEHICLE_COLORS[vehicle.vehicle_id] || VEHICLE_COLORS.default;
  const heading    = (vehicle.heading_degrees || 0);

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((heading - 90) * Math.PI / 180);

  // Car body
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(-10, -6, 22, 12, 3);
  ctx.fill();

  // Heading arrow (white chevron)
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.beginPath();
  ctx.moveTo(10, 0);
  ctx.lineTo(5, -4);
  ctx.lineTo(5,  4);
  ctx.closePath();
  ctx.fill();

  ctx.restore();

  // --- Label (vehicle ID) ---
  ctx.font      = 'bold 10px sans-serif';
  ctx.fillStyle = '#1f2328';
  ctx.fillText(vehicle.vehicle_id, cx + 14, cy - 6);

  // Speed label
  const speed = vehicle.speed_mph != null ? vehicle.speed_mph.toFixed(0) : '?';
  ctx.font      = '9px sans-serif';
  ctx.fillStyle = '#57606a';
  ctx.fillText(`${speed} mph`, cx + 14, cy + 5);
}
