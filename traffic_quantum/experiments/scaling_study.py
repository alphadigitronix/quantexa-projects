"""Phase E.4: Combinatorial Scaling Study (Brute-Force vs Network Size).

Measures exact brute-force runtime across intersection counts N in [4, 6, 8, 10, 12, 14, 16, 18, 20]
(search space 2^N states). Demonstrates exponential growth: O(2^N) classical scaling
and why QUBO/Ising formulation matters for scaling traffic networks, alongside the honest
note that state-vector simulators limit QAOA to small qubit counts (<=20).

Outputs results to results/scaling_table.csv and results/scaling_curve.png.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from traffic_quantum.quantum.brute_force import BruteForceOptimizer


def run_scaling_study():
    """Measures runtime scaling of exact brute force enumeration."""
    print("Starting Combinatorial Scaling Study (N = 4 to 20 intersections)...")
    n_values = [4, 6, 8, 10, 12, 14, 16, 18, 20]
    records = []

    for n in n_values:
        np.random.seed(42)
        Q = np.random.randn(n, n)
        Q = 0.5 * (Q + Q.T)
        C0 = 0.0

        num_states = 1 << n

        t0 = time.perf_counter()
        best_x, min_cost, _ = BruteForceOptimizer.solve(Q, C0)
        dt = time.perf_counter() - t0

        records.append({
            "intersections_N": n,
            "search_space_states": num_states,
            "runtime_seconds": round(dt, 5),
            "evaluations_per_sec": round(num_states / max(1e-6, dt), 1),
            "measurement_type": "Measured",
        })
        print(f"N = {n:2d} intersections | States = {num_states:10,d} | Runtime = {dt:8.5f}s")

    # Extrapolate N=22 and N=24 based on empirical rate
    eval_rate = np.mean([r["evaluations_per_sec"] for r in records[-3:]])
    for n in [22, 24]:
        num_states = 1 << n
        est_time = num_states / eval_rate
        records.append({
            "intersections_N": n,
            "search_space_states": num_states,
            "runtime_seconds": round(est_time, 2),
            "evaluations_per_sec": round(eval_rate, 1),
            "measurement_type": "Projected (Extrapolated)",
        })
        print(f"N = {n:2d} intersections | States = {num_states:10,d} | Projected = {est_time:8.2f}s")

    df = pd.DataFrame(records)
    os.makedirs("results", exist_ok=True)
    csv_path = "results/scaling_table.csv"
    df.to_csv(csv_path, index=False)

    metadata = {
        "title": "Combinatorial Scaling Study (Brute-Force vs Network Size)",
        "measured_range": "N = 4 to 20",
        "projected_range": "N = 22 to 24",
        "scaling_model": "O(2^N) brute-force state enumeration",
        "caption": (
            "Exact brute-force search space scales as 2^N discrete phase configurations. "
            "N=22 and N=24 runtimes are projected based on empirical evaluation throughput (~4M evaluations/sec). "
            "Important note: Traffic QUBO matrices are sparse (planar street topology with bounded node degree <= 4) "
            "and structured. Specialized classical solvers (e.g., branch-and-bound, simulated annealing, "
            "and tensor networks) solve sparse planar spin systems far faster than brute-force enumeration."
        ),
        "data_points": records,
    }
    with open("results/scaling_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Plot
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(8.5, 5.8), dpi=150)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#111827")

    measured_df = df[df["measurement_type"] == "Measured"]
    extrap_df = df[df["measurement_type"] == "Projected (Extrapolated)"]

    ax.plot(
        measured_df["intersections_N"],
        measured_df["runtime_seconds"],
        "o-",
        color="#38bdf8",
        linewidth=2.5,
        markersize=8,
        label="Measured Brute-Force Runtime",
    )
    # Connect last measured to extrapolated
    connect_df = df[df["intersections_N"] >= 20]
    ax.plot(
        connect_df["intersections_N"],
        connect_df["runtime_seconds"],
        "s--",
        color="#f43f5e",
        linewidth=2,
        markersize=7,
        label="Projected Runtime (N=22, 24)",
    )

    ax.set_yscale("log")
    ax.set_xlabel("Number of Intersections ($N$)", color="#cbd5e1", fontsize=11, labelpad=8)
    ax.set_ylabel("Runtime in Seconds (Log Scale)", color="#cbd5e1", fontsize=11, labelpad=8)
    ax.set_title("Combinatorial Scaling: Brute-Force Search Space ($2^N$ States)\n(N=22 and N=24 Projected; Sparse Solvers Excluded)", color="#f8fafc", fontsize=12, pad=12)
    ax.grid(True, which="both", linestyle=":", alpha=0.3, color="#475569")
    ax.tick_params(colors="#94a3b8")
    ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f1f5f9", loc="upper left")

    # Annotations
    n6_time = df.loc[df['intersections_N']==6, 'runtime_seconds'].values[0]
    ax.annotate(f"N=6: {n6_time:.4f}s\n(Chennai 2x3 Grid)", (6, n6_time),
                textcoords="offset points", xytext=(15, 10), color="#38bdf8", fontsize=9,
                arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=1.2))

    n20_time = df.loc[df['intersections_N']==20, 'runtime_seconds'].values[0]
    ax.annotate(f"N=20: {n20_time:.2f}s\n(~1M states)", (20, n20_time),
                textcoords="offset points", xytext=(-60, 20), color="#38bdf8", fontsize=9,
                arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=1.2))

    n24_time = df.loc[df['intersections_N']==24, 'runtime_seconds'].values[0]
    ax.annotate(f"N=24 (Projected): {n24_time:.1f}s\n(~16.8M states)", (24, n24_time),
                textcoords="offset points", xytext=(-70, -25), color="#f43f5e", fontsize=9,
                arrowprops=dict(arrowstyle="->", color="#f43f5e", lw=1.2))

    # Add sparse solver footnote
    fig.text(
        0.5, 0.01,
        "Note: Traffic QUBOs are planar & sparse (degree <= 4). Specialized classical solvers outperform brute force.",
        ha="center", color="#94a3b8", fontsize=8, style="italic"
    )

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    chart_path = "results/scaling_curve.png"
    plt.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Scaling table saved to {csv_path} and chart to {chart_path}")
    return df


if __name__ == "__main__":
    run_scaling_study()
