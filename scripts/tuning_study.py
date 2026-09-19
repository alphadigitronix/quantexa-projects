"""Tuning study on TRAINING SEEDS 1-5 only.

Explores:
- reopt_interval_sec: 10, 15, 25
- w_switch: 0.0, 1.0, 2.5
Across rush_hour and surge_accident (and balanced, moderate_load)
to understand controller performance tradeoffs.
"""

import sys
import os
import copy
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager, EventType, TrafficEvent
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.scenarios import SCENARIO_SPECS


def evaluate_trial(scenario_id: str, controller, seed: int, duration: int = 300, config = None) -> float:
    cfg = config or DEFAULT_CONFIG
    spec = SCENARIO_SPECS[scenario_id]
    net = RoadNetwork(cfg.network)
    sim = TrafficSimulator(net, config=cfg, seed=seed)
    if spec.boundary_rates:
        sim.boundary_arrival_rates = dict(spec.boundary_rates)

    em_mgr = EmergencyCorridorManager(net, config=cfg)
    evt_mgr = EventManager(net)
    if spec.accident_edge:
        evt = TrafficEvent(
            id=f"accident_{seed}",
            event_type=EventType.ACCIDENT,
            start_tick=spec.accident_start,
            duration_ticks=spec.accident_duration,
            target_edge=spec.accident_edge,
        )
        evt_mgr.schedule_event(evt)

    controller.reset()
    for tick in range(duration):
        evt_mgr.step(tick, sim, em_mgr)
        biases = em_mgr.update_and_get_biases(tick, sim)
        if isinstance(controller, HybridController):
            phases = controller.get_phases(tick, sim, emergency_biases=biases)
        else:
            phases = controller.get_phases(tick, sim)
        sim.step(phases)

    m = MetricsEngine().compute_run_metrics(sim)
    return m["avg_wait_sec"]


def run_tuning():
    training_seeds = [1, 2, 3, 4, 5]
    reopt_intervals = [10, 15, 25]
    w_switches = [0.0, 1.0, 2.5]
    scenarios_to_test = ["rush_hour", "surge_accident", "balanced"]

    print("=" * 80)
    print("HYBRID CONTROLLER TUNING STUDY ON TRAINING SEEDS (1-5)")
    print(f"Scenarios: {scenarios_to_test}")
    print(f"Reopt Intervals: {reopt_intervals}")
    print(f"Switching Weights (w_switch): {w_switches}")
    print("=" * 80)

    # First, benchmark classical baselines on training seeds
    baseline_results = {}
    for sc in scenarios_to_test:
        fixed_waits = [evaluate_trial(sc, FixedController(RoadNetwork(DEFAULT_CONFIG.network)), s) for s in training_seeds]
        rule_waits = [evaluate_trial(sc, RuleBasedController(RoadNetwork(DEFAULT_CONFIG.network)), s) for s in training_seeds]
        baseline_results[f"{sc}_fixed"] = np.mean(fixed_waits)
        baseline_results[f"{sc}_rule"] = np.mean(rule_waits)
        print(f"[{sc}] Baseline Means -> Fixed: {np.mean(fixed_waits):.2f}s | Rule-Based: {np.mean(rule_waits):.2f}s")

    print("\nEvaluating Hybrid (Brute-Force) combinations:")
    records = []

    for sc in scenarios_to_test:
        for reopt in reopt_intervals:
            for w_sw in w_switches:
                cfg = copy.deepcopy(DEFAULT_CONFIG)
                cfg.hybrid.reopt_interval_sec = reopt
                cfg.qubo.w_switch = w_sw

                waits = []
                for s in training_seeds:
                    net = RoadNetwork(cfg.network)
                    ctrl = HybridController(net, config=cfg, solver_mode="brute_force")
                    w = evaluate_trial(sc, ctrl, s, config=cfg)
                    waits.append(w)

                mean_wait = float(np.mean(waits))
                fixed_base = baseline_results[f"{sc}_fixed"]
                rule_base = baseline_results[f"{sc}_rule"]

                records.append({
                    "Scenario": sc,
                    "Reopt (s)": reopt,
                    "w_switch": w_sw,
                    "Hybrid Wait (s)": round(mean_wait, 2),
                    "vs Fixed (s)": round(mean_wait - fixed_base, 2),
                    "vs Rule (s)": round(mean_wait - rule_base, 2),
                })
                print(f"  {sc:<14} | Reopt={reopt:>2}s, w_sw={w_sw:>3.1f} | Hybrid={mean_wait:.2f}s | vs Fixed={mean_wait-fixed_base:+.2f}s | vs Rule={mean_wait-rule_base:+.2f}s")

    df_res = pd.DataFrame(records)
    print("\n" + "=" * 80)
    print("TUNING SUMMARY TABLE:")
    print("=" * 80)
    print(df_res.to_string(index=False))

    best_configs = {}
    for sc in scenarios_to_test:
        sub = df_res[df_res["Scenario"] == sc].sort_values(by="Hybrid Wait (s)")
        best_configs[sc] = sub.iloc[0].to_dict()
        print(f"\nBest Config for {sc}: Reopt={best_configs[sc]['Reopt (s)']}s, w_sw={best_configs[sc]['w_switch']} -> Wait={best_configs[sc]['Hybrid Wait (s)']}s")


if __name__ == "__main__":
    run_tuning()
