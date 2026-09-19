"""Traffic Scenario Suite for Defensible Multi-Regime Evaluation.

Evaluates traffic controllers across three distinct operating conditions:
1. Balanced Flow: Uniform baseline arrival rate (0.35 cars/s) across all perimeter gates.
   - Symmetrical demand where fixed 50/50 green splits are near-optimal.
2. Rush-Hour Arterial: Highly asymmetric demand where East-West arterial receives
   3x traffic (0.45 cars/s on W/E approaches vs 0.15 cars/s on N/S approaches).
   - Tests dynamic green allocation and coordination under lopsided flow.
3. Surge + Accident: Heavy arterial surge (0.45 W/E, 0.20 N/S) combined with an active
   incident/accident on arterial link 1->2 (Saidapet Metro to Nandanam) reducing capacity.
   - Tests resilience to physical bottlenecks and spillback prevention.

Ground Rules:
- Evaluated across separate evaluation seeds (seeds 100-119).
- No hardcoded numbers or cherry-picking.
- Reports all regimes transparently, including regimes where Fixed-Timing wins.
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager, EventType, TrafficEvent
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


@dataclass
class ScenarioSpec:
    id: str
    name: str
    description: str
    boundary_rates: Optional[Dict[str, float]]
    accident_edge: Optional[Tuple[int, int]] = None
    accident_start: int = 50
    accident_duration: int = 200


SCENARIO_SPECS: Dict[str, ScenarioSpec] = {
    "balanced": ScenarioSpec(
        id="balanced",
        name="Balanced Flow (Uniform Demand)",
        description="Symmetric baseline traffic: 0.35 cars/sec across all North, South, East, West gates (oversaturated, queues grow over time).",
        boundary_rates=None,  # Uses default base_arrival_rate (0.35)
    ),
    "moderate_load": ScenarioSpec(
        id="moderate_load",
        name="Moderate Load (75-80% Saturation)",
        description="Uncongested baseline: 0.18 cars/sec per gate (~108 cars/min offered load, ~75-80% of measured network capacity).",
        boundary_rates={"W": 0.18, "E": 0.18, "N": 0.18, "S": 0.18},
    ),
    "rush_hour": ScenarioSpec(
        id="rush_hour",
        name="Rush-Hour (3x Arterial Demand)",
        description="Lopsided demand: East-West arterial gates (W, E) receive 3x traffic (0.45 cars/s) vs cross-streets (0.15 cars/s).",
        boundary_rates={"W": 0.45, "E": 0.45, "N": 0.15, "S": 0.15},
    ),
    "surge_accident": ScenarioSpec(
        id="surge_accident",
        name="Surge + Incident (Lane Closure)",
        description="Arterial surge (0.45 W/E, 0.20 N/S) + active incident on Link 1->2 (Saidapet to Nandanam) between t=50s and t=250s.",
        boundary_rates={"W": 0.45, "E": 0.45, "N": 0.20, "S": 0.20},
        accident_edge=(1, 2),
        accident_start=50,
        accident_duration=200,
    ),
}


def run_scenario_trial(
    scenario_id: str,
    ctrl_name: str,
    ctrl_factory: Callable[[RoadNetwork], object],
    seed: int,
    duration: int = 300,
    config: Optional[MasterConfig] = None,
) -> Dict[str, object]:
    """Executes a single simulation trial under the specified scenario."""
    cfg = config or DEFAULT_CONFIG
    spec = SCENARIO_SPECS[scenario_id]

    network = RoadNetwork(cfg.network)
    sim = TrafficSimulator(network=network, config=cfg, seed=seed)
    controller = ctrl_factory(network)
    emergency_mgr = EmergencyCorridorManager(network, config=cfg)
    event_mgr = EventManager(network)

    # Configure directional arrival rates
    if spec.boundary_rates:
        sim.boundary_arrival_rates = dict(spec.boundary_rates)

    # Schedule scenario incident if applicable
    if spec.accident_edge is not None:
        evt = TrafficEvent(
            id=f"scenario_accident_{seed}",
            event_type=EventType.ACCIDENT,
            start_tick=spec.accident_start,
            duration_ticks=spec.accident_duration,
            target_edge=spec.accident_edge,
        )
        event_mgr.schedule_event(evt)

    # Track phase switches
    total_phase_switches = 0
    prev_phases: Optional[Dict[int, int]] = None

    for tick in range(duration):
        event_mgr.step(tick, sim, emergency_mgr)
        biases = emergency_mgr.update_and_get_biases(tick, sim)

        if isinstance(controller, HybridController):
            phases = controller.get_phases(tick, sim, emergency_biases=biases)
        else:
            phases = controller.get_phases(tick, sim)

        if prev_phases is not None:
            total_phase_switches += sum(1 for n in phases if phases[n] != prev_phases[n])
        prev_phases = dict(phases)

        sim.step(phases)

    metrics = MetricsEngine(cfg).compute_run_metrics(sim)

    qaoa_ratios = []
    if isinstance(controller, HybridController) and controller.solver_mode == "qaoa":
        for entry in controller.optimization_history:
            if "approximation_ratio" in entry:
                qaoa_ratios.append(entry["approximation_ratio"])

    return {
        "scenario": scenario_id,
        "controller": ctrl_name,
        "seed": seed,
        "avg_wait_sec": metrics["avg_wait_sec"],
        "max_wait_sec": metrics["max_wait_sec"],
        "throughput_cpm": metrics["throughput_cars_per_min"],
        "avg_queue_cars": metrics["avg_queue_cars"],
        "fuel_liters": metrics["estimated_fuel_liters"],
        "co2_kg": metrics["estimated_co2_kg"],
        "total_switches": total_phase_switches,
        "completed_cars": len(sim.completed_vehicles),
        "qaoa_ratios": qaoa_ratios,
    }


def run_all_scenarios_benchmark(
    seeds: Optional[List[int]] = None,
    qaoa_seeds: Optional[List[int]] = None,
    duration: int = 300,
    include_qaoa: bool = True,
    output_dir: str = "results",
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Runs all 3 scenarios across evaluation seeds for all controllers."""
    if seeds is None:
        seeds = list(range(100, 120))  # 20 evaluation seeds 100-119
    if qaoa_seeds is None:
        qaoa_seeds = seeds[:5]  # Representative evaluation seeds for QAOA

    controllers = [
        ("Fixed-Timing Baseline", lambda net: FixedController(net), seeds),
        ("Rule-Based (Longest Queue)", lambda net: RuleBasedController(net), seeds),
        ("Hybrid (Brute-Force)", lambda net: HybridController(net, solver_mode="brute_force"), seeds),
    ]
    if include_qaoa:
        controllers.append(
            ("Hybrid (QAOA)", lambda net: HybridController(net, solver_mode="qaoa"), qaoa_seeds)
        )

    all_records: List[Dict[str, object]] = []
    summary_rows: List[Dict[str, object]] = []

    print("\n" + "=" * 80)
    print("DEFENSIBLE SCENARIO SUITE BENCHMARK")
    print(f"Scenarios: Balanced, Rush-Hour (3x), Surge + Incident")
    print(f"Seeds: {len(seeds)} Evaluation Seeds ({seeds[0]}..{seeds[-1]}), Duration: {duration}s each")
    print("=" * 80)

    t_start = time.time()
    total_runs = sum(len(ctrl_seeds) for _, _, ctrl_seeds in controllers) * len(SCENARIO_SPECS)
    current_run = 0

    for sc_id, sc_spec in SCENARIO_SPECS.items():
        print(f"\n--- SCENARIO: {sc_spec.name.upper()} ---")
        for ctrl_name, factory, ctrl_seeds in controllers:
            ctrl_records = []
            for s in ctrl_seeds:
                current_run += 1
                rec = run_scenario_trial(
                    scenario_id=sc_id,
                    ctrl_name=ctrl_name,
                    ctrl_factory=factory,
                    seed=s,
                    duration=duration,
                )
                ctrl_records.append(rec)
                all_records.append(rec)
                sys.stdout.write(f"\r  [{sc_id}] {ctrl_name}: Seed {s} ({current_run}/{total_runs})")
                sys.stdout.flush()
            print()

            waits = [r["avg_wait_sec"] for r in ctrl_records]
            thrus = [r["throughput_cpm"] for r in ctrl_records]
            queues = [r["avg_queue_cars"] for r in ctrl_records]
            fuels = [r["fuel_liters"] for r in ctrl_records]
            co2s = [r["co2_kg"] for r in ctrl_records]
            switches = [r["total_switches"] for r in ctrl_records]

            n_s = len(seeds)
            ci_factor = 1.96 / np.sqrt(n_s)

            row = {
                "Scenario": sc_spec.name,
                "Scenario_ID": sc_id,
                "Controller": ctrl_name,
                "Avg Wait (s)": f"{np.mean(waits):.2f} +/- {np.std(waits):.2f}",
                "Wait Mean (s)": round(float(np.mean(waits)), 2),
                "Wait Std (s)": round(float(np.std(waits)), 2),
                "Wait 95% CI": f"[{np.mean(waits) - ci_factor*np.std(waits):.2f}, {np.mean(waits) + ci_factor*np.std(waits):.2f}]",
                "Throughput (cpm)": f"{np.mean(thrus):.1f} +/- {np.std(thrus):.1f}",
                "Avg Queue": f"{np.mean(queues):.1f} +/- {np.std(queues):.1f}",
                "Est. Fuel (L)": f"{np.mean(fuels):.2f} +/- {np.std(fuels):.2f}",
                "Est. CO2 (kg)": f"{np.mean(co2s):.2f} +/- {np.std(co2s):.2f}",
                "Phase Switches": f"{np.mean(switches):.1f} +/- {np.std(switches):.1f}",
            }
            summary_rows.append(row)

    elapsed = time.time() - t_start
    print(f"\nCompleted {total_runs} scenario runs in {elapsed:.1f}s.")

    df_summary = pd.DataFrame(summary_rows)
    print("\n" + "=" * 80)
    print("SCENARIO SUITE SUMMARY RESULTS:")
    print("=" * 80)
    print(df_summary[["Scenario", "Controller", "Avg Wait (s)", "Throughput (cpm)", "Phase Switches"]].to_string(index=False))

    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "scenario_benchmark.csv")
    json_path = os.path.join(output_dir, "scenario_benchmark.json")

    df_summary.to_csv(csv_path, index=False)
    raw_payload = {
        "seeds": seeds,
        "duration": duration,
        "scenarios": list(SCENARIO_SPECS.keys()),
        "summary": summary_rows,
        "records": all_records,
    }
    with open(json_path, "w") as f:
        json.dump(raw_payload, f, indent=2)

    print(f"\nResults saved to {csv_path} and {json_path}")
    return df_summary, raw_payload


if __name__ == "__main__":
    run_all_scenarios_benchmark()
