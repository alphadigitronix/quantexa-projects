"""Interactive 2D Grid Simulation Area Renderer.

Renders a pure, zero-latency 2D simulation area matching a schematic city block grid:
- Rectangular city blocks with white road corridors
- Four outer corners designated as Corner A, Corner B, Corner C, Corner D
- Vehicles represented by RED DOTS
- Ambulances represented by BLUE DOTS
- Traffic signals represented using RED and GREEN lights only
"""

from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go

from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.emergency import EmergencyCorridorManager, AmbulanceMission


def build_simulation_canvas(
    network: RoadNetwork,
    simulator: TrafficSimulator,
    emergency_mgr: Optional[EmergencyCorridorManager] = None,
    active_mission: Optional[AmbulanceMission] = None,
    marked_vehicle_id: Optional[int] = None,
    block_color: str = "#ff2a5f",  # Vibrant coral/pink matching user's reference image
    road_color: str = "#1e293b",   # Clean dark asphalt road surface
    canvas_bg: str = "#0b0f19",
    **kwargs,
) -> go.Figure:
    """Constructs the 2D grid simulation area with red vehicle dots, blue ambulance dot, and red/green signals."""
    rows = network.rows
    cols = network.cols

    if block_color == "google_maps":
        block_color = "#252b36"
        road_color = "#202632"
        canvas_bg = "#1b2029"

    # Coordinate mapping for grid intersections
    # We map col c -> x, row r -> y
    # Coordinate mapping for grid intersections (100% Full-Width Panoramic Grid)
    # We map col c -> x, row r -> y
    x_step = 280.0
    y_step = 140.0
    margin_x = 100.0
    margin_y = 65.0

    width_total = margin_x * 2 + (cols - 1) * x_step
    height_total = margin_y * 2 + (rows - 1) * y_step

    def get_node_xy(node_id: int) -> Tuple[float, float]:
        r = node_id // cols
        c = node_id % cols
        x = margin_x + c * x_step
        y = height_total - (margin_y + r * y_step)
        return x, y

    fig = go.Figure()

    # 1. DRAW CITY BLOCKS (Matching user's reference image with colored blocks and white/dark streets)
    road_w = 32.0  # Width of road corridor
    half_rw = road_w / 2.0

    # Vertical road centerlines: x_centers
    x_roads = [margin_x + c * x_step for c in range(cols)]
    # Horizontal road centerlines: y_centers
    y_roads = [height_total - (margin_y + r * y_step) for r in range(rows)]
    y_roads.sort()

    # Block boundary boundaries
    x_bounds = [0.0] + [xr - half_rw for xr in x_roads] + [xr + half_rw for xr in x_roads] + [width_total]
    x_bounds = sorted(list(set(x_bounds)))

    y_bounds = [0.0] + [yr - half_rw for yr in y_roads] + [yr + half_rw for yr in y_roads] + [height_total]
    y_bounds = sorted(list(set(y_bounds)))

    # Draw rectangular city blocks
    for i in range(len(x_bounds) - 1):
        x0, x1 = x_bounds[i], x_bounds[i + 1]
        # Check if this column interval is inside a road
        is_road_x = any(abs(((x0 + x1) / 2.0) - xr) < half_rw for xr in x_roads)
        if is_road_x:
            continue

        for j in range(len(y_bounds) - 1):
            y0, y1 = y_bounds[j], y_bounds[j + 1]
            is_road_y = any(abs(((y0 + y1) / 2.0) - yr) < half_rw for yr in y_roads)
            if is_road_y:
                continue

            # Draw block shape
            fig.add_shape(
                type="rect",
                x0=x0 + 2,
                y0=y0 + 2,
                x1=x1 - 2,
                y1=y1 - 2,
                line=dict(color="#ffffff", width=1.5),
                fillcolor=block_color,
                layer="below",
            )

    # 2. DRAW ROAD CORRIDORS & LANE DIVIDERS
    # Horizontal roads
    for yr in y_roads:
        fig.add_shape(
            type="rect",
            x0=0,
            y0=yr - half_rw,
            x1=width_total,
            y1=yr + half_rw,
            fillcolor=road_color,
            line=dict(color="#334155", width=1),
            layer="below",
        )
        # Center dashed line
        fig.add_shape(
            type="line",
            x0=0,
            y0=yr,
            x1=width_total,
            y1=yr,
            line=dict(color="#64748b", width=1, dash="dash"),
            layer="below",
        )

    # Vertical roads
    for xr in x_roads:
        fig.add_shape(
            type="rect",
            x0=xr - half_rw,
            y0=0,
            x1=xr + half_rw,
            y1=height_total,
            fillcolor=road_color,
            line=dict(color="#334155", width=1),
            layer="below",
        )
        # Center dashed line
        fig.add_shape(
            type="line",
            x0=xr,
            y0=0,
            x1=xr,
            y1=height_total,
            line=dict(color="#64748b", width=1, dash="dash"),
            layer="below",
        )

    # 3. LABEL THE FOUR CORNERS (Corner A, Corner B, Corner C, Corner D)
    corner_labels = [
        ("CORNER A", 22, height_total - 18, "top left"),
        ("CORNER B", width_total - 22, height_total - 18, "top right"),
        ("CORNER C", 22, 18, "bottom left"),
        ("CORNER D", width_total - 22, 18, "bottom right"),
    ]
    for text, cx, cy, align in corner_labels:
        fig.add_annotation(
            x=cx,
            y=cy,
            text=f"<b>{text}</b>",
            showarrow=False,
            font=dict(color="#ffffff", size=13, family="monospace"),
            bgcolor="rgba(15, 23, 42, 0.90)",
            bordercolor="#38bdf8",
            borderwidth=1.5,
            borderpad=4,
        )

    # 3.1. LABEL ALL 10 ROAD ENTRY/EXIT POINTS (3 North, 3 South, 2 West, 2 East)
    entry_portals = [
        # North entries (Row 0: entering J0, J1, J2 from top)
        ("N1", x_roads[0], height_total - 8, "#22c55e", "Entry N1 (to J_A)"),
        ("N2", x_roads[1], height_total - 8, "#22c55e", "Entry N2 (to J_B)"),
        ("N3", x_roads[2], height_total - 8, "#22c55e", "Entry N3 (to J_C)"),
        # South entries (Row 1: entering J3, J4, J5 from bottom)
        ("S1", x_roads[0], 8, "#22c55e", "Entry S1 (to J_D)"),
        ("S2", x_roads[1], 8, "#22c55e", "Entry S2 (to J_E)"),
        ("S3", x_roads[2], 8, "#22c55e", "Entry S3 (to J_F)"),
        # West entries (Col 0: entering J0, J3 from left)
        ("W1", 12, y_roads[1], "#22c55e", "Entry W1 (to J_A)"),
        ("W2", 12, y_roads[0], "#22c55e", "Entry W2 (to J_D)"),
        # East entries (Col 2: entering J2, J5 from right)
        ("E1", width_total - 12, y_roads[1], "#22c55e", "Entry E1 (to J_C)"),
        ("E2", width_total - 12, y_roads[0], "#22c55e", "Entry E2 (to J_F)"),
    ]

    for label, ex, ey, color, tooltip in entry_portals:
        fig.add_annotation(
            x=ex,
            y=ey,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(color="#ffffff", size=10, family="monospace"),
            bgcolor="rgba(16, 185, 129, 0.9)",
            bordercolor="#ffffff",
            borderwidth=1,
            borderpad=2,
            hovertext=tooltip,
        )

    # 4. HIGHLIGHT ACTIVE AMBULANCE GREEN CORRIDOR ROUTE (Only while en route)
    if active_mission and not active_mission.completed and active_mission.current_index < len(active_mission.path) - 1:
        route_xs = []
        route_ys = []
        for nid in active_mission.path:
            nx, ny = get_node_xy(nid)
            route_xs.append(nx)
            route_ys.append(ny)

        fig.add_trace(go.Scatter(
            x=route_xs,
            y=route_ys,
            mode="lines",
            line=dict(color="#00e5ff", width=8),
            hoverinfo="text",
            hovertext=f"Emergency Green Wave Corridor: {' -> '.join(map(str, active_mission.path))}",
            name="Emergency Corridor",
        ))

    # 5. DRAW TRAFFIC SIGNALS (RED AND GREEN ONLY) & JUNCTION LABELS
    green_signals_x = []
    green_signals_y = []
    green_signals_text = []

    red_signals_x = []
    red_signals_y = []
    red_signals_text = []

    sig_offset = 15.0  # Distance from intersection center to signal stop line

    junction_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for node_id in network.graph.nodes:
        jx, jy = get_node_xy(node_id)
        phase = simulator.signal_phases.get(node_id, 0)
        j_letter = junction_letters[node_id] if node_id < len(junction_letters) else f"J{node_id}"

        # Intersection center badge
        fig.add_annotation(
            x=jx,
            y=jy,
            text=f"<b>{j_letter}</b>",
            showarrow=False,
            font=dict(color="#ffffff", size=12, family="sans-serif"),
            bgcolor="#1e293b",
            bordercolor="#475569",
            borderwidth=1,
            borderpad=3,
        )

        if phase == 0:  # NS GREEN, EW RED
            # North signal is GREEN (facing Southbound traffic driving on East lane x=jx+6; left kerb is at +x)
            green_signals_x.append(jx + 10)
            green_signals_y.append(jy + sig_offset)
            green_signals_text.append(f"Junction {j_letter}: North Signal GREEN [Left Kerb]")

            # South signal is GREEN (facing Northbound traffic driving on West lane x=jx-6; left kerb is at -x)
            green_signals_x.append(jx - 10)
            green_signals_y.append(jy - sig_offset)
            green_signals_text.append(f"Junction {j_letter}: South Signal GREEN [Left Kerb]")

            # East signal is RED (facing Westbound traffic driving on South lane y=jy-6; left kerb is at -y)
            red_signals_x.append(jx + sig_offset)
            red_signals_y.append(jy - 10)
            red_signals_text.append(f"Junction {j_letter}: East Signal RED [Left Kerb]")

            # West signal is RED (facing Eastbound traffic driving on North lane y=jy+6; left kerb is at +y)
            red_signals_x.append(jx - sig_offset)
            red_signals_y.append(jy + 10)
            red_signals_text.append(f"Junction {j_letter}: West Signal RED [Left Kerb]")
        else:  # EW GREEN, NS RED
            # North signal is RED
            red_signals_x.append(jx + 10)
            red_signals_y.append(jy + sig_offset)
            red_signals_text.append(f"Junction {j_letter}: North Signal RED [Left Kerb]")

            # South signal is RED
            red_signals_x.append(jx - 10)
            red_signals_y.append(jy - sig_offset)
            red_signals_text.append(f"Junction {j_letter}: South Signal RED [Left Kerb]")

            # East signal is GREEN
            green_signals_x.append(jx + sig_offset)
            green_signals_y.append(jy - 10)
            green_signals_text.append(f"Junction {j_letter}: East Signal GREEN [Left Kerb]")

            # West signal is GREEN
            green_signals_x.append(jx - sig_offset)
            green_signals_y.append(jy + 10)
            green_signals_text.append(f"Junction {j_letter}: West Signal GREEN [Left Kerb]")

    # Add Green Signals Trace
    if green_signals_x:
        fig.add_trace(go.Scatter(
            x=green_signals_x,
            y=green_signals_y,
            mode="markers",
            marker=dict(
                color="#22c55e",  # Vibrant Green
                size=12,
                symbol="circle",
                line=dict(color="#ffffff", width=1.5),
            ),
            hoverinfo="text",
            hovertext=green_signals_text,
            name="Signal (Green)",
        ))

    # Add Red Signals Trace
    if red_signals_x:
        fig.add_trace(go.Scatter(
            x=red_signals_x,
            y=red_signals_y,
            mode="markers",
            marker=dict(
                color="#ef4444",  # Vibrant Red
                size=12,
                symbol="circle",
                line=dict(color="#ffffff", width=1.5),
            ),
            hoverinfo="text",
            hovertext=red_signals_text,
            name="Signal (Red)",
        ))

    # 5.1. INTERACTIVE ROAD LINK TARGETS & ACCIDENT ZONES (Tap directly on map)
    road_target_x = []
    road_target_y = []
    road_target_text = []
    road_target_custom = []

    accident_x = []
    accident_y = []
    accident_text = []
    accident_custom = []

    checked_pairs = set()
    for u, v in network.graph.edges:
        pair = (min(u, v), max(u, v))
        if pair in checked_pairs:
            continue
        checked_pairs.add(pair)

        ux, uy = get_node_xy(u)
        vx, vy = get_node_xy(v)
        mx = (ux + vx) / 2.0
        my = (uy + vy) / 2.0

        j_u = junction_letters[u] if u < len(junction_letters) else f"J{u}"
        j_v = junction_letters[v] if v < len(junction_letters) else f"J{v}"

        status_uv = network.graph[u][v].get("status", "open")
        status_vu = network.graph[v][u].get("status", "open") if network.graph.has_edge(v, u) else "open"

        if status_uv != "open" or status_vu != "open":
            accident_x.append(mx)
            accident_y.append(my)
            accident_text.append(f"INCIDENT / CLOSED: Road {j_u} <-> {j_v} (Click to reopen)")
            accident_custom.append(f"{u}_{v}")
        else:
            road_target_x.append(mx)
            road_target_y.append(my)
            road_target_text.append(f"Road {j_u} <-> {j_v} (Click to toggle Incident)")
            road_target_custom.append(f"{u}_{v}")

    # Normal clickable road link markers
    if road_target_x:
        fig.add_trace(go.Scatter(
            x=road_target_x,
            y=road_target_y,
            mode="markers",
            marker=dict(
                color="#0284c7",
                size=10,
                symbol="diamond",
                opacity=0.85,
                line=dict(color="#e0f2fe", width=1),
            ),
            hoverinfo="text",
            hovertext=road_target_text,
            customdata=road_target_custom,
            name="Road Waypoint (Incident Toggle)",
        ))

    # Active accident glow markers (Now click-to-clear enabled!)
    if accident_x:
        fig.add_trace(go.Scatter(
            x=accident_x,
            y=accident_y,
            mode="markers+text",
            marker=dict(
                color="#f97316",
                size=18,
                symbol="triangle-up",
                line=dict(color="#ffffff", width=2),
            ),
            text=["INCIDENT / CLOSED"] * len(accident_x),
            textposition="top center",
            textfont=dict(color="#fb923c", size=10, family="monospace"),
            hoverinfo="text",
            hovertext=accident_text,
            customdata=accident_custom,
            name="Incident Zone",
        ))

    # 6. DRAW REGULAR VEHICLES (RED DOTS) & MARKED TRACKED VEHICLE (GOLD STAR)
    veh_x = []
    veh_y = []
    veh_text = []
    veh_custom = []

    marked_x = []
    marked_y = []
    marked_text = []
    marked_custom = []

    dot_spacing = 8.0
    for node_id in network.graph.nodes:
        jx, jy = get_node_xy(node_id)
        queues = simulator.queues[node_id]

        # North queue (traffic traveling South): Left side of travel is East (+x => jx + 6)
        for idx, veh in enumerate(queues["N"]):
            px = jx + 6
            py = jy + sig_offset + 5.0 + idx * dot_spacing
            if py < height_total - 10:
                t_str = f"Vehicle #{veh.id} (Queued at N | Wait: {veh.waiting_ticks}s)"
                c_str = f"car_{veh.id}"
                if marked_vehicle_id is not None and veh.id == marked_vehicle_id:
                    marked_x.append(px)
                    marked_y.append(py)
                    marked_text.append(f"INSPECTED Vehicle #{veh.id} (Waiting at Junction {junction_letters[node_id]} N | {veh.waiting_ticks}s)")
                    marked_custom.append(c_str)
                else:
                    veh_x.append(px)
                    veh_y.append(py)
                    veh_text.append(t_str)
                    veh_custom.append(c_str)

        # South queue (traffic traveling North): Left side of travel is West (-x => jx - 6)
        for idx, veh in enumerate(queues["S"]):
            px = jx - 6
            py = jy - sig_offset - 5.0 - idx * dot_spacing
            if py > 10:
                t_str = f"Vehicle #{veh.id} (Queued at S | Wait: {veh.waiting_ticks}s)"
                c_str = f"car_{veh.id}"
                if marked_vehicle_id is not None and veh.id == marked_vehicle_id:
                    marked_x.append(px)
                    marked_y.append(py)
                    marked_text.append(f"INSPECTED Vehicle #{veh.id} (Waiting at Junction {junction_letters[node_id]} S | {veh.waiting_ticks}s)")
                    marked_custom.append(c_str)
                else:
                    veh_x.append(px)
                    veh_y.append(py)
                    veh_text.append(t_str)
                    veh_custom.append(c_str)

        # West queue (traffic traveling East): Left side of travel is North (+y => jy + 6)
        for idx, veh in enumerate(queues["W"]):
            px = jx - sig_offset - 5.0 - idx * dot_spacing
            py = jy + 6
            if px > 10:
                t_str = f"Vehicle #{veh.id} (Queued at W | Wait: {veh.waiting_ticks}s)"
                c_str = f"car_{veh.id}"
                if marked_vehicle_id is not None and veh.id == marked_vehicle_id:
                    marked_x.append(px)
                    marked_y.append(py)
                    marked_text.append(f"INSPECTED Vehicle #{veh.id} (Waiting at Junction {junction_letters[node_id]} W | {veh.waiting_ticks}s)")
                    marked_custom.append(c_str)
                else:
                    veh_x.append(px)
                    veh_y.append(py)
                    veh_text.append(t_str)
                    veh_custom.append(c_str)

        # East queue (traffic traveling West): Left side of travel is South (-y => jy - 6)
        for idx, veh in enumerate(queues["E"]):
            px = jx + sig_offset + 5.0 + idx * dot_spacing
            py = jy - 6
            if px < width_total - 10:
                t_str = f"Vehicle #{veh.id} (Queued at E | Wait: {veh.waiting_ticks}s)"
                c_str = f"car_{veh.id}"
                if marked_vehicle_id is not None and veh.id == marked_vehicle_id:
                    marked_x.append(px)
                    marked_y.append(py)
                    marked_text.append(f"INSPECTED Vehicle #{veh.id} (Waiting at Junction {junction_letters[node_id]} E | {veh.waiting_ticks}s)")
                    marked_custom.append(c_str)
                else:
                    veh_x.append(px)
                    veh_y.append(py)
                    veh_text.append(t_str)
                    veh_custom.append(c_str)

    # In-transit vehicles on road corridors
    for (u, v), v_list in simulator.in_transit.items():
        ux, uy = get_node_xy(u)
        vx, vy = get_node_xy(v)
        edge_time = max(1, network.graph[u][v].get("free_flow_travel_time", 12))

        for veh in v_list:
            frac = min(1.0, max(0.0, 1.0 - (veh.in_transit_ticks_remaining / edge_time)))
            # Lane offset
            dx = vx - ux
            dy = vy - uy
            norm = (dx**2 + dy**2)**0.5
            if norm > 0:
                off_x = (-dy / norm) * 6
                off_y = (dx / norm) * 6
            else:
                off_x, off_y = 0, 0

            px = ux + dx * frac + off_x
            py = uy + dy * frac + off_y
            t_str = f"Vehicle #{veh.id} (In Transit: {junction_letters[u]} -> {junction_letters[v]})"
            c_str = f"car_{veh.id}"
            if marked_vehicle_id is not None and veh.id == marked_vehicle_id:
                marked_x.append(px)
                marked_y.append(py)
                marked_text.append(f"INSPECTED Vehicle #{veh.id} (Cruising: {junction_letters[u]} -> {junction_letters[v]})")
                marked_custom.append(c_str)
            else:
                veh_x.append(px)
                veh_y.append(py)
                veh_text.append(t_str)
                veh_custom.append(c_str)

    # Regular Red Dots
    if veh_x:
        fig.add_trace(go.Scatter(
            x=veh_x,
            y=veh_y,
            mode="markers",
            marker=dict(
                color="#ff3b30",  # RED DOTS
                size=9,
                symbol="circle",
                line=dict(color="#ffffff", width=1),
            ),
            selected=dict(marker=dict(opacity=1)),
            unselected=dict(marker=dict(opacity=1)),
            hoverinfo="text",
            hovertext=veh_text,
            customdata=veh_custom,
            name="Active Vehicles",
        ))

    # Highlighted Tracked Vehicle (Gold Star)
    if marked_x:
        fig.add_trace(go.Scatter(
            x=marked_x,
            y=marked_y,
            mode="markers+text",
            marker=dict(
                color="#facc15",  # Glowing Gold
                size=18,
                symbol="star",
                line=dict(color="#ffffff", width=2.5),
            ),
            text=[f"UNIT #{marked_vehicle_id}"],
            textposition="bottom center",
            textfont=dict(color="#facc15", size=11, family="monospace"),
            hoverinfo="text",
            hovertext=marked_text,
            customdata=marked_custom,
            name="Inspected Unit",
        ))

    # 7. DRAW AMBULANCE (BLUE DOT)
    # Ambulance marker: only visible while actively en route to destination
    if active_mission and not active_mission.completed and active_mission.current_index < len(active_mission.path) - 1:
        u_node = active_mission.path[active_mission.current_index]
        v_node = active_mission.path[active_mission.current_index + 1]
        ux, uy = get_node_xy(u_node)
        vx, vy = get_node_xy(v_node)

        edge_time = max(1.0, network.graph[u_node][v_node].get("free_flow_travel_time", 12.0) / 1.5)
        frac = min(1.0, max(0.0, active_mission.current_edge_progress_sec / edge_time))
        amb_x = ux + (vx - ux) * frac
        amb_y = uy + (vy - uy) * frac

        # Large glowing blue dot
        fig.add_trace(go.Scatter(
            x=[amb_x],
            y=[amb_y],
            mode="markers+text",
            marker=dict(
                color="#00e5ff",  # BLUE DOT
                size=22,
                symbol="circle",
                line=dict(color="#ffffff", width=3),
            ),
            text=["<b>EMERGENCY UNIT</b>"],
            textposition="top center",
            textfont=dict(color="#00e5ff", size=12, family="monospace"),
            hoverinfo="text",
            hovertext=f"{active_mission.driver_name} (Priority Emergency Dispatch)",
            name="Emergency Unit",
        ))

    # Configure layout to be clean, sharp, and perfectly framed
    # Configure layout to be clean, sharp, and span 100% full container width
    fig.update_layout(
        plot_bgcolor=canvas_bg,
        paper_bgcolor=canvas_bg,
        xaxis=dict(
            visible=False,
            range=[0, width_total],
            fixedrange=True,
        ),
        yaxis=dict(
            visible=False,
            range=[0, height_total],
            fixedrange=True,
        ),
        autosize=True,
        margin=dict(l=0, r=0, t=10, b=10),
        height=540,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(color="#94a3b8", size=11),
            bgcolor="rgba(15, 23, 42, 0.7)",
            bordercolor="#334155",
            borderwidth=1,
        ),
    )

    return fig
