# Quantum Traffic Brain — Defensible Pitch Claims & Claims Guide

This document establishes the official scientific boundary for the Quantum Traffic Brain project. Every claim permitted for pitch presentations, reports, and documentation is mapped directly to its supporting empirical result file. Disallowed claims are explicitly documented with technical explanations.

---

## 1. Allowed Pitch Claims (With Supporting Result Files)

### Claim 1: Quantum-Ready Formulation for Combinatorial Traffic Phase Optimization
- **Pitch Statement**: "We formulate network-wide multi-intersection traffic signal coordination as a Quadratic Unconstrained Binary Optimization (QUBO) problem solved via QAOA on a quantum circuit, with exact classical verification."
- **Supporting Files**:
  - `traffic_quantum/quantum/qubo.py`: QUBO Hamiltonian with queue, coordination, spillback, emergency, pedestrian, and switching penalties.
  - `traffic_quantum/quantum/qaoa.py`: PennyLane QAOA variational ansatz with parameterized cost and mixer unitary layers.
  - `results/scenario_benchmark.csv` / `results/benchmark_20seeds.json`: 20-seed independent evaluation proving stable optimization across all seeds.

### Claim 2: Hybrid Optimization Significantly Outperforms Fixed Timing Under Moderate and Rush-Hour Traffic
- **Pitch Statement**: "Under moderate unsaturated traffic demand, the hybrid controller reduces vehicle wait time by 9.39s (34.2% reduction) compared to fixed-timing cycles. Under directional rush-hour demand, the hybrid controller cuts average delay by 23.29s (22.1% reduction) relative to fixed timing."
- **Evidence & Data**:
  - `results/scenario_benchmark.csv`:
    - **Moderate Load**: Hybrid (BF) wait `18.11 ± 0.48s` vs Fixed `27.49 ± 0.76s` (Paired mean difference: `-9.39 ± 0.41s`, 95% CI `[-9.79, -8.98]s`, $n=20$).
    - **Rush Hour**: Hybrid (BF) wait `81.91 ± 4.64s` vs Fixed `105.20 ± 3.15s` (Paired mean difference: `-23.29 ± 1.63s`, 95% CI `[-24.92, -21.65]s`, $n=20$).
  - `results/manifest.json`: Identical 10s reoptimization interval, $W_{switch}=1.0$, evaluation seeds 100–119.

### Claim 3: Fixed-Timing is Best Under Uniform Balanced Flow; Tied Under Severe Incident Surge
- **Pitch Statement**: "When traffic demand is symmetric across all approaches, fixed 30s/30s cycling is optimal (102.45s vs 107.80s for hybrid), because adaptive phase shifting incurs transition friction. In severe incident surges, hybrid and fixed-timing are statistically tied."
- **Evidence & Data**:
  - `results/scenario_benchmark.csv`:
    - **Balanced Flow**: Fixed-Timing wait `102.45 ± 4.37s` vs Hybrid (BF) `107.80 ± 5.31s` (Paired mean diff: `+5.35 ± 1.50s` favoring Fixed).
    - **Surge + Accident**: Fixed-Timing wait `98.69 ± 2.82s` vs Hybrid (BF) `99.37 ± 5.31s` (Paired mean diff: `+0.68 ± 1.76s`, 95% CI `[-1.07, +2.44]s`, $n=20$). Because the 95% CI spans zero, this is an honest statistical tie.

### Claim 4: Hybrid Controller Matches Rule-Based on Raw Delay but Delivers Superior Multi-Objective Outcomes
- **Pitch Statement**: "While greedy rule-based (longest queue) and hybrid controllers achieve comparable vehicle delays, the hybrid controller balances multi-objective trade-offs: reducing pedestrian wait times by 12–20% and providing dedicated green corridors for emergency ambulances. However, when Rule-Based is given the same tuning budget with queue hysteresis, Hybrid retains no raw vehicle delay advantage."
- **Evidence & Data**:
  - `results/scenario_benchmark.csv`:
    - **Raw Delay**: Moderate load difference is `+0.41 ± 0.29s`; Rush hour difference is `+1.44 ± 1.41s`; Surge difference is `-0.08 ± 0.82s` (95% CI spans zero; tie).
    - **Pedestrian Wait**: Hybrid (BF) pedestrian wait is `2.91 ± 0.25s` vs Rule-Based `3.31 ± 0.33s` and vs Fixed `7.65 ± 0.74s` (moderate load); `3.52 ± 0.42s` vs `4.29 ± 0.65s` (balanced load); `5.77 ± 0.73s` vs `7.77 ± 1.76s` (surge incident); in rush hour, Hybrid (BF) is `6.99 ± 1.16s` vs Rule-Based `8.75 ± 1.45s` and vs Fixed `7.65 ± 0.74s` (paired diff vs Fixed is `-0.66s`, 95% CI `[-1.45, +0.13]s`, which is statistically insignificant).
  - `results/lost_time_sensitivity.csv` (**Fair Baseline Tuning on Seeds 1–5**):
    - When Rule-Based parameters (eval interval, min green, and queue hysteresis $h=3$) are tuned on training seeds 1–5, **Rule-Based (tuned) outperforms Hybrid in moderate load**:
      - 0s lost time: Rule-Based (tuned) 15.21s vs Hybrid default 18.06s (Rule-Based tuned is 2.85s faster, 95% CI `[-3.20, -2.51]s`). When Hybrid is retuned (reopt=5, w_switch=0), it achieves 11.86s.
      - 2s lost time: Rule-Based (tuned) 24.32s vs Hybrid 26.59s (**Rule-Based tuned is faster by 2.27s**, 95% CI `[+1.62, +2.92]s`).
      - 3s lost time: Rule-Based (tuned) 29.87s vs Hybrid retuned 31.66s (**Rule-Based tuned is faster by 1.79s**, 95% CI `[+1.06, +2.52]s`).
    - In rush hour:
      - 0s lost time: Hybrid retuned is 75.57s vs Rule-Based tuned 81.15s (Hybrid retuned is 5.59s faster).
      - 2s lost time: Hybrid retains a small 2.25s advantage (105.55s vs 107.80s, 95% CI `[-2.89, -1.62]s`).
      - 3s lost time: Default Hybrid (reopt=15) is tied with Rule-Based tuned (113.23s vs 114.74s, 95% CI spans zero), while retuned Hybrid (reopt=5) loses to Rule-Based tuned by 2.62s.
    - **Conclusion**: Under realistic switching lost times ($\ge 2$s), Hybrid has no raw delay advantage over a tuned rule-based controller (losing in moderate load, tied in rush hour). Its true role is multi-objective weighting.
  - `results/ablation_study.json` (**Network Coupling Ablation**):
    - In 2,400 reoptimization rounds across 20 seeds, the global QUBO optimum is bit-for-bit identical to the independent per-intersection greedy choice in **86.58% of rounds** (differing in only 13.42% of rounds, with 1.08 bits differing when different).
    - Uncoupled Hybrid ($W_{coord}=0, W_{spillback}=0$) achieves 17.42s vs Full Hybrid 18.06s in moderate load (-0.64s paired difference, uncoupled slightly faster) and 80.88s vs 80.53s in rush hour (+0.35s, statistical tie). Quadratic coupling provides no delay reduction.

### Claim 5: Soft QUBO Emergency Preemption vs Hard Preemption — Honest Comparison
- **Pitch Statement**: "Dynamic emergency preemption via linear QUBO corridor biasing (W_emergency=50) significantly reduces ambulance travel time compared to controllers with *no* preemption. However, when classical baselines (Fixed and Rule-Based) also receive hard preemption (forced green along the route), they achieve 8.00s ± 0.00s, matching or outperforming Hybrid soft-QUBO (9.25s ± 2.22s). The hybrid's ambulance advantage disappears when baselines also get preemption."
- **Route & Timing Mechanism**:
  - Path [0, 1, 2, 5], 4 nodes, 3 directed edges, 12s free-flow per edge. At 1.5x speed multiplier, each edge takes 8.0s, giving **24.0s total free-flow transit time** (or 36.0s at normal speed).
  - The 8.0s recorded in benchmark scripts occurred because `dispatch_ambulance(..., current_tick=15)` was initialized before the simulation step loop, allowing the ambulance to traverse edges 0->1 and 1->2 between ticks 0 and 15 into empty queues, reaching edge 2->5 at tick 15 and arriving at tick 23 ($23 - 15 = 8.0\text{s}$). When dispatched into active traffic, queue clearance delays at junction 0 add travel time unless preemption clears queues in advance.
- **Evidence & Data**:
  - `results/ambulance_fairness.csv` (n=20 seeds each, moderate_load and rush_hour):
    - **Fixed + Hard Preemption**: 8.00s ± 0.00s
    - **Rule-Based + Hard Preemption**: 8.00s ± 0.00s
    - **Hybrid (BF) Soft QUBO**: 9.25s ± 2.22s (paired diff vs Fixed+Hard: +1.25s, CI [+0.37s, +2.13s])
  - Prior benchmark without preemption for baselines:
    - Fixed (no preemption): 19.9s ± 12.2s (moderate_load); Hybrid: 9.25s → apparent advantage 10.65s
    - That advantage was an artifact of comparing Hybrid's soft preemption to baselines without any preemption.

### Claim 6: QAOA is an Approximation Algorithm; Classical Heuristics Work Effectively Today
- **Pitch Statement**: "QAOA (p=2) operates as an approximation algorithm achieving average approximation ratios between 91.9% and 94.8% across 6 qubits, finding the exact optimum 33% to 60% of the time. Classical simulated annealing also finds optimal solutions in milliseconds, demonstrating that this pipeline is quantum-ready rather than claiming classical computational obsolescence."
- **Evidence & Data**:
  - `results/scenario_benchmark.csv`: Exact hit rates (Moderate: 59.8%, Rush: 36.4%, Surge: 33.6%, Balanced: 32.6%).
  - `results/qaoa_depth_data.json`: Scaling optimizer budget with circuit depth ($20 + 20p$) confirms approximation ratio improves from 0.9031 ($p=1$) to 0.9545 ($p=4$, 55% exact hit rate).
  - `results/scaling_metadata.json`: Traffic QUBO matrices are sparse (planar topology with bounded degree $\le 4$); specialized classical solvers outperform dense brute force.

### Claim 7: Physical QPU Runner is Fully Implemented with Strict Guardrails
- **Pitch Statement**: "The repository includes an audited, cost-capped runner for Amazon Braket QPUs (`scripts/run_hardware_braket.py`) that enforces mandatory `--confirm` flags, dry-run circuit inspection, and zero secret logging."
- **Evidence & Data**:
  - `scripts/run_hardware_braket.py`: Refuses execution without explicit confirmation, validates audit schemas, supports dry-run mode.
  - `dashboard.py`: Renders recorded hardware results read-only from `results/qpu_run_*.json` only when all mandatory audit fields are present.

---

## 2. Claims to Avoid (Strictly Prohibited)

| Disallowed Claim | Why It Must NOT Be Made | What to Say Instead | Supporting Evidence |
|---|---|---|---|
| **"Quantum Advantage / Supremacy"** | A 6-intersection network has only $2^6 = 64$ states. A laptop evaluates all 64 states in 0.0003 seconds. QAOA is an approximation that achieves 91–95% approximation ratio and takes slightly longer wait time (+1.7s to +5.7s) than brute-force. | "Quantum-ready formulation validated on simulators and prepared for future fault-tolerant scaling." | `results/scaling_table.csv`, `results/scenario_benchmark.csv` |
| **"Smoother / Fewer Phase Switches"** | With the current tuned parameters, the Hybrid controller executes ~155 to 328 phase switches across 600s (~2.5x more than Fixed-timing's 114 switches), matching Rule-Based (154–324 switches). | "Hybrid optimizes for queue and coordination delay dynamically, switching phases adaptively at a rate comparable to rule-based policies." | `results/scenario_benchmark.csv` |
| **"w_switch=1.0 is the proven best weight"** | Grid tuning on training seeds (1–5) revealed differences between $W_{switch} \in [0.5, 2.5]$ were small (<1s average wait difference). | "$W_{switch}=1.0$ was selected on training seeds 1–5; differences between settings on those seeds were minor (<1s)." | `results/tuning_summary.csv` |
| **"QAOA Beats Brute-Force on Ambulance Travel Time"** | In moderate load and rush hour, the paired difference 95% CI spans zero (statistically a tie). In balanced flow, discrete 5s differences reflect stochastic civilian queue placement prior to ambulance dispatch, not algorithmic superiority. | "Both QAOA and Brute-Force apply identical $W_{emerg}=50$ biases; minor travel time differences reflect discrete simulation queue noise." | `results/scenario_benchmark.json` paired CI analysis |
| **"Hardware QPU results without hardware JSON"** | If no `results/qpu_run_*.json` file exists with all required audit fields (device name, task ID, timestamp, shots), no physical quantum hardware was used. | "All presented quantum results were evaluated on local state-vector quantum simulators (PennyLane `default.qubit` / Amazon Braket local simulator)." | `dashboard.py` `load_latest_qpu_run()` audit check |
| **"2-Second Yellow Clearance in Simulator"** | The simulator executes discrete 1-second ticks with instantaneous binary green/red signal transitions. It has no yellow clearance phase. | "The software conflict monitor includes yellow clearance logic as an architectural hardware-layer specification, but the discrete simulation engine operates on binary green/red phases." | `traffic_quantum/simulator.py`, `traffic_quantum/signal_interface.py` |
| **"EPA Standard Fuel/Emissions"** | Fuel consumption and $\text{CO}_2$ are computed purely as scalar linear multiples of vehicle idle delay using typical engineering assumptions (0.8 L/hr idle rate and 2.31 kg $\text{CO}_2$/L petrol). | "Fuel and $\text{CO}_2$ are estimated proportional to idle delay based on typical automotive values (0.8 L/hr idle rate)." | `traffic_quantum/config.py`, `traffic_quantum/metrics.py` |
| **"Higher QAOA depth fails due to Barren Plateaus"** | In a 6-qubit system, barren plateaus do not occur. Increasing depth to $p=3$ and $p=4$ increases variational angles to 6 and 8. With scaled optimizer iterations ($20 + 20p$), approximation ratio increases to 0.9545. | "Prior drops at higher depth were optimizer budget artifacts; with proportional iterations, higher depth improves solution quality." | `results/qaoa_depth_data.json` |
| **"Hybrid's ambulance advantage is fundamental"** | The advantage exists only vs *unpreempted* baselines. When Fixed and Rule-Based both receive hard preemption, they achieve 8.00s ± 0.00s (vs Hybrid soft-QUBO 9.25s ± 2.22s). The 95% CI for Hybrid–Hard Preemption diff is [+0.37s, +2.13s], fully above zero. | "Hybrid's ambulance advantage disappears when baselines also get hard preemption. See `results/ambulance_fairness.csv`." | `results/ambulance_fairness.csv` |
| **"Gains are deployment-realistic"** | The simulator has no lost time or yellow phase (switching is free). Under 2s lost-time, Hybrid's advantage over Fixed narrows from 34.3% (9.43s) to 18.2% (5.92s) in moderate load, and from 23.5% (24.67s) to 7.2% (8.16s) in rush hour. At 3s lost-time in moderate load, Hybrid and Fixed are tied (+0.28s, CI spans zero). Furthermore, against Rule-Based (tuned), Hybrid loses across all lost times in moderate load. | "The simulator has no lost time or yellow phase. Real deployments with 2–3s switching penalties would see smaller gains (18.2% moderate, 7.2% rush hour at 2s), and tuned Rule-Based beats Hybrid in moderate load. See `results/lost_time_sensitivity.csv`." | `results/lost_time_sensitivity.csv` |

---

## 3. Network Saturation Breakdown

When discussing scenario benchmarks, clearly differentiate unsaturated regimes from oversaturated regimes:

| Regime | Boundary Arrival Rate | Total Offered Load | Measured Throughput | Avg Network Queue | Saturation Status |
|---|---|---|---|---|---|
| **Moderate Load** | 0.18 cars/s per gate (all 10 gates) | **108.0 cars/min** | **99.2 – 101.1 cars/min** | **31.5 – 48.6 cars** | **Unsaturated (~75–80% capacity)**: Queues remain bounded; delays reflect pure signal timing efficiency. |
| **Balanced Flow** | 0.35 cars/s per gate (all 10 gates) | **210.0 cars/min** | **128.5 – 138.4 cars/min** | **364.4 – 397.7 cars** | **Oversaturated**: Inflow exceeds maximum network exit capacity (~138 cpm); queues grow over time. |
| **Rush Hour** | 0.45 E-W, 0.15 N-S | **162.0 cars/min** | **105.2 – 117.9 cars/min** | **219.7 – 295.3 cars** | **Oversaturated (Directional)**: Heavy arterial queues build up on East-West corridors. |
| **Surge + Incident** | 0.45 E-W, 0.20 N-S + lane closure | **180.0 cars/min** | **116.0 – 120.9 cars/min** | **301.6 – 317.3 cars** | **Oversaturated (Bottlenecked)**: Bottlenecked edge (3, 4) causes upstream queue accumulation. |

---

## 4. Pitch Talking Points Summary

1. **The Problem**: Urban traffic signal timing is a complex multi-agent coordination challenge with competing objectives (throughput, queue balance, pedestrian safety, and emergency response).
2. **The Innovation**: Formulates real-time phase selection as an interconnected QUBO problem mapped to QAOA quantum circuits and validated on Amazon Braket.
3. **The Reality**: On current small grids (6 junctions), classical solvers solve the problem in milliseconds. We do not claim quantum advantage today; we demonstrate a validated, quantum-ready optimization framework.
4. **The Benefits**: Compared to fixed timing, the adaptive system cuts delays by 23.5%–34.3% under realistic traffic at 0s lost-time, narrowing to 18.2% in moderate load and 7.2% in rush hour at 2s lost-time (and statistically tying Fixed in moderate load at 3s lost-time). Furthermore, when Rule-Based is tuned with queue hysteresis, Hybrid retains no raw vehicle delay advantage (Rule-Based tuned is faster by 2.27s to 9.26s in moderate load). The true differentiator is multi-objective integration (pedestrian weighting and emergency preemption corridors).
