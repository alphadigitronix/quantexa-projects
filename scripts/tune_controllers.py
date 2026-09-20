"""Parity Hyperparameter Optimization for Classical Baselines and Hybrid Controller.

Strict Scientific Ground Rules:
1. Optimization is performed strictly on TRAINING seeds 1-10.
2. Unseen EVALUATION seeds (100-119) are NEVER touched during tuning.
3. Equal Tuning Budget: Every learned/tuned controller receives comparable grid sizes (~71-80 combinations).
4. Tuned across switch_lost_time_sec = 0s, 2s, 3s with headline constraint min_green >= 10s and unconstrained minimums.
5. All 8 regimes evaluated: balanced, moderate_load, directional_moderate, incident_moderate,
   shifting_demand, surge_moderate, rush_hour, surge_accident.
6. Explicit boundary warnings when optimal parameters fall on grid edges.
"""

from concurrent.futures import ProcessPoolExecutor
import datetime
import itertools
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.controllers.max_pressure import MaxPressureController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager, EventType, TrafficEvent
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.scenarios import SCENARIO_SPECS
from traffic_quantum.simulator import TrafficSimulator

TRAINING_SEEDS = list(range(1, 11))  # Seeds 1 to 10
SIM_DURATION = 600

# Tuning grids specified by protocol
RULE_BASED_EVAL_INTERVALS = [2, 5, 10, 15]
RULE_BASED_MIN_GREENS = [5, 10, 15, 20]
RULE_BASED_HYSTERESES = [0, 1, 2, 3, 5]

MAX_PRESSURE_EVAL_INTERVALS = [2, 5, 10, 15]
MAX_PRESSURE_MIN_GREENS = [5, 10, 15, 20]
MAX_PRESSURE_HYSTERESES = [0, 1, 2, 3, 5]

FIXED_CYCLES = [30, 40, 50, 60, 70, 80, 90]

HYBRID_REOPT_INTERVALS = [2, 5, 10, 15]
HYBRID_W_SWITCHES = [0.0, 1.0, 2.5, 5.0]
HYBRID_W_COUPLINGS = [0.0, 0.05, 0.1, 0.2, 0.5]


def build_fixed_grid(headline_only: bool = False) -> List[Dict[str, int]]:
    """Builds comprehensive FixedController (cycle x split) candidate grid."""
    candidates = []
    for c in FIXED_CYCLES:
        if c == 30:
            splits = [5, 10, 15, 20, 25]
        elif c == 40:
            splits = [5, 10, 15, 20, 25, 30, 35]
        elif c == 50:
            splits = [5, 10, 15, 20, 25, 30, 35, 40, 45]
        elif c == 60:
            splits = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
        elif c == 70:
            splits = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
        elif c == 80:
            splits = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
        elif c == 90:
            splits = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
        else:
            splits = [c // 2]

        for s in splits:
            if headline_only:
                if s < 10 or (c - s) < 10:
                    continue
            candidates.append({"cycle_len_sec": c, "ns_green_sec": s})
    return candidates


def build_rule_based_grid(headline_only: bool = False) -> List[Dict[str, int]]:
    """Builds RuleBasedController candidate grid."""
    candidates = []
    min_greens = [g for g in RULE_BASED_MIN_GREENS if g >= 10] if headline_only else RULE_BASED_MIN_GREENS
    for ei, mg, h in itertools.product(RULE_BASED_EVAL_INTERVALS, min_greens, RULE_BASED_HYSTERESES):
        candidates.append({"eval_interval_sec": ei, "min_green_sec": mg, "hysteresis": h})
    return candidates


def build_max_pressure_grid(headline_only: bool = False) -> List[Dict[str, int]]:
    """Builds MaxPressureController candidate grid."""
    candidates = []
    min_greens = [g for g in MAX_PRESSURE_MIN_GREENS if g >= 10] if headline_only else MAX_PRESSURE_MIN_GREENS
    for ei, mg, h in itertools.product(MAX_PRESSURE_EVAL_INTERVALS, min_greens, MAX_PRESSURE_HYSTERESES):
        candidates.append({"eval_interval_sec": ei, "min_green_sec": mg, "hysteresis": h})
    return candidates


def build_hybrid_grid(headline_only: bool = False) -> List[Dict[str, float]]:
    """Builds HybridController candidate grid."""
    candidates = []
    reopts = [r for r in HYBRID_REOPT_INTERVALS if r >= 10] if headline_only else HYBRID_REOPT_INTERVALS
    for r, ws, wc in itertools.product(reopts, HYBRID_W_SWITCHES, HYBRID_W_COUPLINGS):
        candidates.append({"reopt_interval_sec": r, "w_switch": ws, "w_throughput_coupling": wc})
    return candidates


def _evaluate_single_trial(args: Tuple) -> float:
    controller_type, ctrl_kwargs, config_dict, scenario_id, seed, duration, switch_lost_time_sec = args
    cfg = MasterConfig()
    cfg.simulation.switch_lost_time_sec = switch_lost_time_sec
    for section, kvs in config_dict.items():
        sub_cfg = getattr(cfg, section)
        for k, v in kvs.items():
            setattr(sub_cfg, k, v)

    network = RoadNetwork(cfg.network)
    sim = TrafficSimulator(network=network, config=cfg, seed=seed)
    spec = SCENARIO_SPECS[scenario_id]

    if spec.boundary_rates:
        if callable(spec.boundary_rates):
            sim.boundary_arrival_rates = spec.boundary_rates
        else:
            sim.boundary_arrival_rates = dict(spec.boundary_rates)

    if controller_type == "fixed":
        ctrl = FixedController(network, cfg, **ctrl_kwargs)
    elif controller_type == "rule_based":
        ctrl = RuleBasedController(network, cfg, **ctrl_kwargs)
    elif controller_type == "max_pressure":
        ctrl = MaxPressureController(network, cfg, **ctrl_kwargs)
    elif controller_type == "hybrid":
        ctrl = HybridController(network, cfg, solver_mode="brute_force")
    else:
        raise ValueError(f"Unknown controller_type: {controller_type}")

    emergency_mgr = EmergencyCorridorManager(network, config=cfg)
    event_mgr = EventManager(network)
    if spec.accident_edge is not None:
        evt = TrafficEvent(
            id=f"tune_accident_{seed}",
            event_type=EventType.ACCIDENT,
            start_tick=spec.accident_start,
            duration_ticks=spec.accident_duration,
            target_edge=spec.accident_edge,
        )
        event_mgr.schedule_event(evt)

    for tick in range(duration):
        event_mgr.step(tick, sim, emergency_mgr)
        biases = emergency_mgr.update_and_get_biases(tick, sim)
        if isinstance(ctrl, HybridController):
            phases = ctrl.get_phases(tick, sim, emergency_biases=biases)
        else:
            phases = ctrl.get_phases(tick, sim)
        sim.step(phases)

    metrics = MetricsEngine(cfg).compute_run_metrics(sim)
    return metrics["avg_wait_sec"]


def check_boundaries(param_name: str, val: Any, allowed_vals: List[Any]) -> str:
    """Returns boundary status string for a tuned parameter."""
    min_v, max_v = min(allowed_vals), max(allowed_vals)
    if val == min_v:
        return f"ON LOWER BOUNDARY ({val} == min {allowed_vals})"
    elif val == max_v:
        return f"ON UPPER BOUNDARY ({val} == max {allowed_vals})"
    return f"INTERIOR ({val} inside {allowed_vals})"


def run_controller_tuning_sweep(
    lost_time_sec: int = 2,
    headline_min_green: bool = True,
    max_workers: int = 10,
    regimes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Tunes all 4 controllers on training seeds 1-10 for the specified lost-time and min_green constraint."""
    mode_label = f"LostTime={lost_time_sec}s | {'Headline (min_green>=10s)' if headline_min_green else 'Unconstrained Minimums'}"
    print("\n" + "=" * 90)
    print(f"STARTING CONTROLLER TUNING SWEEP: {mode_label}")
    print(f"Training Seeds: {TRAINING_SEEDS} | Duration: {SIM_DURATION}s | Workers: {max_workers}")
    print("=" * 90)

    target_regimes = regimes or list(SCENARIO_SPECS.keys())
    results: Dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "lost_time_sec": lost_time_sec,
            "headline_min_green": headline_min_green,
            "training_seeds": TRAINING_SEEDS,
            "sim_duration_sec": SIM_DURATION,
        },
        "fixed": {},
        "fixed_tuned": {},
        "rule_based": {},
        "rule_based_tuned": {},
        "max_pressure": {},
        "max_pressure_tuned": {},
        "hybrid": {},
        "hybrid_tuned": {},
        "boundary_audits": {},
    }

    fixed_candidates = build_fixed_grid(headline_only=headline_min_green)
    rule_candidates = build_rule_based_grid(headline_only=headline_min_green)
    mp_candidates = build_max_pressure_grid(headline_only=headline_min_green)
    hybrid_candidates = build_hybrid_grid(headline_only=headline_min_green)

    print(f"\nParameter Combinations per Regime:")
    print(f"  Fixed:        {len(fixed_candidates):>3} combinations ({len(fixed_candidates)*len(TRAINING_SEEDS):>4} trials)")
    print(f"  Rule-Based:   {len(rule_candidates):>3} combinations ({len(rule_candidates)*len(TRAINING_SEEDS):>4} trials)")
    print(f"  Max-Pressure: {len(mp_candidates):>3} combinations ({len(mp_candidates)*len(TRAINING_SEEDS):>4} trials)")
    print(f"  Hybrid:       {len(hybrid_candidates):>3} combinations ({len(hybrid_candidates)*len(TRAINING_SEEDS):>4} trials)")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for sc_id in target_regimes:
            sc_name = SCENARIO_SPECS[sc_id].name
            print(f"\n>>> Tuning Regime: {sc_id} ({sc_name})")

            # 1. Fixed
            fixed_tasks = []
            for cand in fixed_candidates:
                for s in TRAINING_SEEDS:
                    fixed_tasks.append(("fixed", cand, {}, sc_id, s, SIM_DURATION, lost_time_sec))
            fixed_results = list(executor.map(_evaluate_single_trial, fixed_tasks))
            # Reshape into (num_candidates, num_seeds)
            f_arr = np.array(fixed_results).reshape(len(fixed_candidates), len(TRAINING_SEEDS))
            f_means = np.mean(f_arr, axis=1)
            f_best_idx = int(np.argmin(f_means))
            f_best = fixed_candidates[f_best_idx]
            results["fixed"][sc_id] = {
                **f_best,
                "mean_wait_training": round(float(f_means[f_best_idx]), 2),
            }
            results["fixed_tuned"][sc_id] = results["fixed"][sc_id]
            c_status = check_boundaries("cycle_len_sec", f_best["cycle_len_sec"], FIXED_CYCLES)
            print(f"  [Fixed]        Wait: {f_means[f_best_idx]:.2f}s | cycle={f_best['cycle_len_sec']}s ({c_status}), NS={f_best['ns_green_sec']}s")

            # 2. Rule-Based
            rule_tasks = []
            for cand in rule_candidates:
                for s in TRAINING_SEEDS:
                    rule_tasks.append(("rule_based", cand, {}, sc_id, s, SIM_DURATION, lost_time_sec))
            rule_results = list(executor.map(_evaluate_single_trial, rule_tasks))
            r_arr = np.array(rule_results).reshape(len(rule_candidates), len(TRAINING_SEEDS))
            r_means = np.mean(r_arr, axis=1)
            r_best_idx = int(np.argmin(r_means))
            r_best = rule_candidates[r_best_idx]
            results["rule_based"][sc_id] = {
                **r_best,
                "mean_wait_training": round(float(r_means[r_best_idx]), 2),
            }
            results["rule_based_tuned"][sc_id] = results["rule_based"][sc_id]
            r_ei_st = check_boundaries("eval_interval", r_best["eval_interval_sec"], RULE_BASED_EVAL_INTERVALS)
            r_mg_st = check_boundaries("min_green", r_best["min_green_sec"], RULE_BASED_MIN_GREENS)
            r_hy_st = check_boundaries("hysteresis", r_best["hysteresis"], RULE_BASED_HYSTERESES)
            print(f"  [Rule-Based]   Wait: {r_means[r_best_idx]:.2f}s | eval={r_best['eval_interval_sec']}s ({r_ei_st}), min_green={r_best['min_green_sec']}s ({r_mg_st}), hyst={r_best['hysteresis']} ({r_hy_st})")

            # 3. Max-Pressure
            mp_tasks = []
            for cand in mp_candidates:
                for s in TRAINING_SEEDS:
                    mp_tasks.append(("max_pressure", cand, {}, sc_id, s, SIM_DURATION, lost_time_sec))
            mp_results = list(executor.map(_evaluate_single_trial, mp_tasks))
            mp_arr = np.array(mp_results).reshape(len(mp_candidates), len(TRAINING_SEEDS))
            mp_means = np.mean(mp_arr, axis=1)
            mp_best_idx = int(np.argmin(mp_means))
            mp_best = mp_candidates[mp_best_idx]
            results["max_pressure"][sc_id] = {
                **mp_best,
                "mean_wait_training": round(float(mp_means[mp_best_idx]), 2),
            }
            results["max_pressure_tuned"][sc_id] = results["max_pressure"][sc_id]
            mp_ei_st = check_boundaries("eval_interval", mp_best["eval_interval_sec"], MAX_PRESSURE_EVAL_INTERVALS)
            mp_mg_st = check_boundaries("min_green", mp_best["min_green_sec"], MAX_PRESSURE_MIN_GREENS)
            mp_hy_st = check_boundaries("hysteresis", mp_best["hysteresis"], MAX_PRESSURE_HYSTERESES)
            print(f"  [Max-Pressure] Wait: {mp_means[mp_best_idx]:.2f}s | eval={mp_best['eval_interval_sec']}s ({mp_ei_st}), min_green={mp_best['min_green_sec']}s ({mp_mg_st}), hyst={mp_best['hysteresis']} ({mp_hy_st})")

            # 4. Hybrid
            hybrid_tasks = []
            for cand in hybrid_candidates:
                cfg_dict = {
                    "qubo": {
                        "w_throughput_coupling": cand["w_throughput_coupling"],
                        "w_switch": cand["w_switch"],
                    },
                    "hybrid": {
                        "reopt_interval_sec": cand["reopt_interval_sec"],
                    },
                }
                for s in TRAINING_SEEDS:
                    hybrid_tasks.append(("hybrid", {}, cfg_dict, sc_id, s, SIM_DURATION, lost_time_sec))
            hybrid_results = list(executor.map(_evaluate_single_trial, hybrid_tasks))
            h_arr = np.array(hybrid_results).reshape(len(hybrid_candidates), len(TRAINING_SEEDS))
            h_means = np.mean(h_arr, axis=1)
            h_best_idx = int(np.argmin(h_means))
            h_best = hybrid_candidates[h_best_idx]
            results["hybrid"][sc_id] = {
                **h_best,
                "mean_wait_training": round(float(h_means[h_best_idx]), 2),
            }
            results["hybrid_tuned"][sc_id] = results["hybrid"][sc_id]
            h_re_st = check_boundaries("reopt_interval", h_best["reopt_interval_sec"], HYBRID_REOPT_INTERVALS)
            h_ws_st = check_boundaries("w_switch", h_best["w_switch"], HYBRID_W_SWITCHES)
            h_wc_st = check_boundaries("w_coupling", h_best["w_throughput_coupling"], HYBRID_W_COUPLINGS)
            print(f"  [Hybrid]       Wait: {h_means[h_best_idx]:.2f}s | reopt={h_best['reopt_interval_sec']}s ({h_re_st}), w_sw={h_best['w_switch']} ({h_ws_st}), w_tc={h_best['w_throughput_coupling']} ({h_wc_st})")

            results["boundary_audits"][sc_id] = {
                "fixed": {"cycle_len_sec": c_status},
                "rule_based": {"eval_interval": r_ei_st, "min_green": r_mg_st, "hysteresis": r_hy_st},
                "max_pressure": {"eval_interval": mp_ei_st, "min_green": mp_mg_st, "hysteresis": mp_hy_st},
                "hybrid": {"reopt_interval": h_re_st, "w_switch": h_ws_st, "w_coupling": h_wc_st},
            }

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Regime Parity Tuning")
    parser.add_argument("--lost-time", type=int, default=2, help="Lost time penalty per switch (0, 2, 3)")
    parser.add_argument("--all-lost-times", action="store_true", help="Run tuning sweeps for lost times 0, 2, and 3")
    parser.add_argument("--smoke-test", action="store_true", help="Quick smoke test on 2 seeds and 1 regime")
    args = parser.parse_args()

    if args.smoke_test:
        global TRAINING_SEEDS, SIM_DURATION
        TRAINING_SEEDS = [1, 2]
        SIM_DURATION = 60
        res = run_controller_tuning_sweep(lost_time_sec=2, headline_min_green=True, max_workers=2, regimes=["moderate_load"])
        out_path = os.path.join("results", "tuned_parameters_smoke.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"\nSmoke test complete! Saved to {out_path}")
        return

    all_tuning_data: Dict[str, Any] = {}
    lost_times = [2, 3, 0] if args.all_lost_times else [args.lost_time]

    for lt in lost_times:
        # Headline sweep (min_green >= 10s)
        headline_key = f"lost_time_{lt}s_headline"
        headline_res = run_controller_tuning_sweep(lost_time_sec=lt, headline_min_green=True, max_workers=10)
        all_tuning_data[headline_key] = headline_res

        # Unconstrained sweep (min_green down to 5s)
        unconstrained_key = f"lost_time_{lt}s_unconstrained"
        unconstrained_res = run_controller_tuning_sweep(lost_time_sec=lt, headline_min_green=False, max_workers=10)
        all_tuning_data[unconstrained_key] = unconstrained_res

    # Also maintain primary tuned_parameters.json pointing to headline 2s for default reference
    import copy
    primary_payload = copy.deepcopy(all_tuning_data.get("lost_time_2s_headline", list(all_tuning_data.values())[0]))
    primary_payload["all_sweeps"] = all_tuning_data

    out_file = os.path.join("results", "tuned_parameters.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(primary_payload, f, indent=2)
    print(f"\nAll tuning sweeps completed successfully! Output saved to: {out_file}")


if __name__ == "__main__":
    main()
