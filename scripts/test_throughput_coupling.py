"""Throughput Coupling Experiment (PART 4).

Tests whether an explicit directed-link discharge coordination term helps:
For directed link u->v, the benefit of u discharging toward v depends on v
also being green for that approach.

1. Tunes w_tc in [0.0, 0.05, 0.1, 0.2, 0.5] on training seeds 1-5 only.
2. Evaluates selected w_tc vs uncoupled hybrid and tuned rule-based on 20 evaluation seeds (100-119)
   in rush_hour and surge_accident regimes.
3. Computes paired differences and 95% CIs.
4. Saves to results/throughput_coupling_study.json.
"""

import copy
import json
import os
import sys
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager, EventType, TrafficEvent
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.scenarios import SCENARIO_SPECS
from traffic_quantum.simulator import TrafficSimulator


def run_trial(scenario_id: str, ctrl, seed: int, duration: int = 300, config: MasterConfig = None) -> float:
    cfg = config or DEFAULT_CONFIG
    spec = SCENARIO_SPECS[scenario_id]
    net = RoadNetwork(cfg.network)
    sim = TrafficSimulator(net, cfg, seed=seed)
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

    ctrl.reset()
    for tick in range(duration):
        evt_mgr.step(tick, sim, em_mgr)
        biases = em_mgr.update_and_get_biases(tick, sim)
        if isinstance(ctrl, HybridController):
            phases = ctrl.get_phases(tick, sim, emergency_biases=biases)
        else:
            phases = ctrl.get_phases(tick, sim)
        sim.step(phases)

    m = MetricsEngine().compute_run_metrics(sim)
    return float(m["avg_wait_sec"])


def compute_ci(data: np.ndarray) -> Tuple[float, List[float]]:
    m = float(np.mean(data))
    if len(data) <= 1:
        return round(m, 2), [round(m, 2), round(m, 2)]
    ci = float(1.96 * float(np.std(data, ddof=1)) / np.sqrt(len(data)))
    return round(m, 2), [round(m - ci, 2), round(m + ci, 2)]


def run_experiment():
    training_seeds = [1, 2, 3, 4, 5]
    eval_seeds = list(range(100, 120))
    scenarios = ["rush_hour", "surge_accident"]
    candidates = [0.0, 0.05, 0.1, 0.2, 0.5]

    print("--- Phase 1: Tuning w_throughput_coupling on Training Seeds 1-5 (300s) ---", flush=True)
    tuning_scores = {}
    for wtc in candidates:
        total_w = 0.0
        for sc in scenarios:
            for s in training_seeds:
                cfg = copy.deepcopy(DEFAULT_CONFIG)
                cfg.qubo.w_throughput_coupling = wtc
                net = RoadNetwork(cfg.network)
                ctrl = HybridController(net, config=cfg, solver_mode="brute_force")
                w = run_trial(sc, ctrl, s, duration=300, config=cfg)
                total_w += w
        mean_score = total_w / (len(scenarios) * len(training_seeds))
        tuning_scores[wtc] = mean_score
        print(f"  w_tc = {wtc:4.2f} -> Mean Combined Wait: {mean_score:.2f}s", flush=True)

    best_wtc = min(tuning_scores, key=tuning_scores.get)
    print(f"\nBest w_throughput_coupling selected: {best_wtc} (mean wait {tuning_scores[best_wtc]:.2f}s)", flush=True)

    print("\n--- Phase 2: Evaluation on 20 Evaluation Seeds (600s) ---", flush=True)
    results = {
        "tuning_scores_training_seeds": tuning_scores,
        "selected_w_tc": best_wtc,
        "evaluations": {},
    }

    for sc in scenarios:
        print(f"\nEvaluating Scenario: {sc}...", flush=True)
        # 1. Uncoupled Hybrid (w_coord=0, w_spill=0, w_tc=0)
        cfg_uncoupled = copy.deepcopy(DEFAULT_CONFIG)
        cfg_uncoupled.qubo.w_coord = 0.0
        cfg_uncoupled.qubo.w_spillback = 0.0
        cfg_uncoupled.qubo.w_throughput_coupling = 0.0

        # 2. Tuned Throughput Coupled Hybrid
        cfg_coupled = copy.deepcopy(DEFAULT_CONFIG)
        cfg_coupled.qubo.w_throughput_coupling = best_wtc

        # 3. Rule-Based (tuned)
        cfg_rule = copy.deepcopy(DEFAULT_CONFIG)

        waits_uncoupled = []
        waits_coupled = []
        waits_rule = []

        for s in eval_seeds:
            # Uncoupled Hybrid
            net_u = RoadNetwork(cfg_uncoupled.network)
            ctrl_u = HybridController(net_u, config=cfg_uncoupled, solver_mode="brute_force")
            w_u = run_trial(sc, ctrl_u, s, duration=600, config=cfg_uncoupled)
            waits_uncoupled.append(w_u)

            # Coupled Hybrid
            net_c = RoadNetwork(cfg_coupled.network)
            ctrl_c = HybridController(net_c, config=cfg_coupled, solver_mode="brute_force")
            w_c = run_trial(sc, ctrl_c, s, duration=600, config=cfg_coupled)
            waits_coupled.append(w_c)

            # Tuned Rule-Based
            net_r = RoadNetwork(cfg_rule.network)
            ctrl_r = RuleBasedController(net_r, config=cfg_rule, eval_interval_sec=5, min_green_sec=10, hysteresis=0)
            w_r = run_trial(sc, ctrl_r, s, duration=600, config=cfg_rule)
            waits_rule.append(w_r)

        arr_u = np.array(waits_uncoupled)
        arr_c = np.array(waits_coupled)
        arr_r = np.array(waits_rule)

        diff_vs_uncoupled = arr_c - arr_u
        diff_vs_rule = arr_c - arr_r

        m_u, ci_u = compute_ci(arr_u)
        m_c, ci_c = compute_ci(arr_c)
        m_r, ci_r = compute_ci(arr_r)
        d_u, ci_du = compute_ci(diff_vs_uncoupled)
        d_r, ci_dr = compute_ci(diff_vs_rule)

        print(f"  Uncoupled Hybrid: {m_u:.2f}s {ci_u}", flush=True)
        print(f"  Coupled Hybrid (w_tc={best_wtc}): {m_c:.2f}s {ci_c}", flush=True)
        print(f"  Rule-Based (tuned): {m_r:.2f}s {ci_r}", flush=True)
        print(f"  Paired Diff (Coupled - Uncoupled): {d_u:+.2f}s {ci_du}", flush=True)
        print(f"  Paired Diff (Coupled - Rule-Based): {d_r:+.2f}s {ci_dr}", flush=True)

        results["evaluations"][sc] = {
            "uncoupled_wait_mean": m_u,
            "uncoupled_wait_ci": ci_u,
            "coupled_wait_mean": m_c,
            "coupled_wait_ci": ci_c,
            "rule_tuned_wait_mean": m_r,
            "rule_tuned_wait_ci": ci_r,
            "paired_diff_vs_uncoupled_mean": d_u,
            "paired_diff_vs_uncoupled_ci": ci_du,
            "paired_diff_vs_rule_mean": d_r,
            "paired_diff_vs_rule_ci": ci_dr,
        }

    os.makedirs("results", exist_ok=True)
    out_path = "results/throughput_coupling_study.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved throughput coupling results to {out_path}", flush=True)
    return results


if __name__ == "__main__":
    run_experiment()
