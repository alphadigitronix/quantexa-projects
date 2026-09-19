"""Parity Tuning & Ablation Study for Hybrid Traffic Optimization.

Covers:
1. Parity Tuning: Hybrid (BF, retuned) tuned on training seeds 1-5 across reopt in {5, 10, 15}
   and w_switch in {0.0, 1.0, 2.5, 5.0} for lost times 0, 2, 3s.
2. Evaluates Hybrid (BF, retuned) on 20 evaluation seeds (100-119) and integrates into
   results/lost_time_sensitivity.csv and results/lost_time_sensitivity.json with paired CIs
   vs Fixed and vs Rule-Based (tuned).
3. Ablation Study:
   (a) Fraction of rounds QUBO optimum differs from independent per-intersection greedy choice,
       and mean bits differing.
   (b) Uncoupled Hybrid (w_coord=0, w_spillback=0) vs Full Hybrid across 20 evaluation seeds.
   (c) Impact of larger coupling weights on training seeds.
"""

import copy
import json
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.quantum.brute_force import BruteForceOptimizer
from traffic_quantum.scenarios import SCENARIO_SPECS
from traffic_quantum.simulator import TrafficSimulator
from scripts.run_lost_time_study import run_single_simulation, compute_ci


def run_ablation_greedy_comparison(eval_seeds=range(100, 120), scenarios=("moderate_load", "rush_hour")):
    """Compares global QUBO optimum with independent per-intersection greedy choice."""
    print("\n--- Running Ablation (a): QUBO Optimum vs Independent Greedy Choice ---")
    total_rounds = 0
    different_rounds = 0
    total_bit_differences = 0

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.hybrid.reopt_interval_sec = 10

    for sc in scenarios:
        spec = SCENARIO_SPECS[sc]
        for s in eval_seeds:
            net = RoadNetwork(cfg.network)
            sim = TrafficSimulator(net, cfg, seed=s)
            if spec.boundary_rates:
                sim.boundary_arrival_rates = dict(spec.boundary_rates)
            ctrl = HybridController(net, config=cfg, solver_mode="brute_force")
            ctrl.reset()

            for tick in range(600):
                needs_reopt = (tick - ctrl.last_reopt_tick >= cfg.hybrid.reopt_interval_sec)
                if needs_reopt:
                    total_rounds += 1
                    Q, C0 = ctrl.qubo_builder.build_qubo(sim)
                    qubo_x, _, _ = BruteForceOptimizer.solve(Q, C0)

                    # Independent greedy choice: optimize each intersection independently (ignore off-diagonal)
                    greedy_x = np.zeros(6, dtype=int)
                    for i in range(6):
                        # x_i=1 cost is Q[i, i], x_i=0 cost is 0
                        greedy_x[i] = 1 if Q[i, i] < 0 else 0

                    diff_bits = np.sum(np.abs(qubo_x - greedy_x))
                    if diff_bits > 0:
                        different_rounds += 1
                        total_bit_differences += diff_bits

                phases = ctrl.get_phases(tick, sim)
                sim.step(phases)

    fraction_different = different_rounds / total_rounds if total_rounds > 0 else 0.0
    avg_bits_when_diff = total_bit_differences / different_rounds if different_rounds > 0 else 0.0
    avg_bits_overall = total_bit_differences / total_rounds if total_rounds > 0 else 0.0

    print(f"Total reoptimization rounds evaluated: {total_rounds}")
    print(f"Rounds where QUBO != Independent Greedy: {different_rounds} ({fraction_different*100:.2f}%)")
    print(f"Average bits differing (when different): {avg_bits_when_diff:.2f} / 6 bits")
    print(f"Average bits differing (across all rounds): {avg_bits_overall:.2f} / 6 bits")

    return {
        "total_rounds": total_rounds,
        "different_rounds": different_rounds,
        "fraction_different": fraction_different,
        "avg_bits_when_diff": avg_bits_when_diff,
        "avg_bits_overall": avg_bits_overall,
    }


def run_ablation_uncoupled(eval_seeds=range(100, 120), scenarios=("moderate_load", "rush_hour")):
    """Compares Full Hybrid (w_coord=0.2, w_spillback=0.5) vs Uncoupled Hybrid (w_coord=0, w_spillback=0)."""
    print("\n--- Running Ablation (b): Full Hybrid vs Uncoupled Hybrid (w_coord=0, w_spillback=0) ---")
    results = {}

    for sc in scenarios:
        full_waits = []
        uncoupled_waits = []
        paired_diffs = []

        for s in eval_seeds:
            # Full hybrid
            cfg_full = copy.deepcopy(DEFAULT_CONFIG)
            cfg_full.hybrid.reopt_interval_sec = 10
            cfg_full.qubo.w_coord = 0.2
            cfg_full.qubo.w_spillback = 0.5
            ctrl_full = HybridController(RoadNetwork(cfg_full.network), config=cfg_full, solver_mode="brute_force")
            res_full = run_single_simulation(sc, ctrl_full, s, lost_time_sec=0, duration=600, config=cfg_full)
            full_waits.append(res_full["avg_wait_sec"])

            # Uncoupled hybrid
            cfg_unc = copy.deepcopy(DEFAULT_CONFIG)
            cfg_unc.hybrid.reopt_interval_sec = 10
            cfg_unc.qubo.w_coord = 0.0
            cfg_unc.qubo.w_spillback = 0.0
            ctrl_unc = HybridController(RoadNetwork(cfg_unc.network), config=cfg_unc, solver_mode="brute_force")
            res_unc = run_single_simulation(sc, ctrl_unc, s, lost_time_sec=0, duration=600, config=cfg_unc)
            uncoupled_waits.append(res_unc["avg_wait_sec"])

            paired_diffs.append(res_unc["avg_wait_sec"] - res_full["avg_wait_sec"])

        mean_full = float(np.mean(full_waits))
        ci_full = compute_ci(full_waits)
        mean_unc = float(np.mean(uncoupled_waits))
        ci_unc = compute_ci(uncoupled_waits)
        mean_diff = float(np.mean(paired_diffs))
        ci_diff = compute_ci(paired_diffs)

        print(f"Scenario: {sc}")
        print(f"  Full Hybrid wait:       {mean_full:.2f}s 95% CI [{ci_full[0]:.2f}, {ci_full[1]:.2f}]")
        print(f"  Uncoupled Hybrid wait:  {mean_unc:.2f}s 95% CI [{ci_unc[0]:.2f}, {ci_unc[1]:.2f}]")
        print(f"  Paired Diff (Unc - Full): {mean_diff:+.2f}s 95% CI [{ci_diff[0]:.2f}, {ci_diff[1]:.2f}]")

        results[sc] = {
            "full_wait_mean": mean_full,
            "full_wait_ci": list(ci_full),
            "uncoupled_wait_mean": mean_unc,
            "uncoupled_wait_ci": list(ci_unc),
            "paired_diff_mean": mean_diff,
            "paired_diff_ci": list(ci_diff),
        }

    return results


def run_ablation_larger_coupling_weights(training_seeds=(1, 2, 3, 4, 5)):
    """Sweeps larger coupling weights on training seeds to check if increasing coupling helps."""
    print("\n--- Running Ablation (c): Sweep Larger Coupling Weights on Training Seeds 1-5 ---")
    coord_candidates = [0.0, 0.2, 0.5, 1.0, 2.0]
    spill_candidates = [0.0, 0.5, 1.0, 2.0]

    sweep_results = []
    for w_c in coord_candidates:
        for w_s in spill_candidates:
            total_wait = 0.0
            for sc in ["moderate_load", "rush_hour"]:
                for s in training_seeds:
                    cfg = copy.deepcopy(DEFAULT_CONFIG)
                    cfg.hybrid.reopt_interval_sec = 10
                    cfg.qubo.w_coord = w_c
                    cfg.qubo.w_spillback = w_s
                    ctrl = HybridController(RoadNetwork(cfg.network), config=cfg, solver_mode="brute_force")
                    res = run_single_simulation(sc, ctrl, s, lost_time_sec=0, duration=300, config=cfg)
                    total_wait += res["avg_wait_sec"]
            avg_w = total_wait / 10.0
            sweep_results.append((avg_w, w_c, w_s))

    sweep_results.sort()
    print("Top 5 weight combinations on training seeds:")
    for avg_w, w_c, w_s in sweep_results[:5]:
        print(f"  w_coord={w_c:.1f}, w_spillback={w_s:.1f} -> mean wait: {avg_w:.2f}s")

    default_score = next(r[0] for r in sweep_results if r[1] == 0.2 and r[2] == 0.5)
    zero_score = next(r[0] for r in sweep_results if r[1] == 0.0 and r[2] == 0.0)
    print(f"Default (w_coord=0.2, w_spillback=0.5): {default_score:.2f}s")
    print(f"Zero Coupling (w_coord=0.0, w_spillback=0.0): {zero_score:.2f}s")

    return {
        "sweep_results": [{"avg_wait": r[0], "w_coord": r[1], "w_spillback": r[2]} for r in sweep_results],
        "default_score": default_score,
        "zero_score": zero_score,
    }


def main():
    print("=" * 80)
    print("PARITY TUNING & COMPREHENSIVE ABLATION STUDY")
    print("=" * 80)

    # 1. Parity tuning configs selected on training seeds 1-5 (combined across scenarios)
    retuned_hyb_params = {
        0: {"reopt_interval_sec": 5, "w_switch": 0.0},
        2: {"reopt_interval_sec": 10, "w_switch": 2.5},
        3: {"reopt_interval_sec": 5, "w_switch": 5.0},
    }

    eval_seeds = list(range(100, 120))
    scenarios = ["moderate_load", "rush_hour"]
    lost_times = [0, 2, 3]

    # Load current lost time sensitivity file
    lt_csv_path = os.path.join(os.path.dirname(__file__), "..", "results", "lost_time_sensitivity.csv")
    lt_json_path = os.path.join(os.path.dirname(__file__), "..", "results", "lost_time_sensitivity.json")

    df_existing = pd.read_csv(lt_csv_path) if os.path.exists(lt_csv_path) else pd.DataFrame()
    with open(lt_json_path, "r", encoding="utf-8") as f:
        existing_json = json.load(f)

    # Run evaluations for Hybrid (BF, retuned)
    retuned_records = []
    print("\n--- Evaluating Hybrid (BF, retuned) on 20 Evaluation Seeds ---")

    for sc in scenarios:
        for lt in lost_times:
            p = retuned_hyb_params[lt]
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            cfg.hybrid.reopt_interval_sec = p["reopt_interval_sec"]
            cfg.qubo.w_switch = p["w_switch"]

            ctrl = HybridController(RoadNetwork(cfg.network), config=cfg, solver_mode="brute_force")
            runs = []
            for s in eval_seeds:
                r = run_single_simulation(sc, ctrl, s, lt, duration=600, config=cfg)
                r["controller"] = "Hybrid (BF, retuned)"
                runs.append(r)

            # Get corresponding Fixed and Rule-Based (tuned) runs for paired differences
            waits_hyb = [r["avg_wait_sec"] for r in runs]
            mean_wait = float(np.mean(waits_hyb))
            ci_wait = compute_ci(waits_hyb)
            tps = [r["throughput_cpm"] for r in runs]
            mean_tp = float(np.mean(tps))
            ci_tp = compute_ci(tps)
            switches = [r["total_switches"] for r in runs]
            mean_sw = float(np.mean(switches))
            ci_sw = compute_ci(switches)
            ped_waits = [r["avg_pedestrian_wait_sec"] for r in runs]
            mean_ped = float(np.mean(ped_waits))
            ci_ped = compute_ci(ped_waits)

            # Find matching Fixed runs from existing JSON
            sub_f = [entry for entry in existing_json["records"] if entry["scenario"] == sc and entry["lost_time_sec"] == lt and entry["controller"] == "Fixed-Timing"]
            sub_rt = [entry for entry in existing_json["records"] if entry["scenario"] == sc and entry["lost_time_sec"] == lt and entry["controller"] == "Rule-Based (tuned)"]

            diffs_vs_f = [waits_hyb[i] - sub_f[i]["avg_wait_sec"] for i in range(20)]
            mean_df = float(np.mean(diffs_vs_f))
            ci_df = compute_ci(diffs_vs_f)

            diffs_vs_rt = [waits_hyb[i] - sub_rt[i]["avg_wait_sec"] for i in range(20)]
            mean_drt = float(np.mean(diffs_vs_rt))
            ci_drt = compute_ci(diffs_vs_rt)

            print(f"Scenario {sc}, lost_time={lt}s (reopt={p['reopt_interval_sec']}, w_switch={p['w_switch']}):")
            print(f"  Wait: {mean_wait:.2f}s [{ci_wait[0]:.2f}, {ci_wait[1]:.2f}]")
            print(f"  Paired diff vs Fixed:             {mean_df:+.2f}s [{ci_df[0]:.2f}, {ci_df[1]:.2f}]")
            print(f"  Paired diff vs Rule-Based (tuned): {mean_drt:+.2f}s [{ci_drt[0]:.2f}, {ci_drt[1]:.2f}]")

            retuned_records.append({
                "scenario": sc,
                "lost_time_sec": lt,
                "controller": "Hybrid (BF, retuned)",
                "seeds_evaluated": 20,
                "avg_wait_sec": round(mean_wait, 2),
                "wait_95_ci": [round(ci_wait[0], 2), round(ci_wait[1], 2)],
                "throughput_cpm": round(mean_tp, 2),
                "throughput_95_ci": [round(ci_tp[0], 2), round(ci_tp[1], 2)],
                "total_switches": round(mean_sw, 1),
                "switches_95_ci": [round(ci_sw[0], 1), round(ci_sw[1], 1)],
                "avg_pedestrian_wait_sec": round(mean_ped, 2),
                "pedestrian_wait_95_ci": [round(ci_ped[0], 2), round(ci_ped[1], 2)],
                "paired_diff_vs_fixed_sec": round(mean_df, 2),
                "paired_ci_vs_fixed": [round(ci_df[0], 2), round(ci_df[1], 2)],
                "paired_diff_vs_rule_sec": round(mean_drt, 2),  # vs Rule-Based (tuned)
                "paired_ci_vs_rule": [round(ci_drt[0], 2), round(ci_drt[1], 2)],
                "paired_diff_vs_hybrid_sec": 0.0,
                "paired_ci_vs_hybrid": [0.0, 0.0],
                "ambulance_present": False,
                "pedestrians_present": True,
            })

            # Append raw runs to existing JSON
            existing_json["records"].extend(runs)

    # Combine into lost_time_sensitivity.csv and json
    df_new_summary = pd.DataFrame(retuned_records)
    df_combined = pd.concat([df_existing[df_existing["controller"] != "Hybrid (BF, retuned)"], df_new_summary], ignore_index=True)
    df_combined = df_combined.sort_values(by=["scenario", "lost_time_sec", "controller"]).reset_index(drop=True)
    df_combined.to_csv(lt_csv_path, index=False)

    existing_json["tuned_parameters_hybrid_retuned_training_seeds"] = retuned_hyb_params
    existing_json["summary"] = df_combined.to_dict(orient="records")
    with open(lt_json_path, "w", encoding="utf-8") as f:
        json.dump(existing_json, f, indent=2)
    print(f"\nSuccessfully updated {lt_csv_path} and {lt_json_path}")

    # 2. Run Ablations
    ablation_a = run_ablation_greedy_comparison()
    ablation_b = run_ablation_uncoupled()
    ablation_c = run_ablation_larger_coupling_weights()

    ablation_summary = {
        "ablation_a_greedy_comparison": ablation_a,
        "ablation_b_uncoupled": ablation_b,
        "ablation_c_coupling_sweep": ablation_c,
    }

    ablation_path = os.path.join(os.path.dirname(__file__), "..", "results", "ablation_study.json")
    with open(ablation_path, "w", encoding="utf-8") as f:
        json.dump(ablation_summary, f, indent=2)
    print(f"\nSaved ablation results to {ablation_path}")


if __name__ == "__main__":
    main()
