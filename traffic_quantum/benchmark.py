"""Multi-Seed Headless Benchmark Suite for Traffic Signal Controllers.

Runs Fixed-Timing, Rule-Based, Hybrid (Brute-Force), and Hybrid (QAOA) controllers across
20 separate evaluation seeds (seeds 100-119) with 600 simulated seconds per run.
Computes and reports mean +/- standard deviation and 95% Confidence Intervals for:
- Average wait time (s)
- Pedestrian average wait time (s)
- Network throughput (cars/min)
- Average queue length (cars)
- Estimated fuel consumption (L)
- Estimated CO2 emissions (kg)
- Ambulance travel time (s) and normal traffic extra delay (s)
- QAOA approximation ratio and exact optimum hit frequency

Saves complete results to results/benchmark_20seeds.json and results/benchmark_summary.csv.
"""

import json
import os
import sys
import time
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def run_single_controller_trial(
    ctrl_name: str,
    ctrl_factory,
    seed: int,
    duration: int = 600,
    has_emergency: bool = True,
) -> Dict[str, object]:
    """Runs a single simulation run for a given controller and seed."""
    cfg = DEFAULT_CONFIG
    network = RoadNetwork(cfg.network)
    sim = TrafficSimulator(network=network, config=cfg, seed=seed)
    controller = ctrl_factory(network)
    emergency_mgr = EmergencyCorridorManager(network, config=cfg)
    event_mgr = EventManager(network)

    amb_mission = None
    if has_emergency:
        amb_mission = emergency_mgr.dispatch_ambulance(
            origin=0, destination=5, simulator=sim, current_tick=15
        )

    for tick in range(duration):
        event_mgr.step(tick, sim, emergency_mgr)
        biases = emergency_mgr.update_and_get_biases(tick, sim)

        if isinstance(controller, HybridController):
            phases = controller.get_phases(tick, sim, emergency_biases=biases)
        else:
            phases = controller.get_phases(tick, sim)

        sim.step(phases)

    m = MetricsEngine().compute_run_metrics(sim)
    amb_time = (
        (amb_mission.arrival_tick - amb_mission.dispatch_tick)
        if (amb_mission and amb_mission.arrival_tick)
        else duration
    )

    qaoa_ratios = []
    qaoa_exact_hits = []
    if isinstance(controller, HybridController) and controller.solver_mode == "qaoa":
        for entry in controller.optimization_history:
            if "approximation_ratio" in entry:
                qaoa_ratios.append(entry["approximation_ratio"])
            if "found_exact_optimum" in entry:
                qaoa_exact_hits.append(entry["found_exact_optimum"])

    return {
        "controller": ctrl_name,
        "seed": seed,
        "avg_wait_sec": m["avg_wait_sec"],
        "avg_pedestrian_wait_sec": m.get("avg_pedestrian_wait_sec", 0.0),
        "throughput_cpm": m["throughput_cars_per_min"],
        "avg_queue_cars": m["avg_queue_cars"],
        "fuel_liters": m["estimated_fuel_liters"],
        "co2_kg": m["estimated_co2_kg"],
        "ambulance_time_sec": amb_time,
        "qaoa_ratios": qaoa_ratios,
        "qaoa_exact_hits": qaoa_exact_hits,
    }


def run_benchmark(
    seeds: List[int] = None,
    duration: int = 600,
    include_qaoa: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Runs the comparative benchmark across all 4 controllers on evaluation seeds."""
    if seeds is None:
        seeds = list(range(100, 120))  # 20 evaluation seeds 100-119

    print("\n" + "=" * 78)
    print("QUANTUM-ENHANCED ADAPTIVE URBAN TRAFFIC OPTIMIZATION")
    print(f"DEFENSIBLE MULTI-SEED BENCHMARK ({len(seeds)} Seeds: {seeds[0]}..{seeds[-1]}, {duration}s each)")
    print("=" * 78)

    controller_defs = [
        ("Fixed-Timing Baseline", lambda net: FixedController(net)),
        ("Rule-Based (Longest Queue)", lambda net: RuleBasedController(net)),
        ("Hybrid (Brute-Force)", lambda net: HybridController(net, solver_mode="brute_force")),
    ]
    if include_qaoa:
        controller_defs.append(
            ("Hybrid (QAOA)", lambda net: HybridController(net, solver_mode="qaoa"))
        )

    all_results: Dict[str, List[Dict[str, object]]] = {name: [] for name, _ in controller_defs}
    baseline_no_preempt_waits = {s: 0.0 for s in seeds}

    # Run un-preempted baseline to calculate extra delay to normal traffic
    for s in seeds:
        net = RoadNetwork(DEFAULT_CONFIG.network)
        sim = TrafficSimulator(net, config=DEFAULT_CONFIG, seed=s)
        ctrl = FixedController(net)
        for t in range(duration):
            sim.step(ctrl.get_phases(t, sim))
        baseline_no_preempt_waits[s] = MetricsEngine().compute_run_metrics(sim)["avg_wait_sec"]

    total_runs = len(controller_defs) * len(seeds)
    current_run = 0
    t_start = time.time()

    for name, factory in controller_defs:
        print(f"\nEvaluating: {name}...")
        for s in seeds:
            current_run += 1
            res = run_single_controller_trial(name, factory, seed=s, duration=duration)
            all_results[name].append(res)
            sys.stdout.write(f"\r  Progress: Seed {s} completed ({current_run}/{total_runs})")
            sys.stdout.flush()
        print()

    elapsed_total = time.time() - t_start
    print(f"\nCompleted {total_runs} benchmark runs in {elapsed_total:.1f}s.")

    # Aggregate Statistics
    summary_rows = []
    raw_export = {"seeds": seeds, "duration": duration, "controllers": {}}

    for name, _ in controller_defs:
        records = all_results[name]
        raw_export["controllers"][name] = records

        waits = [r["avg_wait_sec"] for r in records]
        ped_waits = [r["avg_pedestrian_wait_sec"] for r in records]
        thrus = [r["throughput_cpm"] for r in records]
        queues = [r["avg_queue_cars"] for r in records]
        fuels = [r["fuel_liters"] for r in records]
        co2s = [r["co2_kg"] for r in records]
        amb_times = [r["ambulance_time_sec"] for r in records]
        extra_delays = [
            max(0.0, r["avg_wait_sec"] - baseline_no_preempt_waits[r["seed"]])
            for r in records
        ]

        n_s = len(seeds)
        ci_factor = 1.96 / np.sqrt(n_s)

        row = {
            "Controller": name,
            "Avg Wait (s)": f"{np.mean(waits):.2f} +/- {np.std(waits):.2f}",
            "Wait 95% CI": f"[{np.mean(waits) - ci_factor*np.std(waits):.2f}, {np.mean(waits) + ci_factor*np.std(waits):.2f}]",
            "Avg Ped Wait (s)": f"{np.mean(ped_waits):.2f} +/- {np.std(ped_waits):.2f}",
            "Throughput (cpm)": f"{np.mean(thrus):.1f} +/- {np.std(thrus):.1f}",
            "Avg Queue": f"{np.mean(queues):.1f} +/- {np.std(queues):.1f}",
            "Est. Fuel (L)": f"{np.mean(fuels):.2f} +/- {np.std(fuels):.2f}",
            "Est. CO2 (kg)": f"{np.mean(co2s):.2f} +/- {np.std(co2s):.2f}",
            "Ambulance Time (s)": f"{np.mean(amb_times):.1f} +/- {np.std(amb_times):.1f}",
            "Extra Delay (s)": f"{np.mean(extra_delays):.2f} +/- {np.std(extra_delays):.2f}",
        }

        if name == "Hybrid (QAOA)":
            all_ratios = [val for r in records for val in r["qaoa_ratios"]]
            all_hits = [val for r in records for val in r["qaoa_exact_hits"]]
            if all_ratios:
                row["QAOA Approx Ratio"] = f"{np.mean(all_ratios):.4f} +/- {np.std(all_ratios):.4f}"
                row["Exact Hit %"] = f"{(sum(all_hits)/len(all_hits))*100:.1f}%"

        summary_rows.append(row)

    df_summary = pd.DataFrame(summary_rows)

    print("\n" + "=" * 78)
    print("BENCHMARK RESULTS (Mean +/- Std Dev across 20 Evaluation Seeds):")
    print("=" * 78)
    print(df_summary.to_string(index=False))

    os.makedirs("results", exist_ok=True)
    df_summary.to_csv("results/benchmark_summary.csv", index=False)
    with open("results/benchmark_20seeds.json", "w") as f:
        json.dump(raw_export, f, indent=2)

    print(f"\nSaved summary to results/benchmark_summary.csv and full runs to results/benchmark_20seeds.json")
    return df_summary, raw_export


if __name__ == "__main__":
    run_benchmark()
