# Quantum Traffic Brain

> **Quantum-Enhanced Adaptive Urban Traffic Optimization System**
> Built for Hack-Quant · Real Chennai junctions · YOLOv8 + QAOA

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Project Structure](#project-structure)
4. [Module Reference](#module-reference)
5. [Dashboard Pages](#dashboard-pages)
6. [End-to-End System Flow](#end-to-end-system-flow)
7. [Quantum Optimization Pipeline](#quantum-optimization-pipeline)
8. [Emergency Corridor System](#emergency-corridor-system)
9. [Vehicle Detection Pipeline](#vehicle-detection-pipeline)
10. [Configuration Parameters](#configuration-parameters)
11. [Installation & Running](#installation--running)
12. [Running on Real Quantum Hardware](#running-on-real-quantum-hardware)
13. [Known Limitations](#known-limitations)


---



## Overview

**Quantum Traffic Brain** is a real-time, browser-based traffic signal optimization dashboard.
It simulates a 2x3 grid of six real Chennai intersections, optimizes signal phases using
**QAOA** (Quantum Approximate Optimization Algorithm) encoded as a **QUBO** problem,
handles emergency ambulance routing with dynamic signal preemption, and accepts live vehicle
counts from CCTV images/videos using **YOLOv8n** computer vision.

The entire application runs in a single **Streamlit** process — no database needed.

### Where Quantum is Used and Why We Don't Claim Advantage
In this project, quantum computing via QAOA (Quantum Approximate Optimization Algorithm) is utilized to optimize binary traffic signal phases mapped to a QUBO / Ising cost Hamiltonian. We maintain rigorous scientific transparency:
1. **Pipeline Validation**: The formulation is validated end-to-end on quantum simulators (PennyLane `default.qubit` and Amazon Braket local simulator), including formal unit tests verifying QUBO-to-Ising Hamiltonian mapping equivalence and ground-truth comparison against exact brute force.
2. **Exact Solver Baseline**: The headline benchmark performance figures in this report come from the exact classical Brute-Force solver ($2^6 = 64$ states evaluated in <0.5 ms).
3. **QAOA is an Approximation Algorithm**: Because QAOA (p=2) achieves a 91%–95% approximation ratio and finds the exact ground-truth optimum in 33%–60% of rounds, QAOA traffic wait time is slightly higher (+1.7s to +5.7s) than exact brute force.
4. **Coupling Terms & Separability**: In empirical ablation experiments on this 6-intersection network, the quadratic network coupling terms ($W_{\text{coord}}$ and $W_{\text{spillback}}$) that would theoretically make the problem non-separable provided no delay benefit over independent per-intersection greedy decisions.
5. **No Advantage Claim**: We make no claim of quantum advantage or supremacy. This repository demonstrates a verified, quantum-ready pipeline for urban traffic optimization.

---

## Architecture Diagram

```
+---------------------------------------------------------------+
|                     STREAMLIT DASHBOARD                       |
|  +---------------+  +---------------------+  +------------+  |
|  |   Sidebar     |  |  Live Canvas Tab    |  | Diagnostics|  |
|  |  (Controls)   |  |  (HTML/JS iframe)   |  | (Plotly)   |  |
|  +-------+-------+  +---------+-----------+  +------+-----+  |
|          |                    |                      |        |
|  +-------+--------------------+----------------------+------+ |
|  |                    Python Backend                         | |
|  |  RoadNetwork <-> TrafficSimulator <-> HybridController   | |
|  |      |                  |                    |            | |
|  |  EmergencyMgr <-> EventsEngine <-> QUBO + QAOA/BF       | |
|  |      |                  |                                 | |
|  |  MetricsEngine     SecurityService     VehicleDetector   | |
|  +-------------------------------------------------------+--+ |
+---------------------------------------------------------------+
```

---

## Project Structure

```
hack-quant/
├── dashboard.py              <- Main Streamlit entrypoint (Simulation + Hospital Google Maps routing)
├── benchmark.py              <- CLI multi-seed benchmark runner
├── yolov8n.pt                <- YOLOv8 nano weights (6.2 MB, auto-downloaded)
├── results/                  <- Empirical benchmarks & scientific artifacts (JSON, PNG, CSV)
└── traffic_quantum/
    ├── config.py             <- All constants, weights, and hyperparameters
    ├── network.py            <- NetworkX road graph (2x3 directed grid, Chennai coordinates)
    ├── simulator.py          <- Tick-based traffic simulation engine (queues & physics)
    ├── video_canvas.py       <- HTML/CSS/JS animated live canvas generator
    ├── vision.py             <- YOLOv8 + classical CV vehicle detector
    ├── emergency.py          <- Ambulance mission + green corridor manager + conflict arbiter
    ├── hospital_maps.py      <- Standalone Paramedic Hospital Google Maps console (/?page=hospital_maps)
    ├── signal_interface.py   <- Hardware-ready abstraction, Conflict Monitor, Watchdog
    ├── events.py             <- Dynamic events engine (accidents, surges, closures)
    ├── metrics.py            <- Performance + environmental metrics engine
    ├── security.py           <- JWT auth, rate limiting, append-only SHA-256 audit logging
    ├── canvas.py             <- Plotly static diagnostic canvas builder
    ├── benchmark.py          <- Multi-seed controller comparison runner
    ├── requirements.txt
    ├── controllers/
    │   ├── base.py           <- Abstract controller interface
    │   ├── hybrid.py         <- Quantum-classical hybrid controller (QAOA / Brute-Force)
    │   ├── rule_based.py     <- Greedy queue-length rule controller
    │   └── fixed.py          <- Fixed 30s/30s cycle baseline
    ├── quantum/
    │   ├── qubo.py           <- QUBO matrix builder from live traffic state
    │   ├── qaoa.py           <- Manual PennyLane QAOA solver (p=1 to 4)
    │   ├── ising.py          <- QUBO to Ising model converter
    │   ├── brute_force.py    <- Exact 2^N brute-force solver (verification)
    │   ├── simulated_annealing.py <- Classical simulated annealing benchmark solver
    │   └── braket_runner.py  <- Amazon Braket Quantum & SV1/IonQ runner
    └── tests/                <- Unit tests across 14 test suites (100% passing)
        ├── test_baselines.py
        ├── test_emergency_conflict.py
        ├── test_emergency_corridor.py
        ├── test_events.py
        ├── test_hybrid_timing.py
        ├── test_pedestrians.py
        ├── test_qaoa_vs_brute_force.py
        ├── test_qubo_ising_equivalence.py
        ├── test_scenarios.py
        ├── test_security.py
        ├── test_signal_interface.py
        ├── test_simulated_annealing.py
        ├── test_simulator_determinism.py
        └── test_vision.py
```

---

## Module Reference

### dashboard.py (Root Level)

**Role:** Single Streamlit entrypoint — all UI, state, buttons, and callbacks.

**Responsibilities:**
- Initialises `RoadNetwork`, `TrafficSimulator`, `HybridController`, `EmergencyCorridorManager`, `EventsEngine`, `MetricsEngine`, `SecurityService` in `st.session_state`
- Renders sidebar: city theme, traffic mode, live control, controller choice
- Builds main tabs: *Live Traffic Canvas* and *Diagnostic Analytics*
- Manages the *Traffic Inflow Expander* (gate inputs + CCTV upload + YOLOv8 detection)
- Handles ambulance dispatch, road events, metrics display, security panel, benchmark launcher
- Calls `sim.step()` + `controller.compute_phases(sim)` + `sim.set_signal_phases(phases)` each tick
- Detects Auto→Manual mode transition and calls `sim.clear_all_vehicles()` to wipe the map
- Injects AI-detected vehicle counts into simulator entry gates via `sim.inject_by_entry_name()`

---

### config.py

**Role:** Single source of truth for every constant and hyperparameter.

| Dataclass | What it configures |
|---|---|
| `NetworkConfig` | Grid size (2x3), road length (150 m), capacity (20 veh/edge), Chennai GPS coordinates |
| `SimulationConfig` | Tick duration (1 s), Poisson arrival rate (0.35/tick), discharge interval (2 ticks) |
| `QUBOConfig` | Cost weights: queue (1.0), coordination (0.2), spillback (0.5), switching (1.0), emergency (50.0), pedestrian (2.0) |
| `QAOAConfig` | p=2 layers, 35 COBYLA iterations, 1000 shots, warm-start caching |
| `HybridTimingConfig` | Re-optimize every 10 s (tuned on training seeds 1–5), base green 15 s, k=0.5 extension per queued vehicle, min 10s, max 45s |
| `EmergencyConfig` | ETA preemption threshold 45 s, ambulance speed x1.5, max preemption 90 s |
| `MetricsConfig` | Derived estimates: typical idle fuel 0.8 L/hr, CO2 2.31 kg/L petrol |
| `SecurityConfig` | HS256 JWT, 600 s token validity, 5 requests/60 s rate limit |

---

### network.py

**Role:** Builds and manages the directed road graph.

**Class:** `RoadNetwork`

- Creates a `networkx.DiGraph` with 6 nodes (intersections A-F)
- Maps each node to a real Chennai junction with GPS coordinates:
  - A: Guindy Kathipara | B: Saidapet Metro | C: Nandanam Signal
  - D: T. Nagar Panagal Park | E: Anna Salai DMS | F: Thousand Lights
- Adds bidirectional directed edges between all adjacent grid pairs (E-W and N-S)
- Each edge carries: `direction`, `target_approach`, `length_m` (150 m), `capacity` (20), `status`, `free_flow_travel_time` (12 ticks)
- `set_edge_status(u, v, status)` — halves capacity on `reduced`, zeros it on `closed`
- `get_boundary_approaches()` — returns all 10 perimeter gate (node, approach) pairs

Grid layout:
```
  W1->[A]<->[B]<->[C]<-E1
       |         |
  W2->[D]<->[E]<->[F]<-E2
  N1  N2  N3   (North entry)
  S1  S2  S3   (South entry)
```

---

### simulator.py

**Role:** Tick-based discrete-event traffic simulation engine.

**Data structures:**
- `queues[node_id][approach]` — list of `Vehicle` objects waiting at each junction approach (N/S/E/W)
- `in_transit[(u,v)]` — list of vehicles currently traveling between junctions
- `signal_phases[node_id]` — current green phase: 0=NS green, 1=EW green
- `completed_vehicles` — vehicles that have exited the network

**Key methods:**

| Method | What it does |
|---|---|
| `step()` | 1 tick: generate arrivals -> discharge queues -> advance in-transit |
| `spawn_vehicle(node, approach)` | Creates a vehicle in the specified approach queue |
| `spawn_at_entry_portal(portal_id, count)` | Spawns N vehicles at a named gate (N1-N3, S1-S3, W1-W2, E1-E2) |
| `inject_by_entry_name(name, count)` | Convenience alias for `spawn_at_entry_portal` |
| `clear_all_vehicles()` | Wipes all queues and in-transit lists without resetting signals or tick |
| `set_signal_phases(phases)` | Updates all intersection signal phases from controller output |
| `reset()` | Full state reset to tick 0 with clean queues |

**Simulation loop internals:**
1. `_generate_boundary_arrivals()` — 35% chance per boundary gate each tick (skipped in manual mode)
2. `_discharge_queues()` — every 2 ticks, for each green approach, move 1 vehicle to in_transit buffer
3. `_advance_in_transit()` — decrement travel ticks; when 0, move to next junction's queue or mark completed

---

### video_canvas.py

**Role:** Generates the self-contained HTML/CSS/JavaScript animated traffic canvas (1100x560 px).

**Function:** `generate_video_canvas_html(network, simulator, emergency_mgr, ...)`

**What it renders:**
- Dark `#0b0f19` background with neon-styled roads connecting junction nodes labeled A-F
- Traffic signals on the LEFT side of each junction as 3-lens vertical heads (red/amber/green) with animated glow
- Vehicles as colored dots flowing along Bezier curves between junctions, queuing at red signals, exiting the perimeter
- Ambulance rendered separately with flashing siren and highlighted green-corridor path
- Accidents shown as red X markers on blocked road segments
- HUD overlay: tick counter, vehicle count, active controller name

**How JS animation works:**
1. Python serialises entire sim state to `state_json` (nodes, edges, phases, vehicles, ambulance, autoFlow)
2. HTML blob injected into Streamlit `components.html()` iframe
3. Inside iframe, `requestAnimationFrame` drives animation at ~60 fps
4. `flowVehicles[]` holds all cars, each with: `x, y, heading, progress, edgeKey, gateId, isExiting, isGate`
5. Each frame: move vehicles along Bezier path, check signal, queue at red, route through junction, bias towards exits
6. If `autoFlow=true`, new vehicles auto-spawn at random gates every 90 frames
7. If `autoFlow=false` (manual mode), no auto-spawning; only Python-injected vehicles appear

**Bezier routing system:**
- `getInflowCurve(gateId)` — entry path from perimeter gate to junction stopline
- `getJunctionCurve(from, to)` — curved path through junction (supports left/right turns)
- `getOutflowCurve(nodeId, direction)` — exit path towards perimeter (70% exit bias to prevent center clustering)

---

### vision.py — YOLOv8 + Classical CV

**Role:** Detects and counts vehicles in uploaded images or videos.

**Primary engine: YOLOv8n (ultralytics)**
- Pre-trained on COCO, zero additional training needed
- Weights: `yolov8n.pt` (6.2 MB), auto-cached in `~/.cache/ultralytics/`
- COCO vehicle classes: `2=car`, `3=motorcycle`, `5=bus`, `7=truck`
- Confidence threshold: 0.30 | NMS IoU: 0.45
- Colour-coded boxes: Yellow=Car, Cyan=Motorcycle, Blue=Bus, Green=Truck

**Fallback engine: Classical CV (11 stages)**
Resize -> Denoise -> CLAHE -> Road surface mask -> Canny -> Fuse with mask -> Morph close ->
Dilate -> Stripe-killer -> Contour filter (solidity/AR/size) -> NMS

**Class `VehicleDetector`:**
- `decode_media_bytes(bytes, filename)` — decodes image or video (samples frame at 25% position)
- `detect_vehicles(img_bgr)` -> returns `(annotated_rgb, count, detections_list)`
- HUD shows engine tag: `[YOLOv8n]` or `[Classical CV]`

**`map_detected_count_to_entries(n, target, available)`:**
Distributes N detected vehicles across entry gates — all to one gate or round-robin.

---

### emergency.py

**Role:** Ambulance mission management and dynamic signal preemption.

**`AmbulanceMission` dataclass:**
`origin`, `destination`, `path` (node ID list), `driver_name`, `current_index`, `current_edge_progress_sec`, `completed`

`get_current_coordinates(network)` — interpolates real-time GPS position along route

**`EmergencyCorridorManager` methods:**

| Method | What it does |
|---|---|
| `dispatch(origin, destination, driver_name)` | Dijkstra to find shortest path, creates AmbulanceMission |
| `advance_mission(simulator)` | Moves ambulance progress along current edge each tick |
| `get_emergency_biases(simulator)` | Returns `{node_id: 'NS'/'EW'}` for nodes where ambulance ETA < 45 s |
| `restore_normal_signals(simulator, phases)` | Resets preempted signals once ambulance clears |

Ambulance destination is always the correct hospital junction, not a random node.

---

### hospital_maps.py

**Role:** Standalone Tactical EMS Paramedic Cockpit (`/?page=hospital_maps`), accessible via the new-tab button in Tab 2.

**Responsibilities:**
- Renders a full-page, self-contained ambulance in-cabin navigation interface
- **Real Google Maps Roadmap & Satellite**: Leaflet integration with Google Maps tiles (`https://mt1.google.com/vt/lyrs=m...`) and hybrid satellite layer
- **Real Address Search**: Search any Chennai location with OpenStreetMap Nominatim or click quick landmark chips (Marina Beach, T. Nagar, Central Station, Guindy Kathipara, Airport)
- **HTML5 GPS Geolocation**: "Use My GPS Location" button captures live physical coordinates via `navigator.geolocation`
- **Interactive Map Pinning**: Click anywhere directly on the Google Map to place or reposition ambulance pickup or hospital destination pins
- **Chennai Trauma Hospital Selector**: Dropdown covering Apollo Hospitals Greams Road, Rajiv Gandhi Govt General Hospital, Omandurar Multi Super Speciality, Kilpauk Medical College, MIOT International, Fortis Malar, Kauvery, or custom search
- **Real Road Network Driving Paths**: Queries OSRM driving engine (`https://router.project-osrm.org/route/v1/driving/...`) for exact street turning geometry, distance (km), and driving time
- **In-Transit Navigation Simulation**: "Start Emergency Journey" animates the ambulance along the real road polyline with dynamic speedometer (55–68 km/h), transit progress percentage, and turn-by-turn guidance

---

### events.py

**Role:** Real-time dynamic traffic disruption engine.

**Event types:**
- `EMERGENCY` — triggers ambulance dispatch
- `ROAD_CLOSURE` — sets edge capacity to 0
- `ACCIDENT` — halves edge capacity for a duration, auto-restores
- `CONGESTION_SURGE` — injects burst of vehicles at a boundary gate (3x rate)

**`EventsEngine` methods:**
- `trigger_event(event)` — activates event immediately
- `tick(simulator)` — manages event lifecycle (auto-resolve after duration)
- `resolve_event(event_id)` — restores road to normal, logs resolution

---

### metrics.py

**Role:** Computes performance and environmental metrics.

**`MetricsEngine.compute_run_metrics(simulator)` returns:**

| Metric | Unit | Description |
|---|---|---|
| `avg_wait_sec` | seconds | Mean vehicle waiting time |
| `max_wait_sec` | seconds | Worst-case waiting time |
| `throughput_per_min` | veh/min | Completed vehicles per minute |
| `avg_queue_len` | vehicles | Average junction queue depth |
| `idle_fuel_l` | litres | Estimated fuel wasted idling |
| `co2_kg` | kg | CO2 from idle fuel x 2.31 kg/L |
| `improvement_vs_fixed_pct` | % | Throughput gain vs fixed-timing baseline |

---

### security.py

**Role:** Protects emergency preemption from spoofed signals or DOS attacks.

| Feature | Detail |
|---|---|
| JWT authentication | HS256 tokens, 600 s validity |
| Rate limiting | Sliding window: max 5 requests per 60 s per client |
| Preemption cap | Hard limit of 90 s |
| Audit logging | Append-only JSONL with SHA-256 hash chain |
| Input validation | Validates all event payload fields |

---

### signal_interface.py

**Role:** Hardware-ready abstraction layer and physical safety monitors (Phase G).

**Components:**
- `SignalControllerInterface`: Vendor-agnostic abstract base class for traffic signal actuators (`set_phase`, `get_state`, `emergency_preempt`, `safe_fallback`). Enables NTCIP 1202 / NEMA TS2 integration without touching the optimization core.
- `SoftwareConflictMonitor`: Enforces mutually exclusive green phases (prevents concurrent N-S and E-W green lights) and a **10-second minimum green constraint**. (Note: yellow/all-red clearance logic is defined here as a hardware-layer specification for physical cabinet interfaces; it is not exercised by the discrete tick simulator, which uses binary green/red phases).
- `HardwareWatchdog`: Heartbeat monitor tripping `safe_fallback()` into a fail-safe fixed-timing cycle if an optimization step times out (>15s).

---

### canvas.py

**Role:** Builds the static Plotly diagnostic canvas (Tab 2).

**Function:** `build_simulation_canvas(network, simulator, emergency_mgr, ...)`

Renders:
- Road segments as lines (green=open, red=closed, orange=accident)
- Junction nodes sized by queue length, labelled with name + live counts
- Signal state per node (green/red circle)
- Ambulance marker + hover tooltips
- Click-to-select junctions and roads for interactive event targeting

---

### controllers/

**`base.py` — `BaseController`**
Abstract interface. All controllers implement `compute_phases(simulator) -> Dict[int, int]`.

**`hybrid.py` — `HybridController`**
Primary quantum-classical controller. Re-optimizes every `reopt_interval_sec` (default 10s):
1. Builds QUBO matrix Q from live queue state, coordination couplings, and switching penalties
2. QAOA or brute-force solver -> optimal bitstring x*
3. Converts to phase map: x_i=0 -> NS green, x_i=1 -> EW green
4. Phase persistence: A phase persists at each intersection while the optimizer continues selecting it, re-evaluated every `reopt_interval_sec` (no dead clamp timers).

**`rule_based.py` — `RuleBasedController`**
Greedy: every 10 ticks, compares NS vs EW queue totals per junction, assigns green to heavier queue.

**`fixed.py` — `FixedTimingController`**
Baseline: alternates NS/EW green every 30 s on a fixed 60-second cycle.

---

### quantum/

**`qubo.py` — `TrafficQUBOBuilder`**
Builds the 6x6 QUBO matrix Q:
1. **Queue penalty** `w_queue=1.0`: diagonal term for heavier approach
2. **Coordination bonus** `w_coord=0.2`: off-diagonal coupling for green-wave neighbors
3. **Spillback penalty** `w_spillback=0.5`: penalizes greening when downstream is near-full (>=80%)
4. **Emergency bias** `w_emergency=50.0`: forces green at ambulance path intersections
5. **Switching penalty** `w_switch=2.5`: penalizes changing current phase to prevent signal flicker
6. **Pedestrian urgency** `w_pedestrian=2.0`: prioritizes crosswalk waiting queues

**`qaoa.py` — `QAOATrafficSolver`**
Manual PennyLane QAOA (no black-box operators):
1. Hadamard on all qubits -> uniform superposition
2. Cost layer (p=2): RZ for diagonal, CNOT-RZ-CNOT for off-diagonal
3. Mixer layer (p=2): RX on all qubits
4. COBYLA minimizes expected cost over 35 iterations
5. Top-4 most probable bitstrings evaluated; minimum-cost returned
6. Warm-start: optimal (gamma*, beta*) cached between rounds

**`ising.py` — `QUBOToIsingConverter`**
Converts QUBO `x^T Q x` to Ising `h_i sigma_i + J_ij sigma_i sigma_j` via `x_i = (1-sigma_i)/2`.

**`brute_force.py` — `BruteForceOptimizer`**
Exact: enumerates all 2^6=64 binary vectors, returns minimum QUBO cost assignment.

---

## Dashboard Pages & Visual Interface

The user interface is engineered with a high-contrast dark aesthetic, responsive glassmorphism, and distinct color-coded button navigation.

### Top Navigation & Telemetry Strips
- **Cleared Header**: Lowered main container (`padding-top: 4.2rem`) prevents collision with the Streamlit top navbar.
- **Emerald Title**: Styled with a vibrant mint/emerald linear gradient: `Quantum Traffic Brain`.
- **6 Emerald Metric Strips**: Dark-emerald cards (`#05261d` to `#0b3d2f`) with glowing mint metrics:
  - **Elapsed Time**: Simulation ticks elapsed.
  - **Avg Wait Time**: Mean waiting time per vehicle in seconds.
  - **Throughput (cpm)**: Completed vehicles per minute.
  - **Active Queue Depth**: Average queue accumulation across all approaches.
  - **Est. Idle Fuel (L\*)**: Estimated fuel consumption during stop-and-go idling (0.8 L/hr rate).
  - **Est. CO2 Emitted (kg\*)**: Estimated emissions based on fuel consumed (2.31 kg CO2/L).

---

### Navigation: 6 Full-Width Colored Button Tabs

The dashboard navigation uses full-width interactive button pills with clean gaps and alternating vibrant colors:

#### Tab 1: Traffic Orchestration Grid (Emerald Green)
- **Animated 2D Video Canvas (HTML/CSS/JS)**: Self-contained interactive 1100x560 px canvas running at 60 fps. Renders Bezier road curves connecting junctions A through F, dual-phase signal heads with realistic bloom glow, animated vehicle dots, emergency pods with flashing beacons, and blocked road hazard markers.
- **Diagnostic Canvas (Plotly)**: Interactive graph view supporting click-to-track vehicle inspection and link hazard toggling.
- **Perimeter Gate Queues & CCTV Media Detection**:
  - Left column: Direct vehicle injection inputs across all 10 boundary entry gates (N1–N3, S1–S3, W1–W2, E1–E2).
  - Right column: CCTV / Drone feed upload (JPG, PNG, WEBP, MP4) with instant preview and AI vehicle detection (YOLOv8n or 11-stage Classical CV fallback).
- **Intersection Queue Breakdown**: Live tabular breakdown of vehicular queues on N, S, E, W approaches per junction.
- **Dynamic Disruptions**: One-click simulation of traffic incidents and capacity restrictions.

#### Tab 2: Emergency Navigation Cockpit (Sapphire Medical Blue)
- **Tactical Paramedic HUD Header**: High-contrast command banner displaying CAD authority status (`108 EMS | QUANTUM CORRIDOR ACTIVE`).
- **`🏥 View Real Dashboard (Hospital Google Maps) ↗` Button**: Launches the dedicated full-page paramedic ambulance console in a **new browser tab** (`/?page=hospital_maps`).
- **Operator Authentication & Dispatch (Permanent on Main Page)**:
  - Driver Unit Call-Sign input (`Ambulance Unit 108`).
  - Starting Location selector (10 boundary gates N1–N3, S1–S3, W1–W2, E1–E2).
  - Destination Junction selector (Junctions A through F).
  - Preemption Mode: Soft QUBO Corridor bias ($W_{emerg}=15$) vs. Hard Override (forced green).
  - Priority Level: Priority 2 (Code Red / Cardiac) vs. Priority 1 (Code Yellow / Urgent).
  - Dispatch Controls: Single unit dispatch, Random auto-dispatch, and Multi-ambulance conflict resolution test dispatch.
  - Security Attack Simulator: Test harness for forged token attacks, expired token rejections, rate-limit burst blocks, and SHA-256 cryptographic audit chain verification.
  - Live Telemetry Canvas & Preemption Impact Monitor: Reports delay avoided (~9.7s to 13.4s) and downstream queue flushing.

#### Tab 3: Quantum QAOA Core (Electric Violet)
- **QUBO Matrix Heatmap**: Visualizes the $6 \times 6$ quadratic coupling and penalty matrix $Q$, illustrating coordination bonuses and spillback penalties.
- **QAOA State Probability Distribution**: Bar chart displaying the top 16 basis state probabilities measured from the PennyLane parameterized quantum circuit.
- **Circuit Telemetry**: Live readout of the QAOA approximation ratio, exact optimum hit status, and optimal phase bitstring.

#### Tab 4: Performance Benchmarks (Warm Amber)
- **On-Demand Benchmark Runner**: Executes synchronized multi-seed comparisons across all 4 controllers (Fixed-Timing Baseline, Greedy Rule-Based, Hybrid Brute-Force, and Hybrid QAOA).
- **Real-Time Performance Table**: Reports comparative throughput, average wait times, idle fuel savings, and baseline improvement percentages.

#### Tab 5: Evidence (Deep Teal)
- **20-Seed Independent Evaluation Benchmark**: Comprehensive multi-seed table evaluated across seeds 100–119 with 95% confidence intervals.
- **Preemption Pareto Trade-Off Study**: Empirical trade-off curve between ambulance time saved and civilian collateral delay across emergency bias weights $W_{emerg} \in [5, 150]$ vs Hard Override (`results/preemption_tradeoff.png`).
- **QAOA Algorithmic Depth ($p=1$ to $4$)**: Empirical approximation ratios across circuit depths (`results/qaoa_depth_vs_ratio.png`).
- **NISQ Depolarizing Noise Study**: Density matrix simulation of gate noise sensitivity (`results/qaoa_noise_study.png`).
- **Classical Brute-Force Combinatorial Scaling**: Measured $O(2^N)$ wall-clock runtime explosion from $N=4$ to $N=24$ (`results/scaling_curve.png`).

#### Tab 6: Security & Audit Log (Crimson / Ruby)
- **Emergency Green Corridor Cryptographic Governance**: Administrative management of CAD authentication tokens and access policies.
- **Append-Only SHA-256 Audit Log**: Interactive cryptographic ledger detailing every preemption request, granted corridor, and blocked attack.

---

### Standalone Page: Tactical EMS Paramedic Google Maps Console (`/?page=hospital_maps`)

Accessible via the **"🏥 View Real Dashboard (Hospital Google Maps) ↗"** button in Tab 2, this dedicated full-page interface provides genuine real-world navigation for ambulance operators:

```
+-----------------------------------------------------------------------------------+
| 🚑 CHENNAI EMS 108 — TACTICAL DISPATCH HUD       [⬅️ Switch Back to Traffic Brain] |
+---------------------------------------------------+-------------------------------+
|  1. Starting Location (From)                      |  REAL GOOGLE MAPS DISPLAY     |
|  [ Search Chennai address / landmark...         ] |                               |
|  [📍 Use My GPS Location]  [🗺️ Pick on Map]       |  - Roadmap / Satellite layers |
|  Quick: [Marina Beach] [T. Nagar] [Central] [Air] |  - Real road driving polyline |
|                                                   |  - Pulsing ambulance marker   |
|  2. Receiving Hospital (To)                       |  - Hospital trauma bay marker |
|  [ Apollo Hospitals (Greams Road)               v]|                               |
|  - Rajiv Gandhi Govt General Hospital             |  FLOATING HUD OVERLAY:        |
|  - TN Multi Super Speciality (Omandurar)          |  Speed: 58 km/h               |
|  - Kilpauk Medical College Hospital               |  Guidance: Follow Anna Salai  |
|  - MIOT International / Fortis Malar / Kauvery    |  Progress: 34%                |
|                                                   |                               |
|  3. Route Telemetry                               |                               |
|  Distance: 7.8 km  |  Est. Time: 11 mins          |                               |
|                                                   |                               |
|  [ 🚀 START EMERGENCY JOURNEY ]                   |                               |
+---------------------------------------------------+-------------------------------+
```

**Key Features:**
- **No Schematic Grid Jargon**: Completely replaces node IDs (`ja, jb, jc`) with genuine Chennai addresses, landmarks, and trauma hospitals.
- **Real Address Search**: Search any street or landmark powered by OpenStreetMap Nominatim, or choose quick preset chips (Marina Beach, T. Nagar Panagal Park, Central Railway Station, Guindy Kathipara, Chennai Airport).
- **HTML5 GPS Geolocation**: The **"Use My GPS Location"** button queries the browser's `navigator.geolocation` API to instantly pin the ambulance at your live physical coordinates.
- **Map-Click Pin Placement**: Click anywhere directly on the Google Map to drop or reposition pickup and hospital destinations.
- **OSRM Real Road Network Driving Paths**: Queries the Open Source Routing Machine (`router.project-osrm.org`) to compute the exact driving path along actual streets, calculating real road distance (km) and driving time.
- **Interactive Journey Simulation**: Clicking **"Start Emergency Journey"** smoothly animates the ambulance along the real road polyline with dynamic speed updates (55–68 km/h), arrival countdown, and turn-by-turn guidance.
- **Seamless Multitasking**: Operates in its own browser tab without disturbing the simulation state on the main dashboard.

---

## End-to-End System Flow

```
1. App starts -> st.session_state initialised
2. User clicks Auto-Simulate (N=15 steps)
   for each step:
     a. controller.compute_phases(sim)
        |- Build QUBO matrix Q from live queue state
        |- Run QAOA or brute-force -> bitstring x*
        +- Compute adaptive green durations
     b. sim.set_signal_phases(phases)
     c. sim.step()
        |- _generate_boundary_arrivals()  [if autoFlow]
        |- _discharge_queues()            [signal-gated]
        +- _advance_in_transit()
     d. emergency_mgr.advance_mission(sim)
     e. events_engine.tick(sim)
     f. st.rerun() -> canvas re-renders
3. Canvas HTML regenerated each rerun
   |- initial_vehicles from sim.queues + sim.in_transit
   |- signal_phases -> signal head colours
   |- ambulance path -> blue dot + green corridor
   +- accidents -> red X markers
```

---

## Quantum Optimization Pipeline

```
Traffic State (queue counts per approach)
         |
TrafficQUBOBuilder.build_qubo()
  |- Diagonal Q[i,i]: queue imbalance penalty
  |- Off-diagonal Q[i,j]: neighbor coordination bonus
  |- Spillback check: downstream saturation penalty
  +- Emergency bias: +50 weight for ambulance path nodes
         |
       Q matrix (6x6 float64)
         |
  QAOA mode:
    QUBOToIsingConverter -> h_i, J_ij
    PennyLane circuit (p=2 layers):
      |-- Hadamard init
      |-- Cost layer: RZ (diagonal), CNOT-RZ-CNOT (coupling)
      +-- Mixer layer: RX on all qubits
    COBYLA optimizer (35 iterations)
    -> optimal bitstring x* (6 bits)

  Brute-force mode:
    Enumerate all 64 binary vectors
    -> minimum cost bitstring x*
         |
  Phase map: {node_id: 0 or 1}  (NS/EW green)
         |
  Phase persistence:
  Phase held while optimizer re-selects it; re-evaluated every reopt_interval_sec
         |
  sim.set_signal_phases(phases)
```

---

## Emergency Corridor System

```
1. User clicks "Dispatch Ambulance"
   -> EmergencyCorridorManager.dispatch(origin, destination)
   -> Dijkstra weighted by (travel_time + queue_delay)
   -> Creates AmbulanceMission with path [A, B, C, F]

2. Each tick: emergency_mgr.advance_mission(sim)
   -> increments current_edge_progress_sec
   -> when progress >= edge_travel_time: advance to next node
   -> completed = True at final destination (hospital node)

3. HybridController.compute_phases() uses emergency_biases:
   -> For nodes where ambulance ETA < 45 s:
      force green in ambulance approach direction (weight=50)
   -> This dominates QUBO -> signal opens for ambulance

4. Canvas shows:
   -> Blue dot moving along route
   -> Green highlighted corridor edges
   -> Normal vehicles queue and wait at preempted signals

5. On completion: ambulance fades, normal optimization resumes
```

---

## Vehicle Detection Pipeline

```
User uploads file (JPG/PNG/WEBP/MP4)
         |
VehicleDetector.decode_media_bytes()
  |- Image: cv2.imdecode
  +- Video: cv2.VideoCapture -> sample at 25% position
         |
_get_yolo() -> load YOLOv8n from ~/.cache/ultralytics/
         |
If YOLO available:
  model.predict(img, conf=0.30, classes=[2,3,5,7])
  -> boxes, confidences, class IDs
  -> filter vehicle classes only

If YOLO unavailable (fallback):
  Classical 11-stage CV pipeline
  -> denoise -> CLAHE -> road mask -> Canny -> fuse
  -> morph-close -> dilate -> stripe-kill -> contour filter -> NMS

_annotate(img, detections, engine_name)
  -> colored reticle boxes per class (car=yellow, bus=blue...)
  -> HUD with engine tag + count

-> return (annotated_rgb, count, detections_list)
         |
map_detected_count_to_entries(count, gate)
         |
sim.inject_by_entry_name(gate, count)
-> vehicles appear on canvas at next rerun
```

---

## Configuration Parameters

All tunables reside in `traffic_quantum/config.py`:

| Parameter | Value | Effect |
|---|---|---|
| `grid_rows / grid_cols` | 2 / 3 | 6-junction urban topology (matches Chennai pilot corridor) |
| `base_arrival_rate` | 0.35 | Poisson probability of vehicle arrival per gate tick (~21 cars/min per gate) |
| `discharge_interval_ticks` | 2 | Ticks required to discharge leading vehicle through green signal (0.5 car/s) |
| `default_capacity` | 20 | Maximum vehicle holding capacity per directed road segment |
| `w_queue` | 1.0 | QUBO linear weight on active queue depth imbalance |
| `w_coord` | 0.2 | QUBO quadratic coupling weight for arterial green-wave coordination (tuned on training seeds 1–5) |
| `w_spillback` | 0.5 | QUBO penalty for discharging into saturated downstream roads (tuned on training seeds 1–5) |
| `w_emergency` | 50.0 | QUBO emergency corridor bias in config.py (swept across 5–150 in preemption study) |
| `w_pedestrian` | 2.0 | QUBO linear penalty for pedestrian crosswalk waiting queues |
| `pedestrian_arrival_rate` | 0.05 | Poisson arrival rate for crosswalk pedestrians per junction |
| `pedestrian_max_wait_sec` | 45 | Urgency threshold after which pedestrian phase is forced |
| `min_green_sec` | 10 | Minimum green duration enforced by Conflict Monitor |
| `reopt_interval_sec` | 10 | Re-optimization interval (10s) between successive QUBO evaluations (tuned on training seeds 1–5) |
| `w_switch` | 1.0 | QUBO switching penalty (chosen on training seeds 1–5; differences between settings on those seeds were small (<1s)) |
| `p_layers` | 2 | QAOA circuit depth |
| `max_iterations` | 35 | Classical optimizer evaluation steps (35 in config.py) |
| `shots` | 1000 | Number of measurement samples per QAOA evaluation |
| `eta_threshold_sec` | 45.0 | Preemption anticipation horizon for incoming ambulances |
| `rate_limit` | 5 / 60s | Token-bucket preemption rate limit (5 requests per 60 seconds) |
| `road_length_m` | 150.0 | Directed link length between adjacent intersections |
| `YOLO_CONF` | 0.30 | Minimum confidence threshold for vehicle bounding boxes |

---

## Defensible Multi-Regime Scenario Suite (Evaluation Seeds 100–119, 600s Each)

To assess controller performance across realistic urban conditions, the system was evaluated across four distinct traffic regimes on **20 independent evaluation seeds (seeds 100–119, 600 simulated seconds each)**. 
All hyperparameter tuning was conducted strictly on separate **training seeds (seeds 1–5)** to prevent overfitting.

### Network Saturation & Traffic Demand Analysis

Before comparing controllers, traffic regimes must be classified by network saturation (offered demand vs network discharge capacity):

| Regime | Boundary Arrival Profile | Total Offered Demand | Measured Throughput | Avg Network Queue | Saturation Status |
|---|---|---|---|---|---|
| **Moderate Load** | 0.18 cars/s per gate (all 10 gates) | **108.0 cars/min** | **99.2 – 101.1 cars/min** | **31.5 – 48.6 cars** | **Unsaturated (~75–80% capacity)**: Queues remain stable and bounded; differences reflect pure signal timing efficiency. |
| **Balanced Flow** | 0.35 cars/s per gate (all 10 gates) | **210.0 cars/min** | **128.5 – 138.4 cars/min** | **364.4 – 397.7 cars** | **Oversaturated**: Inflow exceeds maximum network exit capacity (~138 cpm); queues accumulate over time across all controllers. |
| **Rush-Hour** | 0.45 E-W, 0.15 N-S | **162.0 cars/min** | **105.2 – 117.9 cars/min** | **219.7 – 295.3 cars** | **Oversaturated (Directional)**: High arterial flow backs up East-West approaches. |
| **Surge + Incident** | 0.45 E-W, 0.20 N-S + lane reduction | **180.0 cars/min** | **116.0 – 120.9 cars/min** | **301.6 – 317.3 cars** | **Oversaturated (Bottlenecked)**: Edge (3, 4) capacity halved between t=60s and t=300s. |

### Scenario Suite Empirical Results (320 Simulation Runs across 20 Seeds)

All metrics below are drawn directly from `results/scenario_benchmark.csv` (600s trials, evaluation seeds 100–119):

| Scenario | Controller | Avg Wait (s) | 95% Confidence Interval | Avg Ped Wait (s) | Throughput (cpm) | Avg Queue (cars) | Phase Switches | Ambulance Time (s) | Exact Hit % |
|---|---|---|---|---|---|---|---|---|---|
| **Moderate Load** | Fixed-Timing Baseline | 27.49 ± 0.76 | [27.16, 27.82] | 7.65 ± 0.74 | 99.2 ± 1.5 | 48.6 ± 1.8 | 114.0 ± 0.0 | 19.9 ± 12.2 | N/A |
| (75–80% Saturation) | Rule-Based (Longest Queue) | 17.70 ± 0.55 | [17.45, 17.94] | 3.31 ± 0.33 | 101.1 ± 1.7 | 31.5 ± 1.3 | 324.4 ± 10.9 | 24.6 ± 13.7 | N/A |
| | **Hybrid (Brute-Force)** | **18.11 ± 0.48** | [17.90, 18.31] | **2.91 ± 0.25** | **100.9 ± 1.7** | **32.2 ± 1.2** | **327.9 ± 9.8** | **9.2 ± 2.2** | N/A |
| | **Hybrid (QAOA)** | **19.86 ± 1.07** | [19.39, 20.33] | **3.26 ± 0.47** | **101.1 ± 1.9** | **35.3 ± 2.3** | **291.9 ± 19.9** | **8.2 ± 1.1** | **59.8%** |
| **Rush-Hour** | Fixed-Timing Baseline | 105.20 ± 3.15 | [103.82, 106.58] | 7.65 ± 0.74 | 105.2 ± 1.8 | 295.3 ± 11.5 | 114.0 ± 0.0 | 25.1 ± 15.7 | N/A |
| (3x Arterial Demand) | Rule-Based (Longest Queue) | 80.47 ± 5.53 | [78.05, 82.89] | 8.75 ± 1.45 | 117.9 ± 1.5 | 219.7 ± 18.0 | 154.6 ± 6.8 | 29.1 ± 13.6 | N/A |
| | **Hybrid (Brute-Force)** | **81.91 ± 4.64** | [79.88, 83.94] | **6.99 ± 1.16** | **117.5 ± 1.7** | **223.3 ± 15.6** | **156.4 ± 7.1** | **9.2 ± 2.2** | N/A |
| | **Hybrid (QAOA)** | **87.57 ± 4.88** | [85.44, 89.71] | **7.43 ± 0.92** | **115.1 ± 1.9** | **238.9 ± 16.0** | **155.6 ± 8.7** | **8.5 ± 1.5** | **36.4%** |
| **Balanced Flow** | **Fixed-Timing Baseline** | **102.45 ± 4.37** | [100.54, 104.37] | 7.65 ± 0.74 | 138.4 ± 0.6 | 364.4 ± 19.7 | **114.0 ± 0.0** | 15.3 ± 3.4 | N/A |
| (Uniform Demand) | Rule-Based (Longest Queue) | 105.98 ± 5.93 | [103.38, 108.57] | 4.29 ± 0.65 | 131.0 ± 5.2 | 375.1 ± 23.8 | 274.1 ± 13.5 | 21.7 ± 3.8 | N/A |
| | Hybrid (Brute-Force) | 107.80 ± 5.31 | [105.47, 110.13] | 3.52 ± 0.42 | 131.0 ± 4.5 | 381.5 ± 22.0 | 279.4 ± 11.0 | 11.0 ± 2.4 | N/A |
| | Hybrid (QAOA) | 112.51 ± 5.66 | [110.02, 114.99] | 4.35 ± 0.67 | 128.5 ± 4.7 | 397.7 ± 23.2 | 235.2 ± 11.7 | 9.0 ± 2.0 | 32.6% |
| **Surge + Incident** | **Fixed-Timing Baseline** | **98.69 ± 2.82** | [97.45, 99.93] | 7.65 ± 0.74 | 120.9 ± 2.0 | 307.7 ± 11.5 | **114.0 ± 0.0** | 19.4 ± 12.2 | N/A |
| (Lane Closure) | Rule-Based (Longest Queue) | 99.45 ± 5.71 | [96.95, 101.96] | 7.77 ± 1.76 | 117.5 ± 2.5 | 301.6 ± 20.3 | 184.8 ± 10.0 | 26.1 ± 9.8 | N/A |
| | **Hybrid (Brute-Force)** | **99.37 ± 5.31** | [97.04, 101.70] | **5.77 ± 0.73** | 118.3 ± 2.2 | 301.6 ± 19.5 | 191.3 ± 9.0 | 10.2 ± 2.5 | N/A |
| | Hybrid (QAOA) | 104.55 ± 5.79 | [102.01, 107.09] | 6.77 ± 0.95 | 116.0 ± 2.5 | 317.3 ± 21.0 | 177.8 ± 11.0 | 9.0 ± 2.0 | 33.6% |

\* *Environmental Metrics Note: Fuel consumption (0.8 L/hr idle rate) and CO₂ emissions (2.31 kg CO₂/L petrol) are calculated directly as scalar multiples of idle wait time based on typical automotive assumptions (not "EPA standard"). They move in lockstep with wait time and do not represent independent empirical sensors.*

### Paired-Seed Delay Differences & Statistical Significance (n=20 seeds)

Evaluating differences paired per evaluation seed eliminates cross-seed traffic variance:

| Regime | Hybrid (BF) vs Fixed | Hybrid (BF) vs Rule-Based | Hybrid (QAOA) vs Fixed | Hybrid (QAOA) vs Rule-Based | QAOA vs Brute-Force |
|---|---|---|---|---|---|
| **Moderate Load** | **-9.39 ± 0.41s** `[-9.79, -8.98]` (Significant) | **+0.41 ± 0.29s** `[+0.12, +0.69]` (Close) | **-7.63 ± 0.51s** `[-8.14, -7.12]` (Significant) | **+2.16 ± 0.56s** `[+1.60, +2.73]` (Rule leads) | **+1.75 ± 0.47s** `[+1.28, +2.23]` (Approximation gap) |
| **Rush-Hour** | **-23.29 ± 1.63s** `[-24.92, -21.65]` (Significant) | **+1.44 ± 1.41s** `[+0.03, +2.85]` (Close) | **-17.62 ± 1.89s** `[-19.51, -15.73]` (Significant) | **+7.10 ± 1.84s** `[+5.26, +8.95]` (Rule leads) | **+5.66 ± 1.34s** `[+4.33, +7.00]` (Approximation gap) |
| **Balanced Flow** | **+5.35 ± 1.50s** `[+3.84, +6.85]` (Fixed wins) | **+1.82 ± 0.71s** `[+1.11, +2.53]` (Rule leads) | **+10.05 ± 1.76s** `[+8.30, +11.81]` (Fixed wins) | **+6.53 ± 1.02s** `[+5.51, +7.55]` (Rule leads) | **+4.71 ± 0.93s** `[+3.78, +5.64]` (Approximation gap) |
| **Surge + Incident** | **+0.68 ± 1.76s** `[-1.07, +2.44]` (**TIE**: CI includes 0) | **-0.08 ± 0.82s** `[-0.91, +0.74]` (**TIE**: CI includes 0) | **+5.86 ± 2.14s** `[+3.73, +8.00]` (Fixed leads) | **+5.10 ± 1.38s** `[+3.72, +6.48]` (Rule leads) | **+5.18 ± 1.40s** `[+3.79, +6.58]` (Approximation gap) |

### Honest Scientific Findings & Core Conclusions

1. **Where Fixed-Timing Wins or Ties**:
   - Under uniform, balanced demand, cyclical 30s/30s splits are optimal: Fixed-Timing achieves **102.45s delay**, beating Hybrid Brute-Force (107.80s) by **5.35s**. When traffic is balanced across all approaches, adaptive re-optimization incurs small phase transition overhead without traffic asymmetry to exploit.
   - Under severe incident surge, Fixed-Timing (98.69s) and Hybrid Brute-Force (99.37s) are **statistically tied** (paired difference: `+0.68 ± 1.76s`, 95% CI includes zero).

2. **Where Hybrid Beats Fixed Decisively**:
   - In moderate, unsaturated traffic, Hybrid Brute-Force cuts average wait time by **9.43s (34.3% reduction)** compared to Fixed-Timing (`[-9.78, -9.07]s`, $n=20$ at 0s lost time).
   - In directional rush-hour demand (3x arterial load), Hybrid Brute-Force cuts average wait time by **24.67s (23.5% reduction)** compared to Fixed-Timing (`[-26.97, -22.36]s`, $n=20$ at 0s lost time).

3. **Hybrid vs Rule-Based (The Multi-Objective Picture)**:
   - On raw vehicle delay at 0s lost time, Hybrid Brute-Force (18.06s moderate, 80.53s rush) is virtually tied with default Rule-Based (17.70s moderate, 80.47s rush). When Rule-Based is tuned, it achieves 15.21s moderate and 81.15s rush.
   - When switching lost time is introduced (2s and 3s), **Rule-Based (tuned) beats Hybrid in moderate load**:
     - At 2s lost time: Rule-Based (tuned) is faster by 2.27s (24.32s vs 26.59s, 95% CI `[+1.62, +2.92]s`).
     - At 3s lost time: Rule-Based (tuned) is faster by 1.79s (29.87s vs 31.66s, 95% CI `[+1.06, +2.52]s`).
   - In rush hour:
     - At 2s lost time: Hybrid holds a modest 2.25s advantage (105.55s vs 107.80s, 95% CI `[-2.89, -1.62]s`).
     - At 3s lost time: Hybrid (BF default) is tied with Rule-Based tuned (113.23s vs 114.74s, 95% CI spans zero).
   - **Pedestrian Wait Times**: Hybrid cuts pedestrian delay in moderate load (down to 2.91s vs 7.65s for fixed and 3.31s for rule-based). In rush hour, Hybrid (6.99s) and Fixed (7.65s) are a **statistical tie** (paired diff -0.66s, 95% CI `[-1.45, +0.13]s`, spanning zero).
   - **Emergency Response**: Preemption cuts ambulance response vs un-preempted baselines by 20s to 44s (50.45s down to 27.85s–30.50s in moderate load; 93.70s down to 49.70s–57.20s in rush hour). However, when Fixed and Rule-Based also receive hard preemption, Rule-Based + Hard Preemption achieves 27.85s (moderate) and 54.50s (rush hour), matching or slightly beating Hybrid Soft QUBO (30.50s and 57.20s). **The hybrid's ambulance advantage disappears when baselines also get preemption** (`results/ambulance_fairness.csv`). Route: nodes [0, 1, 2, 5], 3 directed arterial links, 24.0s free-flow travel time.

4. **Phase Switch Counts (Honest Comparison Across Controllers)**:
   - With the current configuration (10s re-optimization interval, $W_{switch}=1.0$), **the Hybrid controller does NOT switch fewer times than classical baselines**.
   - Over 600 seconds across 6 intersections:
     - Fixed-Timing switches **114.0 times** (strict 30s cycles).
     - Hybrid Brute-Force switches **156.4 to 327.9 times** (~2.5x more than Fixed).
     - Rule-Based switches **154.6 to 324.4 times** (virtually identical to Hybrid).
   - Because Hybrid actively reacts to dynamic queue pressures and pedestrian crosswalk thresholds, it switches phases adaptively at a rate comparable to rule-based logic.

5. **QAOA Approximation Accuracy**:
   - Across regimes, QAOA (p=2) achieves mean approximation ratios between $0.9192$ and $0.9476$, finding the exact ground truth optimum in 32.6% to 59.8% of rounds.
   - Because sub-optimal bitstrings are chosen on a portion of rounds, QAOA vehicle delay is slightly higher than Brute-Force (+1.75s to +5.66s gap).
   - All quantum results presented were computed on quantum simulators (PennyLane `default.qubit` / Amazon Braket local simulator); no physical quantum hardware was used unless a verified `results/qpu_run_*.json` file is present.

6. **Ambulance Travel Time: QAOA vs Brute-Force**:
   - In moderate load (`-1.00 ± 1.15s`, CI `[-2.15, +0.15]`) and rush hour (`-0.75 ± 0.80s`, CI `[-1.55, +0.05]`), the paired ambulance time difference between QAOA and Brute-Force **includes zero (statistically tied)**.
   - In balanced flow and surge, the modest ~1-2s difference is discrete simulation queue noise (the presence or absence of a single civilian vehicle in front of the ambulance at dispatch tick 15). Both controllers apply identical $W_{emerg}=50$ biases and activate green corridors; no quantum advantage over brute force is claimed.

---

### Robustness to Switching Cost (Lost-Time Sensitivity & Fair Baseline Tuning)

In real physical deployments, signal transitions incur lost time due to yellow clearance intervals and startup delays. The simulator includes `switch_lost_time_sec` (blocking vehicle discharge for $N$ seconds after a phase change). Evaluated across 20 evaluation seeds (seeds 100–119) for Fixed, Rule-Based (default), Rule-Based (tuned on training seeds 1–5), Hybrid (Brute-Force default), and Hybrid (BF, retuned with identical parity tuning budget):

*Traffic Condition: `ambulance_present: False` (civilian traffic only), `pedestrians_present: True`.*

| Scenario | Lost Time | Controller | Avg Wait (s) | 95% CI | Throughput (cpm) | Phase Switches | Paired Diff vs Fixed (s) | Paired Diff vs Rule (tuned) (s) |
|---|---|---|---|---|---|---|---|---|
| **Moderate Load** | 0s | Fixed-Timing | 27.49 | [27.13, 27.85] | 99.2 | 114.0 | 0.00 | +12.28 `[+11.99, +12.57]` |
| | 0s | Rule-Based (default) | 17.70 | [17.43, 17.96] | 101.1 | 324.4 | -9.79 `[-10.15, -9.44]` | +2.49 `[+2.12, +2.86]` |
| | 0s | Rule-Based (tuned) | 15.21 | [14.89, 15.53] | 101.8 | 340.9 | -12.28 `[-12.57, -11.99]` | 0.00 |
| | 0s | Hybrid (BF, default) | 18.06 | [17.81, 18.32] | 100.9 | 332.4 | -9.43 `[-9.78, -9.07]` | +2.85 `[+2.51, +3.20]` |
| | 0s | **Hybrid (BF, retuned)** | **11.86** | [11.62, 12.10] | **102.3** | 468.2 | **-15.63** `[-15.91, -15.36]` | **-3.35** `[-3.67, -3.03]` |
| | 2s | Fixed-Timing | 32.51 | [31.96, 33.07] | 98.4 | 114.0 | 0.00 | +8.19 `[+7.56, +8.82]` |
| | 2s | Rule-Based (default) | 26.44 | [25.69, 27.19] | 99.5 | 284.4 | -6.07 `[-6.47, -5.67]` | +2.12 `[+1.51, +2.73]` |
| | 2s | **Rule-Based (tuned)** | **24.32** | [23.56, 25.09] | **100.1** | 234.8 | **-8.19** `[-8.82, -7.56]` | 0.00 |
| | 2s | Hybrid (BF, default) | 26.59 | [25.91, 27.28] | 99.5 | 204.8 | -5.92 `[-6.53, -5.32]` | +2.27 `[+1.62, +2.92]` |
| | 2s | Hybrid (BF, retuned) | 26.59 | [25.91, 27.28] | 99.5 | 204.8 | -5.92 `[-6.53, -5.32]` | +2.27 `[+1.62, +2.92]` |
| | 2s | Hybrid (QAOA) [5 seeds] | 29.15 | [27.42, 30.88] | 98.1 | 209.6 | -2.74 `[-4.45, -1.03]` | +4.75 `[+2.81, +6.69]` |
| | 3s | Fixed-Timing | 38.85 | [38.02, 39.67] | 97.1 | 114.0 | 0.00 | +8.98 `[+8.21, +9.75]` |
| | 3s | Rule-Based (default) | 41.71 | [39.78, 43.63] | 95.7 | 213.2 | +2.86 `[+1.32, +4.41]` | +11.84 `[+10.12, +13.56]` |
| | 3s | **Rule-Based (tuned)** | **29.87** | [28.79, 30.94] | **98.7** | 203.2 | **-8.98** `[-9.75, -8.21]` | 0.00 |
| | 3s | Hybrid (BF, default) | 39.12 | [38.33, 39.92] | 96.8 | 171.8 | +0.28 `[-0.42, +0.97]` | +9.26 `[+8.36, +10.15]` |
| | 3s | Hybrid (BF, retuned) | 31.66 | [30.67, 32.64] | 98.1 | 231.8 | -7.19 `[-7.83, -6.55]` | +1.79 `[+1.06, +2.52]` |
| **Rush-Hour** | 0s | Fixed-Timing | 105.20 | [103.68, 106.71] | 105.2 | 114.0 | 0.00 | +24.04 `[+22.12, +25.97]` |
| | 0s | Rule-Based (default) | 80.47 | [77.82, 83.12] | 117.9 | 154.6 | -24.73 `[-26.79, -22.67]` | -0.68 `[-1.72, +0.36]` |
| | 0s | Rule-Based (tuned) | 81.15 | [78.68, 83.62] | 117.5 | 160.6 | -24.04 `[-25.97, -22.12]` | 0.00 |
| | 0s | Hybrid (BF, default) | 80.53 | [77.72, 83.34] | 117.9 | 159.0 | -24.67 `[-26.97, -22.36]` | -0.62 `[-1.66, +0.42]` (Tie) |
| | 0s | **Hybrid (BF, retuned)** | **75.57** | [72.90, 78.23] | **119.2** | 224.2 | **-29.63** `[-31.72, -27.54]` | **-5.59** `[-6.39, -4.78]` |
| | 2s | Fixed-Timing | 113.72 | [112.25, 115.18] | 101.1 | 114.0 | 0.00 | +5.91 `[+3.35, +8.48]` |
| | 2s | Rule-Based (default) | 107.79 | [105.05, 110.54] | 101.0 | 145.7 | -5.92 `[-8.23, -3.62]` | -0.01 `[-0.72, +0.70]` |
| | 2s | Rule-Based (tuned) | 107.80 | [104.77, 110.84] | 101.0 | 144.7 | -5.91 `[-8.48, -3.35]` | 0.00 |
| | 2s | **Hybrid (BF, default)** | **105.55** | [102.83, 108.27] | **103.5** | 146.8 | **-8.16** `[-10.46, -5.87]` | **-2.25** `[-2.89, -1.62]` |
| | 2s | **Hybrid (BF, retuned)** | **105.55** | [102.83, 108.27] | **103.5** | 146.8 | **-8.16** `[-10.46, -5.87]` | **-2.25** `[-2.89, -1.62]` |
| | 2s | Hybrid (QAOA) [5 seeds] | 108.04 | [102.34, 113.74] | 101.6 | 140.6 | -4.71 `[-7.44, -1.98]` | +0.24 `[-3.42, +3.90]` |
| | 3s | Fixed-Timing | 122.49 | [121.07, 123.91] | 96.8 | 114.0 | 0.00 | +7.75 `[+5.16, +10.34]` |
| | 3s | Rule-Based (default) | 136.54 | [133.15, 139.93] | 82.2 | 133.2 | +14.06 `[+10.98, +17.13]` | +21.80 `[+18.72, +24.88]` |
| | 3s | **Rule-Based (tuned)** | **114.74** | [111.63, 117.85] | **98.2** | 99.0 | **-7.75** `[-10.34, -5.16]` | 0.00 |
| | 3s | Hybrid (BF, default) | 113.23 | [110.14, 116.31] | 100.7 | 106.0 | -9.26 `[-11.93, -6.59]` | -1.51 `[-3.03, +0.01]` (Tie) |
| | 3s | Hybrid (BF, retuned) | 117.36 | [114.38, 120.35] | 98.4 | 127.4 | -5.12 `[-7.56, -2.69]` | +2.62 `[+1.60, +3.65]` |

**Honest Recomputed Findings on Switching Cost & Baseline Tuning**:
1. **Recomputed Improvement vs Fixed**:
   - **0s lost time**: 34.3% with default Hybrid (18.06s vs 27.49s); 56.9% with retuned Hybrid (11.86s vs 27.49s). In rush hour: 23.5% default (80.53s vs 105.20s); 28.2% retuned (75.57s vs 105.20s).
   - **2s lost time**: **18.2% in moderate load** (26.59s vs 32.51s), **7.2% in rush hour** (105.55s vs 113.72s).
   - **3s lost time**: Default Hybrid tied Fixed in moderate load (+0.28s, 95% CI `[-0.42s, +0.97s]`). When retuned (reopt=5, w_switch=5.0), Hybrid achieves 31.66s (18.5% improvement vs Fixed), while in rush hour it achieves 117.36s (4.2% vs Fixed).
2. **Fair Baseline Tuning & Advantage Disappearance**:
   - In moderate load under realistic lost time (2s and 3s), **Rule-Based (tuned) beats Hybrid**:
     - At 2s lost time: Rule-Based (tuned) achieves 24.32s vs Hybrid's 26.59s (**Rule-Based tuned is faster by 2.27s**, 95% CI `[+1.62, +2.92]s`).
     - At 3s lost time: Rule-Based (tuned) achieves 29.87s vs Hybrid retuned 31.66s (**Rule-Based tuned is faster by 1.79s**, 95% CI `[+1.06, +2.52]s`).
   - In rush hour:
     - At 2s lost time: Hybrid retains a modest 2.25s advantage (105.55s vs 107.80s, 95% CI `[-2.89, -1.62]s`).
     - At 3s lost time: Default Hybrid (reopt=15) is tied with Rule-Based tuned (113.23s vs 114.74s, 95% CI spans zero), while retuned Hybrid (reopt=5) loses to Rule-Based tuned by 2.62s.
3. **Exact Parameter Table & Why 37.45 / 111.20 Shifted**:
   - All Hybrid rows share common QUBO weights: `w_queue=1.0`, `w_coord=0.2`, `w_spillback=0.5`, `w_emergency=50.0`, `w_pedestrian=2.0`, `k_queue=0.5`, `spillback_threshold=0.80`.
   - The switching parameter and re-optimization interval for each lost-time setting:
     - `lt=0s`: Default (`reopt=10s, w_switch=1.0`); Retuned (`reopt=5s, w_switch=0.0`).
     - `lt=2s`: Default & Retuned (`reopt=10s, w_switch=2.5`).
     - `lt=3s`: Default (`reopt=15s, w_switch=2.5`); Retuned (`reopt=5s, w_switch=5.0`).
   - **Why 37.45s / 111.20s shifted to 39.12s / 113.23s**: The earlier figures (37.45s moderate, 111.20s rush hour) came from an initial exploratory run holding `reopt=10s` fixed. When retuning was executed systematically on training seeds 1–5 with candidate intervals `[10, 15, 20]`, `reopt=15s, w_switch=2.5` achieved the lowest combined delay on 300s training runs, translating on the 20 held-out 600s evaluation seeds to 39.12s (moderate) and 113.23s (rush hour). When given the full parity search budget `{reopt: [5, 10, 15], w_switch: [0, 1, 2.5, 5]}`, `reopt=5s, w_switch=5.0` achieved 31.66s (moderate) and 117.36s (rush hour).
   - **Tuning vs Evaluation Duration Limitation**: All hyperparameter tuning was conducted on **300s simulation runs across 5 training seeds (1–5)** to conserve compute, whereas the final reported benchmarks evaluate **600s simulation runs across 20 held-out evaluation seeds (100–119)**.
- *Data source*: `results/lost_time_sensitivity.csv`.

---

### Ablation Study: Network Coupling & Greedy Equivalence (Phase 5)

To evaluate whether the quadratic network coupling terms ($W_{coord}$ and $W_{spillback}$) actually contribute to performance, we conducted empirical ablation experiments (saved in `results/ablation_study.json` and `results/throughput_coupling_study.json`):

1. **Ablation (a): QUBO Optimum vs Independent Greedy Choice**:
   - Evaluated across **2,400 reoptimization rounds** (20 evaluation seeds $\times$ 120 rounds per run at 5s re-optimization interval).
   - **Definition of Independent Greedy**: Each junction $i \in \{0..5\}$ independently chooses its phase $x_i \in \{0, 1\}$ to minimize only its local linear queue, wait, and pedestrian terms ($w_{\text{queue}}, w_{\text{wait}}, w_{\text{ped}}, w_{\text{switch}}$), ignoring cross-junction coordination ($W_{coord}=0, W_{spillback}=0$).
   - **Finding**: In **86.58% of rounds**, the global QUBO optimum is bit-for-bit identical to the independent greedy choice. The QUBO optimum differed in only **13.42% of rounds** (322 / 2,400).
   - When different, an average of only **1.08 bits** differed (out of 6 intersections). Across all rounds, the average difference was **0.15 bits**.
2. **Ablation (b): Uncoupled Hybrid ($W_{coord}=0, W_{spillback}=0$) vs Full Hybrid**:
   - **Moderate Load**: Uncoupled Hybrid achieved **17.42s** vs Full Hybrid **18.06s** (paired difference: **-0.64s**, 95% CI `[-0.86, -0.42]s`). Removing coupling slightly improved delay.
   - **Rush Hour**: Uncoupled Hybrid achieved **80.88s** vs Full Hybrid **80.53s** (paired difference: **+0.35s**, 95% CI `[-0.35, +1.04]s`, spanning zero). This is a **statistical tie**.
3. **Ablation (c): Coupling Weights Sweep on Training Seeds**:
   - Sweeping $W_{coord} \in [0.0, 0.2, 0.5, 1.0, 2.0]$ and $W_{spillback} \in [0.0, 0.5, 1.0, 2.0]$ on training seeds 1–5 demonstrated that zero coordination ($W_{coord}=0.0$) achieved the lowest training wait time (31.24s). Setting $W_{coord} \ge 0.5$ worsened delays because forcing coordination restricts junctions from clearing localized queues.
   - **Theoretical Consequence**: With zero coupling terms, the QUBO matrix is diagonal and the corresponding Ising Hamiltonian contains **zero two-qubit interaction terms ($J_{ij} = 0$)**, decomposing into 6 trivial independent single-qubit problems.
4. **Throughput Coupling Term (Optional Investigation)**:
   - To test whether a genuinely coupled term could help, an optional directed-link discharge coordination term ($w_{\text{tc}}$) was implemented: for directed link $u \to v$, discharging toward $v$ receives a negative cost bonus only if $v$ is also green for that approach, weighted by queue plus in-transit load.
   - Tuning on training seeds 1–5 selected $w_{\text{tc}}=0.5$.
   - On the 20 evaluation seeds, this reduced wait by **3.68s** in rush hour (77.19s vs 80.88s uncoupled, 95% CI `[-4.84, -2.53]s`) and **7.22s** in surge accident (91.45s vs 98.67s uncoupled, 95% CI `[-8.47, -5.97]s`). This term is preserved as an optional configurable feature (`w_throughput_coupling=0.0` default).
- **Scientific Takeaway**: The baseline quadratic green-wave coupling terms provide no delay benefit in this 6-intersection network. The hybrid controller functions predominantly as an adaptive per-intersection optimizer with linear multi-objective weighting.

---

### Fairness of Emergency Preemption Comparison (Phase 1)

In early experiments, Hybrid soft-QUBO preemption was compared to Fixed and Rule-Based controllers *without* any preemption capability, giving an impression of an exclusive ambulance advantage. To ensure complete fairness, we implemented hard preemption (`force green along route during transit, restore afterward`) for both Fixed and Rule-Based baselines and evaluated all controllers on the identical 20 evaluation seeds with a **120-second warm-up**:

- **Ambulance Route**: Origin Node 0 -> Node 1 -> Node 2 -> Destination Node 5 (Hospital).
- **Geometry**: 4 nodes, 3 directed arterial links (0->1, 1->2, 2->5). Free-flow speed is 12.5 m/s, or 18.75 m/s at 1.5x ambulance speed. Across 3 links of 150m each (450m total), free-flow travel time is **24.0s** (8.0s per link).
- **Warm-Up Dispatch (Tick 120)**: The ambulance is dispatched inside the simulation loop at tick 120 so it encounters realistic, established queues. `ambulance_time_sec` measures elapsed time from entry at tick 120 until destination arrival.
- **Computation of Extra Civilian Delay**: Evaluated as `wait_with_ambulance - wait_without_ambulance` paired on the exact same seed and controller.

*Traffic Condition: Evaluated across 20 evaluation seeds (100–119), 600s duration, warm-up dispatch at tick 120.*

| Scenario | Controller | Vehicle Wait Mean (s) | 95% CI | Ambulance Time (s) | 95% CI | Extra Civilian Delay (s) |
|---|---|---|---|---|---|---|
| **Moderate Load** | Fixed-Timing (No Preemption) | 27.49 | [27.15, 27.83] | 50.45 | [45.74, 55.16] | 0.00 |
| | Fixed + Hard Preemption | 29.56 | [28.73, 30.40] | 32.15 | [26.82, 37.48] | +2.07 |
| | Rule-Based (tuned) (No Preemption) | 15.21 | [14.91, 15.51] | 36.25 | [32.37, 40.13] | 0.00 |
| | **Rule-Based (tuned) + Hard Preemption** | 15.72 | [15.39, 16.06] | **27.85** | [26.18, 29.52] | +0.52 |
| | Hybrid (Brute-Force) (No Preemption) | 18.06 | [17.83, 18.30] | 36.70 | [32.22, 41.18] | 0.00 |
| | Hybrid (Brute-Force) + Hard Preemption | 18.81 | [18.41, 19.21] | 29.90 | [27.84, 31.96] | +0.74 |
| | **Hybrid (Brute-Force) (Soft QUBO)** | 18.66 | [18.27, 19.04] | 30.50 | [27.86, 33.14] | +0.59 |
| **Rush-Hour** | Fixed-Timing (No Preemption) | 105.20 | [103.78, 106.61] | 93.70 | [77.51, 109.89] | 0.00 |
| | Fixed + Hard Preemption | 109.92 | [108.11, 111.74] | 74.00 | [62.95, 85.05] | +4.73 |
| | Rule-Based (tuned) (No Preemption) | 81.15 | [78.84, 83.47] | 81.25 | [67.83, 94.67] | 0.00 |
| | **Rule-Based (tuned) + Hard Preemption** | 82.81 | [80.55, 85.06] | 54.50 | [47.83, 61.17] | +1.65 |
| | Hybrid (Brute-Force) (No Preemption) | 80.53 | [77.90, 83.16] | 80.90 | [68.39, 93.41] | 0.00 |
| | **Hybrid (Brute-Force) + Hard Preemption** | 83.18 | [80.29, 86.06] | **49.70** | [41.70, 57.70] | +2.65 |
| | Hybrid (Brute-Force) (Soft QUBO) | 82.63 | [80.03, 85.22] | 57.20 | [47.23, 67.17] | +2.10 |

**Defensible Scientific Takeaway**:
- Preemption provides massive ambulance response time benefits compared to un-preempted baselines (in moderate load: 50.45s down to 27.85s–30.50s; in rush hour: 93.70s down to 49.70s–57.20s).
- However, when classical baselines also receive hard preemption, Rule-Based + Hard Preemption achieves **27.85s** (moderate) and **54.50s** (rush hour), matching or slightly beating Hybrid Soft QUBO (**30.50s** and **57.20s**).
- **The hybrid's ambulance advantage disappears when baselines also get preemption.** Soft QUBO preemption offers operational flexibility by biasing the objective rather than locking signals into an override state, but does not provide lower ambulance transit times than classical hard preemption.
- *Data source*: `results/ambulance_fairness.csv`.

---

### Pedestrian Crossing Wait Times & Model Caveats

*Traffic Condition: `pedestrians_present: True` (0.05 arrivals/s per node/direction).*

| Scenario | Controller | Ped Wait Mean (s) | 95% CI | Paired Diff vs Fixed (s) | Paired Diff vs Rule (s) |
|---|---|---|---|---|---|
| **Moderate Load** | Fixed-Timing Baseline | 7.65 | [7.30, 8.01] | 0.00 | +4.35 `[+3.94, +4.76]` |
| | Rule-Based | 3.31 | [3.15, 3.46] | -4.35 `[-4.76, -3.94]` | 0.00 |
| | **Hybrid (Brute-Force)** | **2.91** | [2.79, 3.03] | **-4.75** `[-5.12, -4.37]` | **-0.40** `[-0.59, -0.21]` |
| | Hybrid (QAOA) | 3.26 | [3.04, 3.49] | -4.39 `[-4.85, -3.93]` | -0.04 `[-0.33, +0.24]` (Tie) |
| **Rush-Hour** | Fixed-Timing Baseline | 7.65 | [7.30, 8.01] | 0.00 | -1.10 `[-1.92, -0.27]` |
| | Rule-Based | 8.75 | [8.05, 9.44] | +1.10 `[+0.27, +1.92]` | 0.00 |
| | **Hybrid (Brute-Force)** | **6.99** | [6.43, 7.55] | **-0.66** `[-1.45, +0.13]` (Tie) | **-1.76** `[-2.27, -1.25]` |
| | Hybrid (QAOA) | 7.43 | [6.98, 7.87] | -0.23 `[-0.85, +0.39]` (Tie) | -1.32 `[-1.99, -0.66]` |

**Important Pedestrian Caveats**:
1. **Pedestrian waits are inherently small** across all controllers in this model (2.8s to 8.8s) because intersection crossing distances are modeled simply without complex multi-stage pedestrian refuge islands.
2. **Rule-Based contains zero pedestrian logic**: Its lower pedestrian delay in moderate load (3.31s vs 7.65s for Fixed) is an incidental consequence of frequent vehicle phase switches clearing parallel pedestrian crosswalks, not deliberate pedestrian optimization.
3. **Rush hour difference is a statistical tie vs Fixed**: In rush hour, the Hybrid (BF) vs Fixed pedestrian wait difference is $-0.66\text{s}$ with a 95% CI of `[-1.45s, +0.13s]`. Because the CI spans zero, this difference is **a statistical tie**.
- *Data source*: `results/pedestrian_summary.csv`.

---

## Emergency Preemption Trade-Off: Soft QUBO vs Hard Override (Phase B)

A systematic sweep across 20 evaluation seeds (100–119) with warm-up dispatch at tick 120 evaluated the Pareto trade-off between ambulance response time saved and collateral delay inflicted on cross-traffic:

| Preemption Policy | $W_{emerg}$ Weight | Ambulance Travel Time (s) | Time Saved (s) | Extra Delay on Normal Traffic (s) | Average Normal Wait (s) |
|---|---|---|---|---|---|
| **No Preemption** | 0.0 | 100.20 | 0.00 | 0.00 | 45.86 |
| **Soft QUBO Bias** | 5.0 | 96.30 | 3.90 | +0.16 | 46.03 |
| **Soft QUBO Bias** | 15.0 | 80.00 | 20.20 | +0.96 | 46.82 |
| **Soft QUBO Bias** | 30.0 | 74.60 | 25.60 | +1.69 | 47.55 |
| **Soft QUBO Bias** | **50.0** | **70.20** | **30.00** | **+2.08** | **47.95** |
| **Soft QUBO Bias** | 80.0 | 68.60 | 31.60 | +2.08 | 47.95 |
| **Soft QUBO Bias** | 150.0 | 68.60 | 31.60 | +2.10 | 47.97 |
| **Hard Override** | N/A (Forced Green) | 64.60 | 35.60 | +2.08 | 47.95 |

### Empirical Preemption Analysis & Saturation
- **Soft Preemption Does NOT Beat Hard Preemption on Travel Time**: Hard preemption clears the ambulance corridor in **64.60s** (saving 35.60s), while soft QUBO preemption clears it in **70.20s** at $W_{emerg}=50$ (saving 30.00s). Soft preemption does not achieve lower ambulance response times than hard preemption.
- **Fair Preemption Baseline Finding**: Furthermore, when classical baselines (Fixed and Rule-Based) are given hard preemption, Rule-Based + Hard achieves **27.85s** in moderate load and **54.50s** in rush hour, matching or beating Hybrid Soft QUBO. The hybrid controller's ambulance-time advantage disappears under fair comparison. Soft QUBO's true value is operational flexibility (biasing the objective rather than locking signals into an override state), with modest cross-traffic delay.
- Saved artifact: `results/preemption_tradeoff.png` and `results/preemption_tradeoff.json`.


---

## "Why Quantum?" Algorithmic Evidence (Phase E)

### 1. Simulated Annealing Baseline & Classical Heuristics
Alongside Brute-Force and QAOA, a classical Simulated Annealing solver was evaluated on the traffic QUBO. Across 100 test states, Simulated Annealing finds optimal solutions in **98% of cases within 4.2ms**, establishing a fast classical heuristic baseline. Because classical heuristics also find the global optimum in most cases in milliseconds today, the honest scientific claim is: **this is a quantum-ready formulation; classical heuristics also work effectively today**.

### 2. QAOA Depth Study ($p=1$ to $4$)
Evaluated across 20 distinct traffic network snapshots with an optimizer budget scaled proportionally to circuit depth (`max_iterations = 20 + 20*p`):
- **$p=1$**: Approximation ratio $0.9031 \pm 0.0347$ (95% CI), Exact hit rate: 25.0%
- **$p=2$**: Approximation ratio $0.9025 \pm 0.0345$ (95% CI), Exact hit rate: 25.0%
- **$p=3$**: Approximation ratio $0.9217 \pm 0.0426$ (95% CI), Exact hit rate: 40.0%
- **$p=4$**: Approximation ratio **$0.9545 \pm 0.0247$** (95% CI), Exact hit rate: **55.0%**
- Metric: **best-state approximation ratio** = `(max_cost − best_sampled_cost) / (max_cost − min_cost)`.
- *Observation*: For a 6-qubit system, barren plateaus do not occur. When the optimizer budget is scaled proportionally with depth (`max_iterations = 20 + 20*p`), higher depth ($p=3, 4$) shows improved approximation ratio. However, **this result is suggestive rather than conclusive** because: (a) the iteration budget grows with $p$, so the improvement may partly reflect more optimizer steps rather than greater circuit expressivity, and (b) the 95% CIs at $p=3$ and $p=4$ overlap.
- Saved artifact: `results/qaoa_depth_vs_ratio.png` and `results/qaoa_depth_data.json`.

### 3. NISQ Depolarizing Noise Study
Simulated on PennyLane's `default.mixed` density matrix simulator under single-qubit depolarizing noise across 20 distinct traffic snapshots (mean ± 95% CI):
- Metric: **best-state approximation ratio** (same formula as depth study above).
- **Ideal (Noiseless)**: Ratio **$0.6899 \pm 0.0333$** (Top state prob: 16.86%)
- **Low Noise ($p_{gate}=0.005$)**: Ratio $0.6809 \pm 0.0319$ (Top state prob: 15.24%)
- **Medium Noise ($p_{gate}=0.02$)**: Ratio $0.6564 \pm 0.0280$ (Top state prob: 11.46%)
- **High Noise ($p_{gate}=0.05$)**: Ratio $0.6163 \pm 0.0214$ (Top state prob: 7.02%)
- *Observation*: Noiseless execution strictly outperforms noisy execution across all 20 snapshots. Solution quality and ground-truth state concentration monotonically degrade as depolarizing noise increases.
- Saved artifact: `results/qaoa_noise_study.png` and `results/qaoa_noise_data.json`.

### 4. Classical Combinatorial Scaling ($O(2^N)$ Explosion)
Brute-force exhaustive search runtime measured from $N=4$ to $N=20$ intersections ($2^N$ states) and projected to $N=24$ based on empirical evaluation throughput (~165k states/sec):

| Intersections ($N$) | Search Space ($2^N$ states) | Classical Wall-Clock Runtime | Measurement Type |
|---|---|---|---|
| 4 | 16 | 0.00021 s | Measured |
| 6 | 64 | 0.00025 s | Measured (Chennai 2x3 Grid) |
| 8 | 256 | 0.00117 s | Measured |
| 10 | 1,024 | 0.00447 s | Measured |
| 12 | 4,096 | 0.04288 s | Measured |
| 14 | 16,384 | 0.08249 s | Measured |
| 16 | 65,536 | 0.37016 s | Measured |
| 18 | 262,144 | 1.39770 s | Measured |
| 20 | 1,048,576 | 8.09737 s | Measured |
| 22 | 4,194,304 | 25.47 s | Projected (Extrapolated) |
| 24 | 16,777,216 | 101.87 s | Projected (Extrapolated) |

- *Observation*: While dense brute-force search exhibits $O(2^N)$ exponential explosion, practical traffic QUBO matrices are **sparse and structured** (planar street graph topology with bounded intersection degree $\le 4$). Specialized classical solvers (branch-and-bound, simulated annealing, and tensor network contraction) solve sparse planar spin systems far faster than dense brute-force enumeration.
- Saved artifact: `results/scaling_curve.png`, `results/scaling_table.csv`, and `results/scaling_metadata.json`.

---

## Hardware-Ready Architecture (Phase G)

To decouple optimization logic from physical actuator dynamics, a vendor-agnostic interface layer is introduced in `traffic_quantum/signal_interface.py`:

```python
class SignalControllerInterface(ABC):
    @abstractmethod
    def set_phase(self, intersection_id: int, phase: int, duration: float) -> bool: ...
    @abstractmethod
    def get_state(self, intersection_id: int) -> Dict[str, Any]: ...
    @abstractmethod
    def emergency_preempt(self, corridor_nodes: List[int], phases: Dict[int, int]) -> bool: ...
    @abstractmethod
    def safe_fallback(self) -> None: ...
```

### Safety Features Implemented
1. **Software Conflict Monitor (`SoftwareConflictMonitor`)**:
   - Strictly prohibits conflicting simultaneous green indications (e.g. concurrent N-S and E-W greens).
   - Enforces a **10-second minimum green constraint** to prevent rapid flickering.
   - *Clearance Interval Note*: Yellow and all-red clearance intervals are defined in the software conflict monitor as an architectural specification for physical field controllers; they are not exercised by the discrete tick simulator, which uses binary green/red phases.
2. **Hardware Watchdog & Heartbeat Monitor (`HardwareWatchdog`)**:
   - Monitors controller pulse heartbeats. If quantum or classical optimization times out or exceeds its execution budget (>15s elapsed), the watchdog immediately triggers `safe_fallback()` into fail-safe fixed-timing cycle.

### Future Work: Physical Signal Hardware Integration
The `SignalControllerInterface` abstracts the underlying physical signal mechanism. In future deployments, this software layer enables seamless substitution of the `TrafficSimulator` with real-world **NEMA TS2**, **Type 170**, or **ATC (Advanced Transportation Controller)** cabinet field controllers using standard **NTCIP 1202** communications protocols without altering any QUBO or QAOA code. 
*Note: No physical hardware is currently integrated or connected; all validations are conducted in simulation.*

---

## Security Architecture & Spoofing Defense (Phase F)

### Security Safeguards
- **HMAC-SHA256 JWT Authentication**: All preemption dispatches require a cryptographically signed token with role-based claims (`emergency_vehicle`, `transit_priority`).
- **Rate-Limiting Protection**: Token-bucket limiter restricts emergency preemption requests to a maximum of 5 requests per 60 seconds per vehicle ID (`SecurityConfig.rate_limit_window_sec = 60`), neutralizing denial-of-service spam.
- **Append-Only SHA-256 Hash Chaining**: Every dispatch, rejection, and preemption override is logged to an immutable audit chain (`audit_log.jsonl`). The integrity verifier re-computes the entire chain hash to detect unauthorized tampering.
- **Interactive Security Attack Demo**: The Driver Cockpit includes a dedicated test harness that simulates forged token attacks, expired token attempts, and rate-limit bursts, demonstrating real-time cryptographic rejection.
- *Notice*: In this interactive prototype, the JWT issuer is collocated within the Streamlit dashboard for demonstration purposes. In a real-world municipal deployment, tokens are issued exclusively by an isolated, air-gapped Computer-Aided Dispatch (CAD) municipal authority.

---

## Assumptions vs. Empirical Measurements

To maintain complete scientific integrity, all metrics in this system are strictly classified into either **empirical measurements** or **configurable baseline assumptions**:

| Metric / Parameter | Category | Basis / Citation |
|---|---|---|
| Vehicle Average Wait Time | **Empirical Measurement** | Measured from tick-level vehicle queue dwell timers across 20 evaluation seeds. |
| Pedestrian Average Wait Time | **Empirical Measurement** | Measured from individual pedestrian crosswalk queue timers across 20 seeds. |
| Network Throughput | **Empirical Measurement** | Measured total vehicles successfully traversing perimeter exit boundaries per minute. |
| Active Queue Depth | **Empirical Measurement** | Measured instantaneous vehicle counts accumulated behind stop lines. |
| Ambulance Response Time | **Empirical Measurement** | Measured tick difference between ambulance dispatch and hospital node arrival. |
| QAOA Approximation Ratio | **Empirical Measurement** | Ratio of QAOA expectation value to exact Brute-Force ground truth QUBO minimum. |
| Exact Optimum Hit Rate | **Empirical Measurement** | Percentage of runs where sampled QAOA bitstring matches the exact global minimum. |
| Idle Fuel Consumption Rate | **Configurable Assumption** | Typical automotive assumption: 0.8 L/hr for idling internal combustion passenger vehicles (scalar multiple of idle wait time, not an independent empirical sensor). |
| Fuel-to-CO2 Conversion Rate | **Configurable Assumption** | Typical automotive assumption: 2.31 kg CO2 per liter of gasoline consumed. |
| Road Segment Capacity | **Configurable Assumption** | Fixed geometric model assumption: 20 passenger cars per 150m directed road link (`NetworkConfig.default_road_length_m = 150.0`). |
| Urban Speed Limit | **Configurable Assumption** | Standard schematic model assumption: 45 km/h (12.5 m/s) free-flow travel speed. |

---

## Installation & Running

### Prerequisites
- Python 3.11+
- CUDA GPU optional (YOLOv8 runs smoothly on CPU)

### Install
```bash
git clone https://github.com/your-repo/hack-quant.git
cd hack-quant

pip install -r traffic_quantum/requirements.txt
```

### Environment Configuration (.env)
Copy the example environment file and set local credentials:
```bash
cp .env.example .env
```
The application defaults to open-source **OpenStreetMap / CartoDB** tiles with zero proprietary API dependencies. Google Maps tiles are available behind an explicit "demo only" UI toggle.

### Run Dashboard
```bash
streamlit run dashboard.py
# Access dashboard at http://localhost:8501
```

> [!IMPORTANT]
> **Server Security Notice**:
> Standard `streamlit run dashboard.py` operates with Cross-Origin Resource Sharing (CORS) and Cross-Site Request Forgery (XSRF) protection enabled by default.
> Disabling XSRF protection (`--server.enableXsrfProtection false`) or CORS (`--server.enableCORS false`) must **never** be used on public, untrusted networks. It is strictly reserved for private evaluation tunnels (e.g., an authenticated demo tunnel) to prevent unauthorized cross-origin requests.


### Run Multi-Seed Benchmark Suite
```bash
python traffic_quantum/benchmark.py
```

### Run Full Test Suite
```bash
pytest traffic_quantum/tests -v
```

---

## Running on Real Quantum Hardware

The project provides an **optional standalone runner** (`scripts/run_on_qpu.py`) to execute the 6-qubit traffic signal QAOA circuit on physical quantum processing units (QPUs) via **Amazon Braket** or **IBM Quantum**.

> [!WARNING]
> **Cost & Real Hardware Warning**:
> Executing jobs on physical quantum hardware is NOT free. Provider charges typically include per-task submission fees (e.g. ~$0.30 on Braket) and per-shot fees (e.g. ~$0.01 to $0.03 per shot on trapped-ion QPUs), or consume IBM Quantum monthly runtime quotas.
> Always run `--dry-run` first. The runner will refuse to submit jobs unless `--confirm` is explicitly passed.

### 1. Prerequisites

1. **Credentials**: Never commit credentials to git. Store them in `.env` (which is in `.gitignore`) or your system cloud credential store:
   ```bash
   # AWS Braket (.env or ~/.aws/credentials)
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_DEFAULT_REGION=us-east-1
   AWS_BRAKET_S3_BUCKET=amazon-braket-your-bucket-name

   # IBM Quantum (.env or qiskit-ibm-runtime save_account)
   IBM_QUANTUM_TOKEN=your_ibm_api_token
   IBM_QUANTUM_INSTANCE=ibm-q/open/main
   ```

2. **Packages**: The dependencies (`amazon-braket-sdk`, `amazon-braket-pennylane-plugin`, `qiskit`, `qiskit-ibm-runtime`, `boto3`) are installed in the Python environment.

### 2. Provider Device Verification & Pricing Notice

Device ARNs, operational availability windows, and per-shot pricing are subject to vendor changes and **must be verified in the provider console** before submitting workloads:
- **AWS Braket Console**: Navigate to *Amazon Braket > Devices* to inspect active QPU online status, queue depths, and operational hours.
  - IonQ Aria-1: `arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1` (~$0.30/task + $0.03/shot)
  - Rigetti Ankaa-9Q: `arn:aws:braket:us-west-1::device/qpu/rigetti/Ankaa-9Q` (~$0.30/task + $0.00035/shot)
  - IQM Garnet: `arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet` (~$0.30/task + $0.00145/shot)
- **IBM Quantum Platform**: Navigate to *Platform > Instances / Compute Resources* to view operational backends and queue times (e.g., `ibm_sherbrooke`, `ibm_brisbane`, or least-busy selection).

The script automatically queries the device status and **fails immediately if the target device is offline or unavailable**, saving nothing labeled "hardware".

### 3. Execution Commands

#### Safe Dry-Run (Compiles circuit, prints depth & 2-qubit gates, charges $0.00)
```bash
# Amazon Braket compilation dry-run
python scripts/run_on_qpu.py --provider braket --dry-run

# IBM Quantum compilation dry-run
python scripts/run_on_qpu.py --provider ibm --dry-run
```

#### Confirmed Hardware Execution (Submits 1 task to physical QPU)
```bash
# Execute on AWS Braket IonQ Aria-1 (1000 shots)
python scripts/run_on_qpu.py --provider braket --shots 1000 --confirm

# Execute on IBM Quantum least-busy operational backend (1000 shots)
python scripts/run_on_qpu.py --provider ibm --shots 1000 --confirm
```

### 4. Safety Guardrails Enforced by Code
- **Cost & Shot Caps**: Hard safety limit of `max_shots` (default 1,000) and `max_cost_usd` (default $35.00) in `traffic_quantum/config.py:QPUConfig`.
- **Mandatory `--confirm`**: If run without `--confirm`, the runner compiles the circuit, displays estimated cost, and exits with code 1.
- **No Silent Fallback**: If the QPU is offline or a task fails, the runner aborts with a clear error and writes no file labeled "hardware".
- **Strict Separation**: Zero QPU calls exist in the live simulation loop, benchmark, or dashboard reruns.

### 5. Verifying Your Run in Provider Consoles
Each hardware execution generates a JSON audit file in `results/qpu_run_<provider>_<timestamp>.json` and a comparison plot in `results/qpu_run_<provider>_<timestamp>.png`.
- **AWS Braket Console**: Copy the printed `Quantum Task ID` (e.g., `arn:aws:braket:...:quantum-task/...`), open the AWS Management Console -> Amazon Braket -> Quantum Tasks, and confirm the task state (`COMPLETED`), runtime, and S3 output artifacts.
- **IBM Quantum Platform**: Copy the `Job ID`, open the IBM Quantum Platform -> Jobs dashboard, and view the transpiled ISA circuit graph, QPU calibration snapshot, and execution timestamps.

### 6. Honest Performance & Noise Notice
- **No Quantum Advantage**: For a 6-intersection (6-qubit) network, classical brute-force solves the QUBO in <1 millisecond. No claim of quantum supremacy or speedup is made.
- **Noise Degradation**: Physical QPUs are subject to state preparation and measurement (SPAM) errors, gate infidelity (across the 28 two-qubit CNOT/CZ gates), and decoherence. Hardware sample distributions will show dispersion and lower approximation ratios compared to the noiseless simulator, quantified via Total Variation Distance (TVD).
- **Labeling**: Every output artifact is explicitly labeled: `"sampled on <device>, angles trained on simulator"`.

---

## Known Limitations


| Area | Limitation | Mitigation / Planned Resolution |
|---|---|---|
| **Simulator Scale** | 2x3 grid (6 intersections / 6 qubits) simulated locally on CPU. | Sufficient to demonstrate quantum encoding; physical QPUs or tensor networks required for >30 qubits. |
| **QAOA CPU Latency** | 6-qubit QAOA takes ~0.5–1.0s per solve on CPU. | For live interactive UI testing, Brute-Force mode provides instantaneous (<1ms) solving. |
| **Free Signal Switching** | **The simulator has no lost time or yellow phase, so signal switching is free; real deployments would see smaller gains from high-switching controllers.** At 2s lost time (per-intersection discharge blocked after switch), Hybrid Brute-Force advantage over Fixed narrows from 9.43s to 5.92s (moderate load). At 3s lost time, Fixed actually beats Rule-Based (Rule-Based degrades faster due to more switches). See `results/lost_time_sensitivity.csv` for the full robustness table. | Tune `switch_lost_time_sec` in config.py for deployment-realistic evaluation. |
| **Vehicle Detection** | YOLOv8n is an edge nano model; low-angle camera occlusions can cause vehicle under-counting. | Classical CV morphological fallback pipeline ensures detection continuity even without YOLO weights. |
| **Preemption Fairness** | Hybrid's ambulance time advantage (vs Fixed and Rule-Based) disappears when baselines also receive hard preemption. All three controllers achieve comparable ambulance travel times when hard preemption is applied uniformly. See `results/ambulance_fairness.csv`. | Use hard preemption for actual emergency deployments; soft QUBO preemption offers flexibility and lower collateral delay. |
| **Tuning Budget & Duration** | Parameter tuning was conducted on **300s simulation runs on 5 training seeds (1–5)** to limit search cost, while evaluation runs use **600s simulation runs on 20 held-out evaluation seeds (100–119)**. Longer evaluation runs allow queues to stabilize and capture full clearance dynamics. | Tuning on training seeds ensures unbiased evaluation on held-out seeds. |
| **Hardware Link** | Physical traffic cabinet controllers are simulated via software abstraction. | The `SignalControllerInterface` is designed for direct drop-in integration with NTCIP 1202 controller hardware. |
| **Hospital Navigation Demo** | Standalone Leaflet / Google Maps page is decoupled from live simulator signals. | Uses public OSRM / Nominatim routing servers for driver waypoint navigation; does not affect traffic lights. |


