"""HTML5 Canvas 60FPS Video Flow Simulation Player.

Provides a flicker-free, 60 FPS continuous traffic animation using 100% full container width:
- Full 100% width responsive layout with zero letterboxing
- Realistic Google Maps Road Network mode with dynamic curved Bezier splines
- Corner A, B, C, D perimeter labeling in the 4 corners
- Clean default state (zero random autonomous cars cluttering the screen)
- Strict FIFO road queuing with 24px car spacing (cars never overlap or stack)
- Single-car selective highlight on tap (no intrusive cards or layout shifts)
- Click any road segment to toggle incidents / hazards with instant dynamic ambulance rerouting
- Emergency ambulance only appears when actively en route, disappears upon arrival
- Play/Pause, 1x/2x/4x speed controls, Google Maps toggle, and quick +5 Cars / Ambulance dispatch
- Simulation step countdown & auto-halt upon tick completion so cars never stall at frozen signals
"""

import json
from typing import Dict, List, Optional, Tuple
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.emergency import EmergencyCorridorManager, AmbulanceMission


def generate_video_canvas_html(
    network: RoadNetwork,
    simulator: TrafficSimulator,
    emergency_mgr: Optional[EmergencyCorridorManager] = None,
    active_mission: Optional[AmbulanceMission] = None,
    marked_vehicle_id: Optional[int] = None,
    block_color: str = "#ff2a5f",
    step_duration: int = 15,
    canvas_width: int = 1200,
    canvas_height: int = 560,
) -> str:
    """Generates a self-contained HTML5 Canvas component that dynamically expands to 100% full width."""
    rows = network.rows
    cols = network.cols

    # Collect nodes data
    nodes_data = []
    junction_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for nid in network.graph.nodes:
        phase = simulator.signal_phases.get(nid, 0)
        lbl = junction_letters[nid] if nid < len(junction_letters) else f"J{nid}"
        r = nid // cols
        c = nid % cols
        nodes_data.append({
            "id": nid,
            "label": lbl,
            "r": r,
            "c": c,
            "phase": phase,  # 0: NS green, 1: EW green
        })

    # Collect edges and accidents
    edges_data = []
    for u, v in network.graph.edges:
        if u < v:
            st_uv = network.graph[u][v].get("status", "open")
            st_vu = network.graph[v][u].get("status", "open") if network.graph.has_edge(v, u) else "open"
            is_accident = (st_uv != "open" or st_vu != "open")
            edges_data.append({
                "u": u,
                "v": v,
                "accident": is_accident,
            })

    # Collect initial seed vehicles from simulator queues & in-transit
    initial_vehicles = []
    for nid in network.graph.nodes:
        queues = simulator.queues[nid]
        for app, v_list in queues.items():
            for veh in v_list:
                initial_vehicles.append({
                    "id": veh.id,
                    "targetNode": nid,
                    "app": app,
                    "marked": (veh.id == marked_vehicle_id),
                })
    for (u_e, v_e), v_list in simulator.in_transit.items():
        for veh in v_list:
            initial_vehicles.append({
                "id": veh.id,
                "u": u_e,
                "v": v_e,
                "marked": (veh.id == marked_vehicle_id),
            })

    # Ambulance mission: only active if a valid, non-completed mission exists
    has_active_mission = (active_mission is not None and not active_mission.completed and active_mission.current_index < len(active_mission.path) - 1)
    amb_path_nodes = []
    amb_driver = ""
    amb_curr_idx = 0
    if has_active_mission:
        amb_path_nodes = list(active_mission.path)
        amb_driver = active_mission.driver_name
        amb_curr_idx = active_mission.current_index

    amb_data = {
        "active": has_active_mission,
        "path": amb_path_nodes,
        "driver": amb_driver,
        "curr_index": amb_curr_idx,
    }

    # Respect manual traffic mode: if manual mode is on, no random cars auto-spawn (autoFlow=false)
    # NOTE: initial_vehicles MUST still be passed so manually-injected vehicles appear on the canvas.
    #       Clearing on mode transition is handled by sim.clear_all_vehicles() in dashboard.py.
    is_auto_flow = not getattr(simulator, "manual_traffic_mode", False)
    is_google_maps = (block_color == "google_maps")

    sim_state = {
        "rows": rows,
        "cols": cols,
        "blockColor": block_color,
        "isGoogleMaps": is_google_maps,
        "stepDuration": step_duration,
        "nodes": nodes_data,
        "edges": edges_data,
        "vehicles": initial_vehicles,
        "ambulance": amb_data,
        "markedId": marked_vehicle_id,
        "autoFlow": is_auto_flow,
    }

    state_json = json.dumps(sim_state)

    html_code = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  * {{
    box-sizing: border-box;
  }}
  html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: #0b0f19;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    overflow: hidden;
    user-select: none;
  }}
  #canvasContainer {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 560px;
    margin: 0;
    padding: 0;
    border-radius: 12px;
    border: 1px solid #1e293b;
    background: #0b0f19;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    overflow: hidden;
  }}
  canvas {{
    display: block;
    width: 100%;
    height: 100%;
    cursor: crosshair;
  }}
  .controls-bar {{
    position: absolute;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 7px;
    align-items: center;
    background: rgba(15, 23, 42, 0.94);
    padding: 6px 14px;
    border-radius: 30px;
    border: 1px solid #334155;
    box-shadow: 0 4px 15px rgba(0,0,0,0.6);
    z-index: 20;
    backdrop-filter: blur(8px);
  }}
  .btn {{
    background: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    border-radius: 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s ease;
    white-space: nowrap;
  }}
  .btn:hover {{
    background: #334155;
    border-color: #64748b;
  }}
  .btn-primary {{
    background: #0284c7;
    border-color: #38bdf8;
    color: #ffffff;
  }}
  .btn-active-map {{
    background: #1e3a5f;
    border-color: #38bdf8;
    color: #38bdf8;
  }}
  .hud-badge {{
    position: absolute;
    top: 10px;
    left: 12px;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid #334155;
    padding: 7px 13px;
    border-radius: 8px;
    font-size: 11px;
    line-height: 1.35;
    z-index: 10;
    backdrop-filter: blur(6px);
  }}
</style>
</head>
<body>

<div id="canvasContainer">
  <div class="hud-badge">
    <div style="display:flex; align-items:center; gap:7px;">
      <span style="width:8px; height:8px; border-radius:50%; background:#10b981; display:inline-block; box-shadow:0 0 8px #10b981;"></span>
      <span style="color:#38bdf8; font-weight:700; letter-spacing:0.6px; font-size:11px;">QUANTUM TRAFFIC BRAIN</span>
      <span id="badgeMode" style="background:rgba(56,189,248,0.15); border:1px solid rgba(56,189,248,0.3); color:#38bdf8; font-size:9px; font-family:monospace; padding:1px 5px; border-radius:3px;">60 FPS ENGINE</span>
    </div>
    <div id="hudDesc" style="color:#94a3b8; font-size:10px; margin-top:3px;">Indian LHT Multi-Directional Turning (Straight / Left / Right) &bull; Select Unit to Inspect</div>
    
    <!-- Simulation Step Countdown & Auto-Halt Progress -->
    <div style="display:flex; align-items:center; gap:8px; margin-top:6px; padding-top:5px; border-top:1px solid rgba(51,65,85,0.6);">
      <div style="font-size:10px; font-family:monospace; color:#38bdf8; font-weight:600;">
        STEP WINDOW: <span id="lblStepTimer" style="color:#f8fafc;">0.0s</span> / <span id="lblStepTotal" style="color:#94a3b8;">{step_duration}.0s</span>
      </div>
      <div style="width:75px; height:5px; background:#334155; border-radius:3px; overflow:hidden;">
        <div id="barStepProgress" style="width:0%; height:100%; background:#10b981; transition:width 0.1s linear;"></div>
      </div>
      <span id="badgeStepStatus" style="font-size:8.5px; font-family:monospace; background:rgba(16,185,129,0.2); color:#10b981; border:1px solid rgba(16,185,129,0.4); padding:1px 5px; border-radius:3px;">ACTIVE</span>
    </div>
  </div>
  <canvas id="simCanvas"></canvas>
  <div class="controls-bar">
    <button id="btnPlay" class="btn btn-primary">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-1px; margin-right:4px;"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>Pause
    </button>
    <button id="btnSpeed" class="btn">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px; margin-right:4px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Speed: 1x
    </button>
    <button id="btnToggleMap" class="btn">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px; margin-right:4px;"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg><span id="lblMapMode">Google Map</span>
    </button>
    <button id="btnAdd5" class="btn">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px; margin-right:4px;"><path d="M12 5v14M5 12h14"/></svg>+5 Vehicles
    </button>
    <button id="btnAmb" class="btn">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00e5ff" stroke-width="2.5" style="vertical-align:-1px; margin-right:4px;"><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 8v8M8 12h8"/></svg>Ambulance Unit 108
    </button>
    <button id="btnClearAccidents" class="btn">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px; margin-right:4px;"><path d="M20 6L9 17l-5-5"/></svg>Clear Incidents
    </button>
    <span style="font-size:11px; color:#94a3b8; margin-left:6px; font-family:monospace;">Active: <span id="lblCarCount" style="color:#38bdf8; font-weight:bold;">0</span></span>
  </div>
</div>

<script>
  const simData = {state_json};
  const canvas = document.getElementById("simCanvas");
  const ctx = canvas.getContext("2d");
  const container = document.getElementById("canvasContainer");

  const dpr = window.devicePixelRatio || 1;
  let width = container.clientWidth || window.innerWidth || 1200;
  let height = container.clientHeight || 560;

  let isGoogleMaps = !!simData.isGoogleMaps;

  // Step Duration Countdown & Auto-Halt State
  const stepDuration = simData.stepDuration || 15.0;
  let elapsedStepTime = 0.0;
  let isStepFinished = false;
  let localSignalTimer = 0.0;

  // Geometry coordinates
  let xRoads = [];
  let yRoads = [];
  const roadW = 34.0;
  const halfRoad = roadW / 2.0;

  function recomputeDimensions() {{
    width = container.clientWidth || window.innerWidth || 1200;
    height = container.clientHeight || 560;
    if (height < 450) height = 560;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.resetTransform ? ctx.resetTransform() : ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    xRoads = [
      Math.round(width * 0.20),
      Math.round(width * 0.50),
      Math.round(width * 0.80),
    ];
    yRoads = [
      Math.round(height * 0.28),
      Math.round(height * 0.72),
    ];
  }}

  recomputeDimensions();
  window.addEventListener("resize", () => {{
    recomputeDimensions();
  }});

  function getNodePos(nid) {{
    if (isGoogleMaps) {{
      const mapPositions = [
        {{ x: Math.round(width * 0.20), y: Math.round(height * 0.26) }}, // J_A
        {{ x: Math.round(width * 0.50), y: Math.round(height * 0.22) }}, // J_B (elevation arch)
        {{ x: Math.round(width * 0.80), y: Math.round(height * 0.27) }}, // J_C
        {{ x: Math.round(width * 0.22), y: Math.round(height * 0.74) }}, // J_D
        {{ x: Math.round(width * 0.52), y: Math.round(height * 0.71) }}, // J_E
        {{ x: Math.round(width * 0.78), y: Math.round(height * 0.76) }}, // J_F
      ];
      return mapPositions[nid] || {{ x: width * 0.5, y: height * 0.5 }};
    }}
    const r = Math.floor(nid / 3);
    const c = nid % 3;
    return {{ x: xRoads[c], y: yRoads[r] }};
  }}

  // Cubic Bezier Evaluator
  function evalBezier(p0, cp1, cp2, p1, t) {{
    const mt = 1 - t;
    const mt2 = mt * mt;
    const t2 = t * t;
    const x = mt2 * mt * p0.x + 3 * mt2 * t * cp1.x + 3 * mt * t2 * cp2.x + t2 * t * p1.x;
    const y = mt2 * mt * p0.y + 3 * mt2 * t * cp1.y + 3 * mt * t2 * cp2.y + t2 * t * p1.y;
    const dx = 3 * mt2 * (cp1.x - p0.x) + 6 * mt * t * (cp2.x - cp1.x) + 3 * t2 * (p1.x - cp2.x);
    const dy = 3 * mt2 * (cp1.y - p0.y) + 6 * mt * t * (cp2.y - cp1.y) + 3 * t2 * (p1.y - cp2.y);
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len;
    const ny = dx / len;
    const angle = Math.atan2(dy, dx);
    return {{ x, y, dx, dy, nx, ny, len, angle }};
  }}

  // Spline Curves for Road Network
  function getEdgeCurve(u, v) {{
    const isRev = (u > v);
    const minNode = isRev ? v : u;
    const maxNode = isRev ? u : v;
    const pA = getNodePos(minNode);
    const pB = getNodePos(maxNode);

    if (!isGoogleMaps) {{
      const cpA = {{ x: (pA.x * 2 + pB.x) / 3, y: (pA.y * 2 + pB.y) / 3 }};
      const cpB = {{ x: (pA.x + pB.x * 2) / 3, y: (pA.y + pB.y * 2) / 3 }};
      return isRev ? {{ p0: pB, cp1: cpB, cp2: cpA, p1: pA }} : {{ p0: pA, cp1: cpA, cp2: cpB, p1: pB }};
    }}

    let cp1, cp2;
    if (minNode === 0 && maxNode === 1) {{ // A - B (North arterial arc)
      cp1 = {{ x: Math.round(width * 0.31), y: Math.round(height * 0.20) }};
      cp2 = {{ x: Math.round(width * 0.41), y: Math.round(height * 0.19) }};
    }} else if (minNode === 1 && maxNode === 2) {{ // B - C (Parkway S-curve)
      cp1 = {{ x: Math.round(width * 0.59), y: Math.round(height * 0.26) }};
      cp2 = {{ x: Math.round(width * 0.70), y: Math.round(height * 0.23) }};
    }} else if (minNode === 3 && maxNode === 4) {{ // D - E (Riverfront boulevard)
      cp1 = {{ x: Math.round(width * 0.33), y: Math.round(height * 0.79) }};
      cp2 = {{ x: Math.round(width * 0.43), y: Math.round(height * 0.77) }};
    }} else if (minNode === 4 && maxNode === 5) {{ // E - F (Commercial highway arc)
      cp1 = {{ x: Math.round(width * 0.61), y: Math.round(height * 0.67) }};
      cp2 = {{ x: Math.round(width * 0.70), y: Math.round(height * 0.71) }};
    }} else if (minNode === 0 && maxNode === 3) {{ // A - D (West serpentine)
      cp1 = {{ x: Math.round(width * 0.16), y: Math.round(height * 0.43) }};
      cp2 = {{ x: Math.round(width * 0.17), y: Math.round(height * 0.57) }};
    }} else if (minNode === 1 && maxNode === 4) {{ // B - E (Central expressway)
      cp1 = {{ x: Math.round(width * 0.54), y: Math.round(height * 0.41) }};
      cp2 = {{ x: Math.round(width * 0.48), y: Math.round(height * 0.55) }};
    }} else if (minNode === 2 && maxNode === 5) {{ // C - F (East coastal avenue)
      cp1 = {{ x: Math.round(width * 0.84), y: Math.round(height * 0.45) }};
      cp2 = {{ x: Math.round(width * 0.83), y: Math.round(height * 0.59) }};
    }} else {{
      cp1 = {{ x: (pA.x * 2 + pB.x) / 3, y: (pA.y * 2 + pB.y) / 3 }};
      cp2 = {{ x: (pA.x + pB.x * 2) / 3, y: (pA.y + pB.y * 2) / 3 }};
    }}

    return isRev ? {{ p0: pB, cp1: cp2, cp2: cp1, p1: pA }} : {{ p0: pA, cp1: cp1, cp2: cp2, p1: pB }};
  }}

  // Inflow Perimeter Curves
  function getInflowCurve(gateId) {{
    if (gateId === "N1") {{
      const p1 = getNodePos(0);
      const p0 = {{ x: Math.round(width * 0.20), y: 0 }};
      const cp1 = {{ x: Math.round(width * 0.20), y: Math.round(p1.y * 0.4) }};
      const cp2 = {{ x: Math.round(p1.x - 4), y: Math.round(p1.y * 0.75) }};
      return {{ p0, cp1, cp2, p1, targetNode: 0, approach: "N" }};
    }} else if (gateId === "N2") {{
      const p1 = getNodePos(1);
      const p0 = {{ x: Math.round(width * 0.50), y: 0 }};
      const cp1 = {{ x: Math.round(width * 0.50), y: Math.round(p1.y * 0.4) }};
      const cp2 = {{ x: Math.round(p1.x), y: Math.round(p1.y * 0.75) }};
      return {{ p0, cp1, cp2, p1, targetNode: 1, approach: "N" }};
    }} else if (gateId === "N3") {{
      const p1 = getNodePos(2);
      const p0 = {{ x: Math.round(width * 0.80), y: 0 }};
      const cp1 = {{ x: Math.round(width * 0.80), y: Math.round(p1.y * 0.4) }};
      const cp2 = {{ x: Math.round(p1.x + 4), y: Math.round(p1.y * 0.75) }};
      return {{ p0, cp1, cp2, p1, targetNode: 2, approach: "N" }};
    }} else if (gateId === "S1") {{
      const p1 = getNodePos(3);
      const p0 = {{ x: Math.round(width * 0.22), y: height }};
      const cp1 = {{ x: Math.round(width * 0.22), y: Math.round(height - (height - p1.y) * 0.4) }};
      const cp2 = {{ x: Math.round(p1.x), y: Math.round(height - (height - p1.y) * 0.75) }};
      return {{ p0, cp1, cp2, p1, targetNode: 3, approach: "S" }};
    }} else if (gateId === "S2") {{
      const p1 = getNodePos(4);
      const p0 = {{ x: Math.round(width * 0.52), y: height }};
      const cp1 = {{ x: Math.round(width * 0.52), y: Math.round(height - (height - p1.y) * 0.4) }};
      const cp2 = {{ x: Math.round(p1.x), y: Math.round(height - (height - p1.y) * 0.75) }};
      return {{ p0, cp1, cp2, p1, targetNode: 4, approach: "S" }};
    }} else if (gateId === "S3") {{
      const p1 = getNodePos(5);
      const p0 = {{ x: Math.round(width * 0.78), y: height }};
      const cp1 = {{ x: Math.round(width * 0.78), y: Math.round(height - (height - p1.y) * 0.4) }};
      const cp2 = {{ x: Math.round(p1.x), y: Math.round(height - (height - p1.y) * 0.75) }};
      return {{ p0, cp1, cp2, p1, targetNode: 5, approach: "S" }};
    }} else if (gateId === "W1") {{
      const p1 = getNodePos(0);
      const p0 = {{ x: 0, y: isGoogleMaps ? Math.round(height * 0.26) : yRoads[0] }};
      const cp1 = {{ x: Math.round(p1.x * 0.35), y: p0.y }};
      const cp2 = {{ x: Math.round(p1.x * 0.70), y: p1.y }};
      return {{ p0, cp1, cp2, p1, targetNode: 0, approach: "W" }};
    }} else if (gateId === "W2") {{
      const p1 = getNodePos(3);
      const p0 = {{ x: 0, y: isGoogleMaps ? Math.round(height * 0.74) : yRoads[1] }};
      const cp1 = {{ x: Math.round(p1.x * 0.35), y: p0.y }};
      const cp2 = {{ x: Math.round(p1.x * 0.70), y: p1.y }};
      return {{ p0, cp1, cp2, p1, targetNode: 3, approach: "W" }};
    }} else if (gateId === "E1") {{
      const p1 = getNodePos(2);
      const p0 = {{ x: width, y: isGoogleMaps ? Math.round(height * 0.27) : yRoads[0] }};
      const cp1 = {{ x: Math.round(width - (width - p1.x) * 0.35), y: p0.y }};
      const cp2 = {{ x: Math.round(width - (width - p1.x) * 0.70), y: p1.y }};
      return {{ p0, cp1, cp2, p1, targetNode: 2, approach: "E" }};
    }} else if (gateId === "E2") {{
      const p1 = getNodePos(5);
      const p0 = {{ x: width, y: isGoogleMaps ? Math.round(height * 0.76) : yRoads[1] }};
      const cp1 = {{ x: Math.round(width - (width - p1.x) * 0.35), y: p0.y }};
      const cp2 = {{ x: Math.round(width - (width - p1.x) * 0.70), y: p1.y }};
      return {{ p0, cp1, cp2, p1, targetNode: 5, approach: "E" }};
    }}
  }}

  // Outflow exit curves – reverse of inflow: car goes FROM junction TO edge of canvas
  function getOutflowCurve(nodeId) {{
    const p0 = getNodePos(nodeId);
    // Map each perimeter node to an off-screen destination
    const exits = [
      {{ x: Math.round(width * 0.20), y: -60 }},  // node 0 exits North
      {{ x: Math.round(width * 0.50), y: -60 }},  // node 1 exits North
      {{ x: Math.round(width * 0.80), y: -60 }},  // node 2 exits North
      {{ x: -60, y: Math.round(height * 0.74) }}, // node 3 exits West
      {{ x: Math.round(width * 0.52), y: height + 60 }}, // node 4 exits South
      {{ x: width + 60, y: Math.round(height * 0.76) }}, // node 5 exits East
    ];
    const dest = exits[nodeId] || {{ x: width / 2, y: -60 }};
    // Build a smooth exit curve from the junction outward
    const dx = dest.x - p0.x;
    const dy = dest.y - p0.y;
    const cp1 = {{ x: p0.x + dx * 0.30, y: p0.y + dy * 0.25 }};
    const cp2 = {{ x: p0.x + dx * 0.65, y: p0.y + dy * 0.65 }};
    return {{ p0, cp1, cp2, p1: dest, isOutflow: true }};
  }}

  let isPlaying = true;
  let simSpeed = 1.0;
  let trackedCarId = simData.markedId;
  let carIdCounter = 200;

  // Vehicles list
  let flowVehicles = [];

  function createFlowCar(opt) {{
    carIdCounter++;
    const baseSpeed = 0.0035;
    return {{
      id: opt.id || carIdCounter,
      edgeKey: opt.edgeKey || "0_1",
      progress: (opt.progress !== undefined) ? opt.progress : 0.0,
      speed: baseSpeed + (Math.random() - 0.5) * 0.0006, // slight speed variance
      marked: opt.marked || false,
      stopped: false,
      isGate: opt.isGate || false,
      isExiting: opt.isExiting || false,
      exitNode: opt.exitNode !== undefined ? opt.exitNode : -1,
      gateId: opt.gateId || null,
      junctionsVisited: opt.junctionsVisited || 0,
      x: opt.x || 0,
      y: opt.y || 0,
      heading: opt.heading || 0,
      lastJunction: -1,
    }};
  }}

  // Spawn perimeter cars at the 10 gates with lane offsets
  function spawnRandomGateCar(preferredGate = null) {{
    const gateChoices = ["N1", "N2", "N3", "S1", "S2", "S3", "W1", "W2", "E1", "E2"];
    let pick = preferredGate || gateChoices[Math.floor(Math.random() * gateChoices.length)];
    const inf = getInflowCurve(pick);
    const pt = evalBezier(inf.p0, inf.cp1, inf.cp2, inf.p1, 0.02);
    flowVehicles.push(createFlowCar({{
      isGate: true,
      gateId: pick,
      edgeKey: `gate_${{pick}}`,
      progress: 0.02,
      x: pt.x + pt.nx * 8,
      y: pt.y + pt.ny * 8,
      heading: pt.angle,
      junctionsVisited: 0,
    }}));
  }}

  // Load simulator vehicles strictly from Python simulator state (queues + in-transit)
  if (simData.vehicles && simData.vehicles.length > 0) {{
      const gateCounts = {{}};
      simData.vehicles.forEach((v, vIdx) => {{
        if (v.u !== undefined && v.v !== undefined) {{
          // In-transit vehicle traversing road segment between u and v
          const u = v.u, wNode = v.v;
          const eCurve = getEdgeCurve(u, wNode);
          const prog = Math.min(0.85, 0.2 + (vIdx % 5) * 0.14);
          const pt = evalBezier(eCurve.p0, eCurve.cp1, eCurve.cp2, eCurve.p1, prog);
          flowVehicles.push(createFlowCar({{
            id: v.id,
            isGate: false,
            edgeKey: `${{u}}_${{wNode}}`,
            progress: prog,
            x: pt.x + pt.nx * 8,
            y: pt.y + pt.ny * 8,
            heading: pt.angle,
            marked: v.marked,
          }}));
          return;
        }}

        let gid = "N1";
        if (v.app === "N") gid = (v.targetNode === 0) ? "N1" : (v.targetNode === 1) ? "N2" : "N3";
        else if (v.app === "S") gid = (v.targetNode === 3) ? "S1" : (v.targetNode === 4) ? "S2" : "S3";
        else if (v.app === "W") gid = (v.targetNode === 0) ? "W1" : "W2";
        else if (v.app === "E") gid = (v.targetNode === 2) ? "E1" : "E2";

        gateCounts[gid] = (gateCounts[gid] || 0) + 1;
        // Stagger progress from entry gate towards junction stopline
        const queueProg = Math.max(0.05, Math.min(0.78, 0.75 - (gateCounts[gid] - 1) * 0.14));

        const inf = getInflowCurve(gid);
        const pt = evalBezier(inf.p0, inf.cp1, inf.cp2, inf.p1, queueProg);
        flowVehicles.push(createFlowCar({{
          id: v.id,
          isGate: true,
          gateId: gid,
          edgeKey: `gate_${{gid}}`,
          progress: queueProg,
          x: pt.x + pt.nx * 8,
          y: pt.y + pt.ny * 8,
          heading: pt.angle,
          marked: v.marked,
        }}));
      }});
  }}

  // Accidents map
  let accidents = {{}};
  simData.edges.forEach(e => {{
    if (e.accident) {{
      accidents[`${{e.u}}_${{e.v}}`] = true;
      accidents[`${{e.v}}_${{e.u}}`] = true;
    }}
  }});

  // Dynamic Dijkstra pathfinder for Ambulance
  function findAmbulancePath(startNode, endNode) {{
    function searchDijkstra(avoidAccidents) {{
      const dist = {{}};
      const prev = {{}};
      const unvisited = new Set();

      simData.nodes.forEach(n => {{
        dist[n.id] = Infinity;
        unvisited.add(n.id);
      }});
      dist[startNode] = 0;

      while (unvisited.size > 0) {{
        let curr = null;
        let minD = Infinity;
        unvisited.forEach(u => {{
          if (dist[u] < minD) {{ minD = dist[u]; curr = u; }}
        }});

        if (curr === null || curr === endNode) break;
        unvisited.delete(curr);

        simData.edges.forEach(e => {{
          let nbr = null;
          if (e.u === curr) nbr = e.v;
          else if (e.v === curr) nbr = e.u;

          if (nbr !== null && unvisited.has(nbr)) {{
            const isAcc = !!(accidents[curr + "_" + nbr] || accidents[nbr + "_" + curr]);
            if (avoidAccidents && isAcc) return;
            const weight = isAcc ? 1000 : 1;
            const alt = dist[curr] + weight;
            if (alt < dist[nbr]) {{
              dist[nbr] = alt;
              prev[nbr] = curr;
            }}
          }}
        }});
      }}

      if (dist[endNode] === Infinity) return null;

      const path = [];
      let step = endNode;
      while (step !== undefined) {{
        path.unshift(step);
        step = prev[step];
      }}
      return (path.length > 1 && path[0] === startNode) ? path : null;
    }}

    let res = searchDijkstra(true);
    if (res) return res;
    res = searchDijkstra(false);
    if (res) return res;
    return null;
  }}

  // Ambulance State
  const ambInitActive = !!(simData.ambulance && simData.ambulance.active);
  let ambulance = {{
    active: ambInitActive,
    isWaiting: false,
    progress: 0.0,
    currSeg: (simData.ambulance && simData.ambulance.curr_index) || 0,
    startNode: (simData.ambulance && simData.ambulance.path && simData.ambulance.path.length > 0) ? simData.ambulance.path[0] : 0,
    targetNode: (simData.ambulance && simData.ambulance.path && simData.ambulance.path.length > 0) ? simData.ambulance.path[simData.ambulance.path.length - 1] : 5,
    pathNodes: (simData.ambulance && simData.ambulance.path && simData.ambulance.path.length > 0) ? simData.ambulance.path : [],
    x: 0,
    y: 0,
    heading: 0,
  }};

  function updateAmbulanceRoute() {{
    if (!ambulance.active) return;
    const currNode = (ambulance.pathNodes && ambulance.pathNodes.length > ambulance.currSeg)
      ? ambulance.pathNodes[ambulance.currSeg]
      : ambulance.startNode;
    const newPath = findAmbulancePath(currNode, ambulance.targetNode);
    if (newPath) {{
      ambulance.pathNodes = newPath;
      ambulance.currSeg = 0;
      ambulance.isWaiting = false;
    }} else {{
      ambulance.isWaiting = true;
    }}
  }}

  // Signals phase lookup
  const signalPhases = {{}};
  simData.nodes.forEach(n => {{
    signalPhases[n.id] = n.phase;
  }});

  // Main Render Loop
  let frameCount = 0;
  function render() {{
    frameCount++;
    ctx.clearRect(0, 0, width, height);

    // Simulation Step Countdown & Auto-Pause Logic
    if (isPlaying) {{
      elapsedStepTime += (1.0 / 60.0) * simSpeed;
      localSignalTimer += (1.0 / 60.0) * simSpeed;

      // When playing past step duration, cycle signals every 10s so cars never stall indefinitely
      if (localSignalTimer >= 10.0) {{
        localSignalTimer = 0.0;
        simData.nodes.forEach(n => {{
          signalPhases[n.id] = (signalPhases[n.id] === 0) ? 1 : 0;
        }});
      }}

      // Step Completion Auto-Halt
      if (elapsedStepTime >= stepDuration) {{
        elapsedStepTime = stepDuration;
        isPlaying = false;
        isStepFinished = true;

        const btnPlay = document.getElementById("btnPlay");
        if (btnPlay) {{
          btnPlay.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-1px; margin-right:4px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>Resume Step`;
          btnPlay.classList.remove("btn-primary");
        }}

        const badgeStatus = document.getElementById("badgeStepStatus");
        if (badgeStatus) {{
          badgeStatus.innerText = "STEP COMPLETE";
          badgeStatus.style.background = "rgba(245, 158, 11, 0.2)";
          badgeStatus.style.color = "#fbbf24";
          badgeStatus.style.borderColor = "rgba(245, 158, 11, 0.4)";
        }}

        const hudDesc = document.getElementById("hudDesc");
        if (hudDesc) {{
          hudDesc.innerHTML = `<span style="color:#fbbf24; font-weight:600;">Simulation step ended (${{stepDuration}}s). Cars held in place. Click 'Auto-Simulate' to compute next quantum phase!</span>`;
        }}
      }}
    }}

    // Update Step Timer UI elements
    const pct = Math.min(100, Math.round((elapsedStepTime / stepDuration) * 100));
    const elTimer = document.getElementById("lblStepTimer");
    if (elTimer) elTimer.innerText = elapsedStepTime.toFixed(1) + "s";
    const elBar = document.getElementById("barStepProgress");
    if (elBar) elBar.style.width = pct + "%";

    // 1. Google Maps or Executive Block Background
    if (isGoogleMaps) {{
      // A. Dark Terrain Base
      ctx.fillStyle = "#1b2029";
      ctx.fillRect(0, 0, width, height);

      // B. Marina Bay River / Canal Feature
      ctx.fillStyle = "#0f1c2d";
      ctx.strokeStyle = "#162a42";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(width * 0.32, height);
      ctx.bezierCurveTo(width * 0.44, height * 0.86, width * 0.62, height * 0.83, width * 0.74, height * 0.66);
      ctx.bezierCurveTo(width * 0.82, height * 0.54, width * 0.90, height * 0.56, width, height * 0.48);
      ctx.lineTo(width, height);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#1e3a5a";
      ctx.font = "italic 11px sans-serif";
      ctx.fillText("Marina Bay Canal", width * 0.74, height * 0.88);

      // C. Urban Nature Reserves / Parks
      // Northern Botanical Reserve
      ctx.fillStyle = "#14281c";
      ctx.strokeStyle = "#1b3827";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(width * 0.28, height * 0.05, width * 0.17, height * 0.16, 10);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#22c55e";
      ctx.font = "10px sans-serif";
      ctx.fillText("Northern Botanical Reserve", width * 0.29, height * 0.09);

      // Central Eco Meadow
      ctx.fillStyle = "#14281c";
      ctx.strokeStyle = "#1b3827";
      ctx.beginPath();
      ctx.roundRect(width * 0.58, height * 0.34, width * 0.18, height * 0.25, 10);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#22c55e";
      ctx.fillText("Central Eco Park", width * 0.59, height * 0.38);

      // D. Urban Building Footprints
      const buildings = [
        {{ x: width * 0.05, y: height * 0.06, w: width * 0.10, h: height * 0.14 }},
        {{ x: width * 0.04, y: height * 0.38, w: width * 0.10, h: height * 0.24 }},
        {{ x: width * 0.05, y: height * 0.82, w: width * 0.12, h: height * 0.11 }},
        {{ x: width * 0.28, y: height * 0.38, w: width * 0.16, h: height * 0.24 }},
        {{ x: width * 0.30, y: height * 0.86, w: width * 0.14, h: height * 0.08 }},
        {{ x: width * 0.86, y: height * 0.06, w: width * 0.10, h: height * 0.15 }},
        {{ x: width * 0.88, y: height * 0.32, w: width * 0.09, h: height * 0.18 }},
        {{ x: width * 0.56, y: height * 0.05, w: width * 0.18, h: height * 0.14 }},
      ];
      ctx.fillStyle = "#232934";
      ctx.strokeStyle = "#303947";
      ctx.lineWidth = 1;
      buildings.forEach(b => {{
        ctx.beginPath();
        ctx.roundRect(b.x, b.y, b.w, b.h, 6);
        ctx.fill();
        ctx.stroke();
      }});

      // E. Road Name Badges
      ctx.font = "bold 9px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("GRAND ARTERIAL (NH-48)", width * 0.31, height * 0.23);
      ctx.fillText("CENTRAL PARKWAY", width * 0.61, height * 0.27);
      ctx.fillText("RIVERSIDE EXPRESSWAY", width * 0.31, height * 0.74);
      ctx.fillText("SOUTHERN CORRIDOR", width * 0.62, height * 0.74);

      // F. Google Maps Watermark & Controls
      ctx.font = "bold 15px -apple-system, BlinkMacSystemFont, sans-serif";
      ctx.fillStyle = "rgba(255, 255, 255, 0.72)";
      ctx.fillText("Google", 20, height - 26);
      ctx.font = "9px monospace";
      ctx.fillStyle = "rgba(148, 163, 184, 0.6)";
      ctx.fillText("Map data ©2026 Google • Imagery ©CNES / Airbus", 20, height - 12);

      // Map style selector pill (top right)
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.strokeStyle = "#334155";
      ctx.beginPath();
      ctx.roundRect(width - 130, 10, 118, 24, 6);
      ctx.fill();
      ctx.stroke();
      ctx.font = "bold 10px sans-serif";
      ctx.fillStyle = "#38bdf8";
      ctx.fillText("Map", width - 118, 26);
      ctx.fillStyle = "#64748b";
      ctx.fillText("|  Satellite", width - 88, 26);

      // Zoom & scale widget (bottom right)
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.strokeStyle = "#334155";
      ctx.beginPath();
      ctx.roundRect(width - 48, height - 74, 34, 58, 6);
      ctx.fill();
      ctx.stroke();
      ctx.font = "bold 14px sans-serif";
      ctx.fillStyle = "#cbd5e1";
      ctx.textAlign = "center";
      ctx.fillText("+", width - 31, height - 56);
      ctx.beginPath();
      ctx.moveTo(width - 42, height - 46);
      ctx.lineTo(width - 20, height - 46);
      ctx.strokeStyle = "#334155";
      ctx.stroke();
      ctx.fillText("-", width - 31, height - 28);
      ctx.textAlign = "left";
    }} else {{
      // Standard Geometric City Blocks
      const bColor = simData.blockColor || "#ff2a5f";
      const blockPad = 6.0;
      const cornerCut = 8.0;

      function drawBlock(x0, y0, x1, y1) {{
        const bw = x1 - x0;
        const bh = y1 - y0;
        if (bw <= 0 || bh <= 0) return;

        ctx.fillStyle = bColor;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(x0, y0, bw, bh, cornerCut);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "rgba(0, 0, 0, 0.08)";
        ctx.beginPath();
        ctx.roundRect(x0 + 4, y0 + 4, bw - 8, bh - 8, 4);
        ctx.fill();
      }}

      drawBlock(12, 12, xRoads[0] - halfRoad - blockPad, yRoads[0] - halfRoad - blockPad);
      drawBlock(12, yRoads[0] + halfRoad + blockPad, xRoads[0] - halfRoad - blockPad, yRoads[1] - halfRoad - blockPad);
      drawBlock(12, yRoads[1] + halfRoad + blockPad, xRoads[0] - halfRoad - blockPad, height - 12);

      drawBlock(xRoads[0] + halfRoad + blockPad, 12, xRoads[1] - halfRoad - blockPad, yRoads[0] - halfRoad - blockPad);
      drawBlock(xRoads[0] + halfRoad + blockPad, yRoads[0] + halfRoad + blockPad, xRoads[1] - halfRoad - blockPad, yRoads[1] - halfRoad - blockPad);
      drawBlock(xRoads[0] + halfRoad + blockPad, yRoads[1] + halfRoad + blockPad, xRoads[1] - halfRoad - blockPad, height - 12);

      drawBlock(xRoads[1] + halfRoad + blockPad, 12, xRoads[2] - halfRoad - blockPad, yRoads[0] - halfRoad - blockPad);
      drawBlock(xRoads[1] + halfRoad + blockPad, yRoads[0] + halfRoad + blockPad, xRoads[2] - halfRoad - blockPad, yRoads[1] - halfRoad - blockPad);
      drawBlock(xRoads[1] + halfRoad + blockPad, yRoads[1] + halfRoad + blockPad, xRoads[2] - halfRoad - blockPad, height - 12);

      drawBlock(xRoads[2] + halfRoad + blockPad, 12, width - 12, yRoads[0] - halfRoad - blockPad);
      drawBlock(xRoads[2] + halfRoad + blockPad, yRoads[0] + halfRoad + blockPad, width - 12, yRoads[1] - halfRoad - blockPad);
      drawBlock(xRoads[2] + halfRoad + blockPad, yRoads[1] + halfRoad + blockPad, width - 12, height - 12);
    }}

    // 2. Draw Dynamic Roads (Straight or Curved Splines)
    // A. Inter-Junction Corridors
    simData.edges.forEach(e => {{
      const c = getEdgeCurve(e.u, e.v);

      // Casing (Curb)
      ctx.strokeStyle = isGoogleMaps ? "#384353" : "#334155";
      ctx.lineWidth = 36;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(c.p0.x, c.p0.y);
      ctx.bezierCurveTo(c.cp1.x, c.cp1.y, c.cp2.x, c.cp2.y, c.p1.x, c.p1.y);
      ctx.stroke();

      // Driving Surface
      ctx.strokeStyle = isGoogleMaps ? "#212732" : "#1e293b";
      ctx.lineWidth = 30;
      ctx.stroke();

      // Centerline Divider
      ctx.strokeStyle = isGoogleMaps ? "#f59e0b" : "#64748b";
      ctx.lineWidth = isGoogleMaps ? 1.6 : 1.2;
      ctx.setLineDash([8, 8]);
      ctx.stroke();
      ctx.setLineDash([]);
    }});

    // B. Perimeter Inflow Roads
    const inGates = ["N1", "N2", "N3", "S1", "S2", "S3", "W1", "W2", "E1", "E2"];
    inGates.forEach(gid => {{
      const ic = getInflowCurve(gid);
      ctx.strokeStyle = isGoogleMaps ? "#384353" : "#334155";
      ctx.lineWidth = 36;
      ctx.beginPath();
      ctx.moveTo(ic.p0.x, ic.p0.y);
      ctx.bezierCurveTo(ic.cp1.x, ic.cp1.y, ic.cp2.x, ic.cp2.y, ic.p1.x, ic.p1.y);
      ctx.stroke();

      ctx.strokeStyle = isGoogleMaps ? "#212732" : "#1e293b";
      ctx.lineWidth = 30;
      ctx.stroke();

      ctx.strokeStyle = isGoogleMaps ? "#f59e0b" : "#64748b";
      ctx.lineWidth = isGoogleMaps ? 1.6 : 1.2;
      ctx.setLineDash([8, 8]);
      ctx.stroke();
      ctx.setLineDash([]);
    }});

    // 3. Four Corners Badges
    ctx.font = "bold 11px monospace";
    ctx.fillStyle = "#38bdf8";
    ctx.fillText("CORNER A", 18, 22);
    ctx.fillText("CORNER B", width - 82, 22);
    ctx.fillText("CORNER C", 18, height - 14);
    ctx.fillText("CORNER D", width - 82, height - 14);

    // 4. Perimeter Entry/Exit Gate Badges
    const gates = [
      {{ lbl: "GATE N1", x: Math.round(width * 0.20), y: 12 }},
      {{ lbl: "GATE N2", x: Math.round(width * 0.50), y: 12 }},
      {{ lbl: "GATE N3", x: Math.round(width * 0.80), y: 12 }},
      {{ lbl: "GATE S1", x: Math.round(width * 0.22), y: height - 12 }},
      {{ lbl: "GATE S2", x: Math.round(width * 0.52), y: height - 12 }},
      {{ lbl: "GATE S3", x: Math.round(width * 0.78), y: height - 12 }},
      {{ lbl: "GATE W1", x: 26, y: isGoogleMaps ? Math.round(height * 0.26) : yRoads[0] }},
      {{ lbl: "GATE W2", x: 26, y: isGoogleMaps ? Math.round(height * 0.74) : yRoads[1] }},
      {{ lbl: "GATE E1", x: width - 26, y: isGoogleMaps ? Math.round(height * 0.27) : yRoads[0] }},
      {{ lbl: "GATE E2", x: width - 26, y: isGoogleMaps ? Math.round(height * 0.76) : yRoads[1] }},
    ];
    ctx.font = "bold 9px monospace";
    gates.forEach(g => {{
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(g.x - 24, g.y - 8, 48, 16, 4);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#34d399";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(g.lbl, g.x, g.y);
    }});

    // 5. Emergency Cyan Wave Corridor (Curved Spline)
    if (ambulance.active && ambulance.pathNodes && ambulance.pathNodes.length > 1) {{
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 5;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      for (let i = 0; i < ambulance.pathNodes.length - 1; i++) {{
        const c = getEdgeCurve(ambulance.pathNodes[i], ambulance.pathNodes[i + 1]);
        if (i === 0) ctx.moveTo(c.p0.x, c.p0.y);
        ctx.bezierCurveTo(c.cp1.x, c.cp1.y, c.cp2.x, c.cp2.y, c.p1.x, c.p1.y);
      }}
      ctx.stroke();

      ctx.strokeStyle = "rgba(0, 229, 255, 0.25)";
      ctx.lineWidth = 14;
      ctx.stroke();
    }}

    // 6. Interactive Incidents on Road Spline Midpoints
    simData.edges.forEach(e => {{
      const c = getEdgeCurve(e.u, e.v);
      const mid = evalBezier(c.p0, c.cp1, c.cp2, c.p1, 0.5);
      const mx = mid.x;
      const my = mid.y;
      const isAcc = accidents[`${{e.u}}_${{e.v}}`];

      if (isAcc) {{
        ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
        ctx.beginPath();
        ctx.arc(mx, my, 16, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#0f172a";
        ctx.beginPath();
        ctx.moveTo(mx, my - 12);
        ctx.lineTo(mx + 12, my);
        ctx.lineTo(mx, my + 12);
        ctx.lineTo(mx - 12, my);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 1.8;
        ctx.stroke();

        ctx.fillStyle = "#ef4444";
        ctx.font = "bold 13px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("!", mx, my);

        ctx.font = "bold 8px monospace";
        ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
        ctx.beginPath();
        ctx.roundRect(mx - 24, my + 14, 48, 12, 3);
        ctx.fill();
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 0.8;
        ctx.stroke();
        ctx.fillStyle = "#f87171";
        ctx.fillText("BLOCKED", mx, my + 20);
      }} else {{
        ctx.fillStyle = "rgba(56, 189, 248, 0.6)";
        ctx.beginPath();
        ctx.moveTo(mx, my - 5);
        ctx.lineTo(mx + 5, my);
        ctx.lineTo(mx, my + 5);
        ctx.lineTo(mx - 5, my);
        ctx.closePath();
        ctx.fill();
      }}
    }});

    // 7. Junction Hubs & Left-Side Full 3-Lens Traffic Signals (Red, Amber, Green)
    simData.nodes.forEach(n => {{
      const pos = getNodePos(n.id);

      // Junction circular hub
      ctx.fillStyle = isGoogleMaps ? "#212732" : "#1e293b";
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 16, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = isGoogleMaps ? "#475569" : "#64748b";
      ctx.lineWidth = 1.8;
      ctx.stroke();

      ctx.fillStyle = "#f8fafc";
      ctx.font = "bold 11px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(n.label, pos.x, pos.y);

      const isNSGreen = (signalPhases[n.id] === 0);

      // Left-side signal placement for Indian LHT (Driver approaching intersection looks to their left)
      // North approach (moving South): Driver is at East side, so left curb is pos.x + 22, pos.y - 28
      // South approach (moving North): Driver is at West side, so left curb is pos.x - 22, pos.y + 28
      // West approach (moving East): Driver is at South side, so left curb is pos.x - 28, pos.y - 22
      // East approach (moving West): Driver is at North side, so left curb is pos.x + 28, pos.y + 22
      const sigs = [
        {{ x: pos.x + 22, y: pos.y - 28, isGreen: isNSGreen, dir: "N" }},
        {{ x: pos.x - 22, y: pos.y + 28, isGreen: isNSGreen, dir: "S" }},
        {{ x: pos.x - 28, y: pos.y - 22, isGreen: !isNSGreen, dir: "W" }},
        {{ x: pos.x + 28, y: pos.y + 22, isGreen: !isNSGreen, dir: "E" }},
      ];

      sigs.forEach(s => {{
        // Mounting post
        ctx.strokeStyle = "#475569";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x, s.y + 14);
        ctx.stroke();

        // 3-Lens Traffic Signal Head Housing (Deep black casing with border)
        const boxW = 10;
        const boxH = 26;
        ctx.fillStyle = "#090d16";
        ctx.beginPath();
        ctx.roundRect(s.x - boxW / 2, s.y - boxH / 2, boxW, boxH, 3.5);
        ctx.fill();
        ctx.strokeStyle = "#334155";
        ctx.lineWidth = 0.9;
        ctx.stroke();

        // Active State Colors
        const isRed = !s.isGreen;
        const isGreen = s.isGreen;
        const isYellow = false; // Middle lens

        // 1. Red Lamp (Top: y - 7.5)
        const redY = s.y - 7.5;
        if (isRed) {{
          // Glowing halo
          ctx.fillStyle = "rgba(239, 68, 68, 0.45)";
          ctx.beginPath();
          ctx.arc(s.x, redY, 7, 0, Math.PI * 2);
          ctx.fill();
          // Vibrant Red Lamp
          ctx.fillStyle = "#ef4444";
          ctx.beginPath();
          ctx.arc(s.x, redY, 3.2, 0, Math.PI * 2);
          ctx.fill();
          // Specular highlight
          ctx.fillStyle = "#fca5a5";
          ctx.beginPath();
          ctx.arc(s.x - 0.8, redY - 0.8, 1.0, 0, Math.PI * 2);
          ctx.fill();
        }} else {{
          // Dimmed inactive red
          ctx.fillStyle = "#261214";
          ctx.beginPath();
          ctx.arc(s.x, redY, 2.8, 0, Math.PI * 2);
          ctx.fill();
        }}

        // 2. Yellow / Amber Lamp (Middle: y)
        const yelY = s.y;
        if (isYellow) {{
          ctx.fillStyle = "rgba(245, 158, 11, 0.45)";
          ctx.beginPath();
          ctx.arc(s.x, yelY, 7, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = "#f59e0b";
          ctx.beginPath();
          ctx.arc(s.x, yelY, 3.2, 0, Math.PI * 2);
          ctx.fill();
        }} else {{
          // Dimmed inactive yellow
          ctx.fillStyle = "#231e11";
          ctx.beginPath();
          ctx.arc(s.x, yelY, 2.8, 0, Math.PI * 2);
          ctx.fill();
        }}

        // 3. Green Lamp (Bottom: y + 7.5)
        const grnY = s.y + 7.5;
        if (isGreen) {{
          // Glowing halo
          ctx.fillStyle = "rgba(16, 185, 129, 0.45)";
          ctx.beginPath();
          ctx.arc(s.x, grnY, 7, 0, Math.PI * 2);
          ctx.fill();
          // Vibrant Green Lamp
          ctx.fillStyle = "#10b981";
          ctx.beginPath();
          ctx.arc(s.x, grnY, 3.2, 0, Math.PI * 2);
          ctx.fill();
          // Specular highlight
          ctx.fillStyle = "#6ee7b7";
          ctx.beginPath();
          ctx.arc(s.x - 0.8, grnY - 0.8, 1.0, 0, Math.PI * 2);
          ctx.fill();
        }} else {{
          // Dimmed inactive green
          ctx.fillStyle = "#0e241b";
          ctx.beginPath();
          ctx.arc(s.x, grnY, 2.8, 0, Math.PI * 2);
          ctx.fill();
        }}

        // Stopline bar on road surface for approaching lane
        ctx.fillStyle = isRed ? "rgba(239, 68, 68, 0.7)" : "rgba(16, 185, 129, 0.5)";
        ctx.fillRect(s.x - 4, s.y + boxH / 2 + 1, 8, 2);
      }});
    }});

    // 8. Vehicle Trajectory Updates Along Curved Road Splines
    if (isPlaying) {{
      flowVehicles.forEach((v, idx) => {{
        // === EXITING CARS: bypass all signal / edge logic, glide off canvas ===
        if (v.isExiting) {{
          v.progress = Math.min(1.02, v.progress + (v.speed || 0.004) * simSpeed * 1.3);
          v.stopped = false;
          return; // rendering happens in the exit/outflow block below
        }}

        let curve;
        let isApproachGreen = false;
        let targetJunction = 0;

        if (v.isGate) {{
          const inf = getInflowCurve(v.gateId);
          curve = inf;
          targetJunction = inf.targetNode;
          const isEW = (inf.approach === "W" || inf.approach === "E");
          isApproachGreen = isEW ? (signalPhases[targetJunction] === 1) : (signalPhases[targetJunction] === 0);
        }} else {{
          const parts = v.edgeKey.split("_").map(Number);
          const u = parts[0], wNode = parts[1];
          curve = getEdgeCurve(u, wNode);
          targetJunction = wNode;
          const isEW = (Math.abs(u - wNode) === 1);
          isApproachGreen = isEW ? (signalPhases[targetJunction] === 1) : (signalPhases[targetJunction] === 0);
        }}

        // Check if car is blocked by red signal or car ahead
        let maxAllowedProgress = 1.0;
        if (!isApproachGreen) {{
          maxAllowedProgress = 0.86;
        }}

        // FIFO queue spacing along same edge
        flowVehicles.forEach((other, oIdx) => {{
          if (oIdx !== idx && other.edgeKey === v.edgeKey && other.progress > v.progress) {{
            const gap = other.progress - 0.09;
            if (gap < maxAllowedProgress) {{
              maxAllowedProgress = Math.max(0.02, gap);
            }}
          }}
        }});

        if (v.progress < maxAllowedProgress) {{
          v.progress = Math.min(maxAllowedProgress, v.progress + v.speed * simSpeed);
          v.stopped = false;
        }} else {{
          v.stopped = true;
        }}

        // Calculate (x, y) and heading angle along Bezier spline
        const pt = evalBezier(curve.p0, curve.cp1, curve.cp2, curve.p1, Math.min(0.99, v.progress));
        v.x = pt.x + pt.nx * 8; // Indian Left-Hand Traffic offset
        v.y = pt.y + pt.ny * 8;
        v.heading = pt.angle;

        // Turn evaluation when reaching intersection on GREEN signal
        if (!v.isExiting && v.progress >= 0.98 && isApproachGreen) {{
          const jId = targetJunction;
          v.junctionsVisited = (v.junctionsVisited || 0) + 1;

          // EXIT PROBABILITY: biased towards leaving after visiting 1+ junctions
          // First crossing: 65% exit. After 2 junctions: 78%. After 3+: 88%
          const exitChance = Math.min(0.88, 0.65 + (v.junctionsVisited - 1) * 0.13);
          const willExit = (Math.random() < exitChance);

          if (willExit) {{
            // Send car on outflow curve towards map edge
            v.isExiting = true;
            v.exitNode = jId;
            v.isGate = false;
            v.progress = 0.01;
            v.lastJunction = jId;
          }} else {{
            // Continue through network – pick a neighbour that is NOT where we came from
            const outbound = [];
            simData.edges.forEach(e => {{
              if (e.u === jId && e.v !== v.lastJunction && !accidents[`${{jId}}_${{e.v}}`]) outbound.push(e.v);
              else if (e.v === jId && e.u !== v.lastJunction && !accidents[`${{jId}}_${{e.u}}`]) outbound.push(e.u);
            }});
            if (outbound.length === 0) {{
              // fallback: any neighbour
              simData.edges.forEach(e => {{
                if (e.u === jId && !accidents[`${{jId}}_${{e.v}}`]) outbound.push(e.v);
                else if (e.v === jId && !accidents[`${{jId}}_${{e.u}}`]) outbound.push(e.u);
              }});
            }}
            if (outbound.length > 0) {{
              const nextNode = outbound[Math.floor(Math.random() * outbound.length)];
              v.isGate = false;
              v.edgeKey = `${{jId}}_${{nextNode}}`;
              v.progress = 0.02;
              v.lastJunction = jId;
            }} else {{
              // no route – exit
              v.isExiting = true;
              v.exitNode = jId;
              v.progress = 0.01;
            }}
          }}
        }}
      }});

      // Clean up cars that exited the network (off-canvas)
      flowVehicles = flowVehicles.filter(v => {{
        if (v.isExiting && v.progress >= 1.0) return false;
        if (!v.isExiting && v.progress > 1.02) return false;
        return true;
      }});

      // Vehicles strictly mirror Python simulator arrivals and queues; no untracked JS phantom spawning.

      // Ambulance Navigation along Curved Splines
      if (ambulance.active && ambulance.pathNodes && ambulance.pathNodes.length > 1) {{
        const currSeg = ambulance.currSeg;
        if (currSeg < ambulance.pathNodes.length - 1) {{
          const u = ambulance.pathNodes[currSeg];
          const v = ambulance.pathNodes[currSeg + 1];
          const isBlocked = !!(accidents[`${{u}}_${{v}}`] || accidents[`${{v}}_${{u}}`]);

          if (isBlocked) {{
            ambulance.isWaiting = true;
          }} else {{
            ambulance.isWaiting = false;
            ambulance.progress += 0.007 * simSpeed;
          }}

          const ambCurve = getEdgeCurve(u, v);
          const apt = evalBezier(ambCurve.p0, ambCurve.cp1, ambCurve.cp2, ambCurve.p1, Math.min(0.99, ambulance.progress));
          ambulance.x = apt.x;
          ambulance.y = apt.y;
          ambulance.heading = apt.angle;

          if (ambulance.progress >= 1.0) {{
            ambulance.progress = 0.0;
            ambulance.currSeg++;
            if (ambulance.currSeg >= ambulance.pathNodes.length - 1) {{
              ambulance.active = false;
              ambulance.isWaiting = false;
            }}
          }}
        }}
      }}
    }}

    // 9. Draw Vehicles (Aerodynamic Pods with Rotated Headlights & Taillights)
    flowVehicles.forEach(v => {{
      const isTracked = (trackedCarId !== null && v.id === trackedCarId);

      // Update position from exit curve if in exit state
      if (v.isExiting && v.exitNode >= 0) {{
        const exitCurve = getOutflowCurve(v.exitNode);
        const exPt = evalBezier(exitCurve.p0, exitCurve.cp1, exitCurve.cp2, exitCurve.p1, Math.min(0.99, v.progress));
        v.x = exPt.x;
        v.y = exPt.y;
        v.heading = exPt.angle;
      }}

      // Fade out exiting vehicles
      ctx.globalAlpha = v.isExiting ? Math.max(0, 1.0 - v.progress * 1.2) : 1.0;

      ctx.save();
      ctx.translate(v.x, v.y);
      ctx.rotate(v.heading);

      // Forward Headlights
      ctx.fillStyle = "rgba(254, 240, 138, 0.4)";
      ctx.beginPath();
      ctx.moveTo(9, -4);
      ctx.lineTo(24, -9);
      ctx.lineTo(24, 9);
      ctx.lineTo(9, 4);
      ctx.closePath();
      ctx.fill();

      // Taillights
      ctx.fillStyle = v.stopped ? "#ef4444" : "#991b1b";
      ctx.fillRect(-10, -5, 2, 2.5);
      ctx.fillRect(-10, 2.5, 2, 2.5);
      if (v.stopped) {{
        ctx.fillStyle = "rgba(239, 68, 68, 0.6)";
        ctx.beginPath();
        ctx.arc(-9, -3.5, 4, 0, Math.PI * 2);
        ctx.arc(-9, 3.5, 4, 0, Math.PI * 2);
        ctx.fill();
      }}

      // Capsule Chassis
      ctx.fillStyle = isTracked ? "#eab308" : "#dc2626";
      ctx.strokeStyle = isTracked ? "#fef08a" : "#fca5a5";
      ctx.lineWidth = isTracked ? 1.8 : 1.0;
      ctx.beginPath();
      ctx.roundRect(-9, -5.5, 18, 11, 4.5);
      ctx.fill();
      ctx.stroke();

      // Windshield
      ctx.fillStyle = "#0f172a";
      ctx.beginPath();
      ctx.roundRect(0, -4, 4.5, 8, 1.5);
      ctx.fill();

      ctx.restore();

      // Tracking Reticle
      if (isTracked) {{
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(v.x, v.y, 16, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
        ctx.beginPath();
        ctx.roundRect(v.x - 26, v.y - 28, 52, 14, 4);
        ctx.fill();
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = "#38bdf8";
        ctx.font = "bold 8px monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`UNIT #${{v.id}}`, v.x, v.y - 21);
      }}

      // Reset opacity after each car
      ctx.globalAlpha = 1.0;
    }});

    // 10. Draw Emergency Ambulance
    if (ambulance.active) {{
      ctx.save();
      ctx.translate(ambulance.x, ambulance.y);
      ctx.rotate(ambulance.heading);

      // Forward Searchlight
      ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
      ctx.beginPath();
      ctx.moveTo(12, -5);
      ctx.lineTo(34, -12);
      ctx.lineTo(34, 12);
      ctx.lineTo(12, 5);
      ctx.closePath();
      ctx.fill();

      // Alternating Strobes
      const flash = (Math.floor(frameCount / 6) % 2 === 0);
      ctx.fillStyle = flash ? "#38bdf8" : "#ef4444";
      ctx.beginPath();
      ctx.arc(-2, -7, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = !flash ? "#38bdf8" : "#ef4444";
      ctx.beginPath();
      ctx.arc(-2, 7, 6, 0, Math.PI * 2);
      ctx.fill();

      // Pod Body
      ctx.fillStyle = "#f8fafc";
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.roundRect(-12, -7, 24, 14, 5);
      ctx.fill();
      ctx.stroke();

      // Medical Cross
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(-2, -5, 4, 10);
      ctx.fillRect(-5, -2, 10, 4);

      ctx.restore();

      // HUD Status Pill
      ctx.font = "bold 9px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const ambText = ambulance.isWaiting ? "STATUS: HOLD (ROADWAY BLOCKED)" : "EMERGENCY UNIT 108 [PRIORITY WAVE]";
      const pW = ctx.measureText(ambText).width + 16;
      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.beginPath();
      ctx.roundRect(ambulance.x - pW / 2, ambulance.y - 28, pW, 16, 4);
      ctx.fill();
      ctx.strokeStyle = ambulance.isWaiting ? "#ef4444" : "#00e5ff";
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.fillStyle = ambulance.isWaiting ? "#f87171" : "#38bdf8";
      ctx.fillText(ambText, ambulance.x, ambulance.y - 20);
    }}

    document.getElementById("lblCarCount").innerText = flowVehicles.length;
  }}

  function loop() {{
    render();
    requestAnimationFrame(loop);
  }}
  requestAnimationFrame(loop);

  // Interactive Click Handlers (Map & Single Car Selection)
  canvas.addEventListener("click", function(evt) {{
    const rect = canvas.getBoundingClientRect();
    const clickX = evt.clientX - rect.left;
    const clickY = evt.clientY - rect.top;

    // 1. Check if user clicked a single car to track (closest car within 18px)
    let clickedCar = null;
    let minDist = 18;
    for (let i = 0; i < flowVehicles.length; i++) {{
      const v = flowVehicles[i];
      const dist = Math.hypot(clickX - v.x, clickY - v.y);
      if (dist < minDist) {{
        minDist = dist;
        clickedCar = v;
      }}
    }}

    if (clickedCar) {{
      trackedCarId = (trackedCarId === clickedCar.id) ? null : clickedCar.id;
      return;
    }}

    // 2. Check if user clicked a road segment to toggle accident
    for (let i = 0; i < simData.edges.length; i++) {{
      const e = simData.edges[i];
      const c = getEdgeCurve(e.u, e.v);
      const mid = evalBezier(c.p0, c.cp1, c.cp2, c.p1, 0.5);
      const dist = Math.hypot(clickX - mid.x, clickY - mid.y);

      if (dist < 32) {{
        const k1 = `${{e.u}}_${{e.v}}`;
        const k2 = `${{e.v}}_${{e.u}}`;
        if (accidents[k1]) {{
          delete accidents[k1];
          delete accidents[k2];
        }} else {{
          accidents[k1] = true;
          accidents[k2] = true;
        }}
        updateAmbulanceRoute();
        return;
      }}
    }}
  }});

  // Button Controls (Zero Emojis, Clean SVG Iconography)
  document.getElementById("btnPlay").addEventListener("click", () => {{
    if (isStepFinished) {{
      elapsedStepTime = 0.0;
      isStepFinished = false;
      isPlaying = true;
      const badgeStatus = document.getElementById("badgeStepStatus");
      if (badgeStatus) {{
        badgeStatus.innerText = "ACTIVE";
        badgeStatus.style.background = "rgba(16,185,129,0.2)";
        badgeStatus.style.color = "#10b981";
        badgeStatus.style.borderColor = "rgba(16,185,129,0.4)";
      }}
      document.getElementById("btnPlay").classList.add("btn-primary");
      document.getElementById("hudDesc").innerText = "Indian LHT Multi-Directional Turning (Straight / Left / Right) • Select Unit to Inspect";
    }} else {{
      isPlaying = !isPlaying;
    }}
    const playSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-1px; margin-right:4px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>Resume Step`;
    const pauseSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-1px; margin-right:4px;"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>Pause`;
    document.getElementById("btnPlay").innerHTML = isPlaying ? pauseSvg : playSvg;
  }});

  document.getElementById("btnSpeed").addEventListener("click", () => {{
    if (simSpeed === 1.0) simSpeed = 2.0;
    else if (simSpeed === 2.0) simSpeed = 4.0;
    else simSpeed = 1.0;
    document.getElementById("btnSpeed").innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px; margin-right:4px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Speed: ${{simSpeed}}x`;
  }});

  const btnMap = document.getElementById("btnToggleMap");
  if (btnMap) {{
    if (isGoogleMaps) btnMap.classList.add("btn-active-map");
    btnMap.addEventListener("click", () => {{
      isGoogleMaps = !isGoogleMaps;
      if (isGoogleMaps) {{
        btnMap.classList.add("btn-active-map");
        document.getElementById("badgeMode").innerText = "GOOGLE MAPS REAL ROADWAY";
        document.getElementById("hudDesc").innerText = "Realistic Curved Arterial Highway Geometry & Google Maps Dark Cartography";
      }} else {{
        btnMap.classList.remove("btn-active-map");
        document.getElementById("badgeMode").innerText = "60 FPS ENGINE";
        document.getElementById("hudDesc").innerText = "Indian LHT Multi-Directional Turning (Straight / Left / Right) • Select Unit to Inspect";
      }}
    }});
  }}

  document.getElementById("btnAdd5").addEventListener("click", () => {{
    if (isStepFinished) {{
      elapsedStepTime = 0.0;
      isStepFinished = false;
      isPlaying = true;
      document.getElementById("btnPlay").classList.add("btn-primary");
      const badgeStatus = document.getElementById("badgeStepStatus");
      if (badgeStatus) {{
        badgeStatus.innerText = "ACTIVE";
        badgeStatus.style.background = "rgba(16,185,129,0.2)";
        badgeStatus.style.color = "#10b981";
        badgeStatus.style.borderColor = "rgba(16,185,129,0.4)";
      }}
    }}
    for (let i = 0; i < 5; i++) spawnRandomGateCar();
  }});

  document.getElementById("btnAmb").addEventListener("click", () => {{
    if (isStepFinished) {{
      elapsedStepTime = 0.0;
      isStepFinished = false;
      isPlaying = true;
      document.getElementById("btnPlay").classList.add("btn-primary");
      const badgeStatus = document.getElementById("badgeStepStatus");
      if (badgeStatus) {{
        badgeStatus.innerText = "ACTIVE";
        badgeStatus.style.background = "rgba(16,185,129,0.2)";
        badgeStatus.style.color = "#10b981";
        badgeStatus.style.borderColor = "rgba(16,185,129,0.4)";
      }}
    }}
    ambulance.startNode = 0;
    ambulance.targetNode = 5;
    ambulance.active = true;
    ambulance.currSeg = 0;
    ambulance.progress = 0.0;
    ambulance.isWaiting = false;
    updateAmbulanceRoute();
  }});

  document.getElementById("btnClearAccidents").addEventListener("click", () => {{
    accidents = {{}};
    if (ambulance.active) {{
      updateAmbulanceRoute();
    }}
  }});
</script>
</body>
</html>
"""
    return html_code
