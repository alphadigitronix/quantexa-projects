"""Phase E.2: QAOA Depth Study (Approximation Ratio vs Circuit Depth p).

Evaluates QAOA circuit depths p in [1, 2, 3, 4] across 20 distinct traffic network
snapshots, recording:
- Approximation ratio mean and standard deviation
- Ground-truth exact optimum hit frequency
Outputs chart to results/qaoa_depth_vs_ratio.png and JSON data.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import matplotlib.pyplot as plt
import numpy as np

from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.network import RoadNetwork
from traffic_quantum.quantum.brute_force import BruteForceOptimizer
from traffic_quantum.quantum.qaoa import QAOATrafficSolver
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder
from traffic_quantum.simulator import TrafficSimulator


def generate_traffic_snapshots(count: int = 20) -> list:
    """Generates diverse traffic state QUBO matrices from simulation runs."""
    snapshots = []
    network = RoadNetwork()
    builder = TrafficQUBOBuilder(network)

    for s in range(count):
        sim = TrafficSimulator(network=network, seed=s + 10)
        # Advance random ticks
        ticks = (s + 1) * 15
        for _ in range(ticks):
            sim.step({n: (s + n) % 2 for n in network.graph.nodes})
        Q, C0 = builder.build_qubo(sim)
        exact_x, exact_cost, _ = BruteForceOptimizer.solve(Q, C0)
        snapshots.append((Q, C0, exact_cost))
    return snapshots


def run_depth_study():
    """Runs QAOA for depths p=1, 2, 3, 4 across 20 snapshots."""
    print("Generating 20 traffic network snapshots for QAOA depth study...")
    snapshots = generate_traffic_snapshots(20)

    p_values = [1, 2, 3, 4]
    results_by_p = {p: {"ratios": [], "exact_hits": 0} for p in p_values}

    for p in p_values:
        print(f"Evaluating QAOA at depth p = {p} across 20 snapshots...")
        cfg = DEFAULT_CONFIG
        cfg.qaoa.p_layers = p
        # Proportional budget: 2p variational parameters require scaled optimizer steps
        cfg.qaoa.max_iterations = 20 + 20 * p
        solver = QAOATrafficSolver(num_qubits=6, config=cfg)

        for Q, C0, exact_cost in snapshots:
            solver.reset_cache()
            res = solver.solve(Q, C0, exact_cost=exact_cost)
            ratio = res["approximation_ratio"]
            hit = res["found_exact_optimum"]
            results_by_p[p]["ratios"].append(ratio)
            if hit:
                results_by_p[p]["exact_hits"] += 1

    summary = {}
    for p in p_values:
        arr = results_by_p[p]["ratios"]
        m_r = float(np.mean(arr))
        s_r = float(np.std(arr))
        ci_r = 1.96 * s_r / np.sqrt(len(arr))
        summary[str(p)] = {
            "p": p,
            "max_iterations": 20 + 20 * p,
            "mean_ratio": round(m_r, 4),
            "std_ratio": round(s_r, 4),
            "ci_95": round(ci_r, 4),
            "exact_hit_rate": round(results_by_p[p]["exact_hits"] / len(arr), 3),
        }
        print(f"p = {p}: Mean Approx Ratio = {m_r:.4f} +/- {ci_r:.4f} (95% CI) "
              f"| Exact Hit Rate: {summary[str(p)]['exact_hit_rate']*100:.1f}%")

    os.makedirs("results", exist_ok=True)
    with open("results/qaoa_depth_data.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Plot
    plt.style.use("dark_background")
    fig, ax1 = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor("#0b0f19")
    ax1.set_facecolor("#111827")

    means = [summary[str(p)]["mean_ratio"] for p in p_values]
    stds = [summary[str(p)]["std_ratio"] for p in p_values]
    hit_rates = [summary[str(p)]["exact_hit_rate"] * 100 for p in p_values]

    line1 = ax1.errorbar(
        p_values,
        means,
        yerr=stds,
        fmt="o-",
        color="#38bdf8",
        ecolor="#0284c7",
        elinewidth=2,
        capsize=5,
        capthick=2,
        markersize=8,
        linewidth=2.5,
        label="Mean Approx Ratio",
    )
    ax1.set_xlabel("QAOA Circuit Depth ($p$)", color="#cbd5e1", fontsize=11, labelpad=8)
    ax1.set_ylabel("Approximation Ratio $\\alpha$", color="#38bdf8", fontsize=11, labelpad=8)
    ax1.set_xticks(p_values)
    ax1.tick_params(axis="y", labelcolor="#38bdf8")
    ax1.tick_params(axis="x", labelcolor="#94a3b8")
    ax1.set_ylim(0.70, 1.05)
    ax1.grid(True, linestyle=":", alpha=0.3, color="#475569")

    # Twin axis for hit rate
    ax2 = ax1.twinx()
    line2 = ax2.plot(
        p_values,
        hit_rates,
        "s--",
        color="#a855f7",
        linewidth=2,
        markersize=7,
        label="Exact Optimum Hit Rate (%)",
    )
    ax2.set_ylabel("Exact Optimum Hit Rate (%)", color="#a855f7", fontsize=11, labelpad=8)
    ax2.tick_params(axis="y", labelcolor="#a855f7")
    ax2.set_ylim(0, 110)

    lines = [line1, line2[0]]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="lower right", facecolor="#1e293b", edgecolor="#334155", labelcolor="#f1f5f9")

    plt.title("QAOA Convergence vs Circuit Depth ($p=1..4$)\nEvaluated on 20 Traffic State Snapshots", color="#f8fafc", fontsize=12, pad=12)
    plt.tight_layout()
    chart_path = "results/qaoa_depth_vs_ratio.png"
    plt.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Chart saved to {chart_path} and data to results/qaoa_depth_data.json")
    return summary


if __name__ == "__main__":
    run_depth_study()
