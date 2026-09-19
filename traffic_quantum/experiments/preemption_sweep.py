"""Phase B: Soft Preemption vs Hard Override Emergency Trade-off Study.

Sweeps W_emerg across multiple values and compares:
1. No Preemption (W_emerg = 0)
2. Soft QUBO Corridor (W_emerg in [5, 15, 30, 50, 80, 150])
3. Hard Override Baseline (unconditional green along corridor)

Measures:
- Ambulance travel time (s) and time saved (s)
- Extra delay imposed on normal traffic (s)
Outputs trade-off chart to results/preemption_tradeoff.png and json summary.
"""

import json
import os
import sys
import copy

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np

from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.metrics import MetricsEngine
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def run_single_preemption_trial(
    seed: int,
    w_emerg: float,
    hard_override: bool = False,
    duration: int = 240,
    dispatch_tick: int = 120,
) -> Dict[str, float]:
    """Runs a single simulation trial with given preemption configuration."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.qubo.w_emergency = w_emerg
    net = RoadNetwork(cfg.network)
    sim = TrafficSimulator(network=net, config=cfg, seed=seed)
    ctrl = HybridController(net, config=cfg, solver_mode="brute_force")
    mgr = EmergencyCorridorManager(net, config=cfg)
    mgr.hard_preemption_mode = hard_override

    amb = None

    for tick in range(duration):
        if tick == dispatch_tick:
            amb = mgr.dispatch_ambulance(
                origin=0,
                destination=5,
                simulator=sim,
                current_tick=dispatch_tick,
                hard_preemption=hard_override,
            )

        biases = mgr.update_and_get_biases(tick, sim)
        if hard_override:
            # Force green directly along route
            phases = ctrl.get_phases(tick, sim, emergency_biases=biases)
            for node, r_dir in biases.items():
                p = 0 if r_dir == "NS" else 1
                phases[node] = p
        elif w_emerg > 0:
            phases = ctrl.get_phases(tick, sim, emergency_biases=biases)
        else:
            # No preemption passed to controller
            phases = ctrl.get_phases(tick, sim, emergency_biases=None)

        sim.step(phases)

    m = MetricsEngine().compute_run_metrics(sim)
    amb_time = (amb.arrival_tick - amb.dispatch_tick) if (amb and amb.arrival_tick) else float(duration - dispatch_tick)
    return {
        "avg_wait_sec": m["avg_wait_sec"],
        "ambulance_time_sec": amb_time,
        "throughput": m["throughput_cars_per_min"],
    }


def run_preemption_sweep(seeds: List[int] = None, duration: int = 240, dispatch_tick: int = 120):
    """Executes the preemption sweep across 20 evaluation seeds."""
    if seeds is None:
        seeds = list(range(100, 120))  # 20 evaluation seeds 100-119

    w_values = [5.0, 15.0, 30.0, 50.0, 80.0, 150.0]
    print(f"Starting Preemption Sweep across {len(seeds)} evaluation seeds (100-119)...")

    # 1. Baseline: No Preemption (W_emerg = 0)
    baseline_amb_times = []
    baseline_waits = []
    for s in seeds:
        res = run_single_preemption_trial(s, w_emerg=0.0, hard_override=False, duration=duration, dispatch_tick=dispatch_tick)
        baseline_amb_times.append(res["ambulance_time_sec"])
        baseline_waits.append(res["avg_wait_sec"])

    base_amb_mean = float(np.mean(baseline_amb_times))
    base_wait_mean = float(np.mean(baseline_waits))
    print(f"No Preemption Baseline: Amb Time = {base_amb_mean:.1f}s, Normal Traffic Wait = {base_wait_mean:.1f}s")

    tradeoff_results = {
        "no_preemption": {
            "w_emerg": 0.0,
            "label": "No Preemption",
            "amb_time": base_amb_mean,
            "amb_time_saved": 0.0,
            "extra_delay": 0.0,
            "normal_wait": base_wait_mean,
        },
        "soft_preemption": [],
        "hard_override": {},
    }

    # 2. Soft Preemption sweep
    for w in w_values:
        amb_times = []
        waits = []
        for s in seeds:
            res = run_single_preemption_trial(s, w_emerg=w, hard_override=False, duration=duration, dispatch_tick=dispatch_tick)
            amb_times.append(res["ambulance_time_sec"])
            waits.append(res["avg_wait_sec"])

        m_amb = float(np.mean(amb_times))
        m_wait = float(np.mean(waits))
        saved = max(0.0, base_amb_mean - m_amb)
        extra_delay = max(0.0, m_wait - base_wait_mean)

        tradeoff_results["soft_preemption"].append({
            "w_emerg": w,
            "label": f"Soft (W={int(w)})",
            "amb_time": round(m_amb, 2),
            "amb_time_saved": round(saved, 2),
            "extra_delay": round(extra_delay, 2),
            "normal_wait": round(m_wait, 2),
        })
        print(f"Soft (W={w:3.0f}): Amb Time = {m_amb:.1f}s (Saved {saved:.1f}s) | Extra Delay = +{extra_delay:.2f}s")

    # 3. Hard Override baseline
    hard_amb_times = []
    hard_waits = []
    for s in seeds:
        res = run_single_preemption_trial(s, w_emerg=50.0, hard_override=True, duration=duration, dispatch_tick=dispatch_tick)
        hard_amb_times.append(res["ambulance_time_sec"])
        hard_waits.append(res["avg_wait_sec"])

    hard_amb_mean = float(np.mean(hard_amb_times))
    hard_wait_mean = float(np.mean(hard_waits))
    hard_saved = max(0.0, base_amb_mean - hard_amb_mean)
    hard_extra = max(0.0, hard_wait_mean - base_wait_mean)

    tradeoff_results["hard_override"] = {
        "label": "Hard Override",
        "amb_time": round(hard_amb_mean, 2),
        "amb_time_saved": round(hard_saved, 2),
        "extra_delay": round(hard_extra, 2),
        "normal_wait": round(hard_wait_mean, 2),
    }
    print(f"Hard Override: Amb Time = {hard_amb_mean:.1f}s (Saved {hard_saved:.1f}s) | Extra Delay = +{hard_extra:.2f}s")

    # 4. Save JSON results
    os.makedirs("results", exist_ok=True)
    with open("results/preemption_tradeoff.json", "w") as f:
        json.dump(tradeoff_results, f, indent=2)

    # 5. Generate Trade-off Chart
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#111827")

    # Plot No Preemption
    ax.scatter([0.0], [0.0], color="#94a3b8", s=140, zorder=5, label="No Preemption (Origin)")
    ax.annotate(" No Preemption", (0.0, 0.0), color="#94a3b8", fontsize=10, verticalalignment="bottom")

    # Plot Soft points
    soft_x = [p["extra_delay"] for p in tradeoff_results["soft_preemption"]]
    soft_y = [p["amb_time_saved"] for p in tradeoff_results["soft_preemption"]]
    ax.plot(soft_x, soft_y, color="#38bdf8", linestyle="--", alpha=0.7, label="Soft QUBO Pareto Curve")
    scatter = ax.scatter(soft_x, soft_y, c=w_values, cmap="cool", s=160, zorder=5, edgecolors="white", linewidths=1.5)

    for pt in tradeoff_results["soft_preemption"]:
        ax.annotate(
            f" W={int(pt['w_emerg'])}",
            (pt["extra_delay"], pt["amb_time_saved"]),
            color="#e2e8f0",
            fontsize=9,
            verticalalignment="bottom",
        )

    # Plot Hard Override
    ax.scatter(
        [hard_extra],
        [hard_saved],
        color="#ef4444",
        s=200,
        marker="^",
        zorder=6,
        label=f"Hard Override (+{hard_extra:.2f}s delay)",
        edgecolors="white",
        linewidths=1.5,
    )
    ax.annotate(
        " Hard Override\n (Forced Green)",
        (hard_extra, hard_saved),
        color="#f87171",
        fontsize=9,
        fontweight="bold",
        verticalalignment="top",
    )

    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label("Emergency Bias Weight ($W_{emerg}$)", color="#cbd5e1", fontsize=10)
    cbar.ax.tick_params(colors="#94a3b8")

    ax.set_xlabel("Extra Delay Imposed on Normal Traffic (seconds)", color="#cbd5e1", fontsize=11, labelpad=8)
    ax.set_ylabel("Ambulance Travel Time Saved (seconds)", color="#cbd5e1", fontsize=11, labelpad=8)
    ax.set_title("Preemption Trade-Off: Ambulance Time Saved vs Normal Delay\n(20 Evaluation Seeds, 240s Runs, Dispatch at Tick 120)", color="#f8fafc", fontsize=13, pad=12)
    ax.grid(True, linestyle=":", alpha=0.3, color="#475569")
    ax.tick_params(colors="#94a3b8")
    ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f1f5f9", loc="upper left")

    plt.tight_layout()
    chart_path = "results/preemption_tradeoff.png"
    plt.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Trade-off chart saved to {chart_path} and data to results/preemption_tradeoff.json")
    return tradeoff_results


if __name__ == "__main__":
    run_preemption_sweep()
