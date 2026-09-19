"""Phase E.3: QAOA Noise Study on PennyLane default.mixed.

Evaluates how quantum depolarizing noise degrades the QAOA approximation ratio.
Simulates noisy hardware execution across 3 depolarizing error rates:
lambda in [0.005, 0.02, 0.05], comparing against ideal noiseless simulation.

Outputs results to results/qaoa_noise_study.png and results/qaoa_noise_data.json.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import matplotlib.pyplot as plt
import numpy as np
import pennylane as qml
from scipy.optimize import minimize

from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.network import RoadNetwork
from traffic_quantum.quantum.brute_force import BruteForceOptimizer
from traffic_quantum.quantum.ising import QUBOToIsingConverter
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder
from traffic_quantum.simulator import TrafficSimulator


def run_noise_study():
    """Evaluates depolarizing noise degradation on QAOA across 20 distinct traffic snapshots.
    
    Methodology:
    1. Variational parameters (gamma, beta) are trained via classical optimizer on the ideal Hamiltonian.
    2. The compiled circuit is evaluated on PennyLane's default.mixed density matrix simulator across
       depolarizing error rates lambda in [0.0, 0.005, 0.02, 0.05].
    3. Records expectation approximation ratio and top-state probability across 20 distinct network states.
    """
    print("=" * 80)
    print("QAOA DEPOLARIZING NOISE STUDY (20 Snapshots, default.mixed)")
    print("=" * 80)

    net = RoadNetwork()
    builder = TrafficQUBOBuilder(net)
    all_x = np.array([[(i >> b) & 1 for b in reversed(range(6))] for i in range(64)], dtype=np.int32)

    # 20 distinct traffic network snapshots
    snapshots = []
    for s in range(20):
        sim = TrafficSimulator(net, seed=s + 100)
        ticks = (s + 1) * 8
        for _ in range(ticks):
            sim.step({n: (s + n) % 2 for n in net.graph.nodes})
        Q, C0 = builder.build_qubo(sim)
        snapshots.append((Q, C0))

    noise_levels = [0.0, 0.005, 0.02, 0.05]
    labels = ["Ideal (Noiseless)", "Low (p=0.005)", "Medium (p=0.02)", "High (p=0.05)"]
    noise_data = {lbl: {"ratios": [], "top_probs": []} for lbl in labels}

    for snap_idx, (Q, C0) in enumerate(snapshots):
        h, J, _ = QUBOToIsingConverter.qubo_to_ising(Q, C0)
        costs = np.array([TrafficQUBOBuilder.evaluate_qubo(Q, C0, x) for x in all_x])
        min_c, max_c = float(np.min(costs)), float(np.max(costs))
        rng_c = max_c - min_c if max_c > min_c else 1.0

        # Step 1: Optimize angles on ideal simulator
        dev_ideal = qml.device("default.qubit", wires=6)

        @qml.qnode(dev_ideal)
        def ideal_circuit(g, b):
            for w in range(6):
                qml.Hadamard(wires=w)
            for l in range(2):
                for i in range(6):
                    if abs(h[i]) > 1e-6:
                        qml.RZ(2.0 * g[l] * h[i], wires=i)
                for i in range(6):
                    for j in range(i + 1, 6):
                        if abs(J[i, j]) > 1e-6:
                            qml.CNOT(wires=[i, j])
                            qml.RZ(2.0 * g[l] * J[i, j], wires=j)
                            qml.CNOT(wires=[i, j])
                for i in range(6):
                    qml.RX(2.0 * b[l], wires=i)
            return qml.probs(wires=range(6))

        def loss(params):
            pr = ideal_circuit(params[:2], params[2:])
            return float(np.dot(pr, costs))

        res = minimize(loss, [0.2, 0.3, 0.4, 0.2], method="COBYLA", options={"maxiter": 35})
        opt_g, opt_b = res.x[:2], res.x[2:]

        # Step 2: Evaluate on density matrix simulator under noise
        for noise, lbl in zip(noise_levels, labels):
            dev_m = qml.device("default.mixed" if noise > 0.0 else "default.qubit", wires=6)

            @qml.qnode(dev_m)
            def noisy_circuit():
                for w in range(6):
                    qml.Hadamard(wires=w)
                    if noise > 0.0:
                        qml.DepolarizingChannel(noise, wires=w)
                for l in range(2):
                    for i in range(6):
                        if abs(h[i]) > 1e-6:
                            qml.RZ(2.0 * opt_g[l] * h[i], wires=i)
                            if noise > 0.0:
                                qml.DepolarizingChannel(noise, wires=i)
                    for i in range(6):
                        for j in range(i + 1, 6):
                            if abs(J[i, j]) > 1e-6:
                                qml.CNOT(wires=[i, j])
                                qml.RZ(2.0 * opt_g[l] * J[i, j], wires=j)
                                qml.CNOT(wires=[i, j])
                                if noise > 0.0:
                                    qml.DepolarizingChannel(noise, wires=j)
                    for i in range(6):
                        qml.RX(2.0 * opt_b[l], wires=i)
                        if noise > 0.0:
                            qml.DepolarizingChannel(noise, wires=i)
                return qml.probs(wires=range(6))

            probs = np.array(noisy_circuit(), dtype=np.float64)
            exp_c = float(np.dot(probs, costs))
            exp_ratio = float((max_c - exp_c) / rng_c)
            noise_data[lbl]["ratios"].append(exp_ratio)
            noise_data[lbl]["top_probs"].append(float(np.max(probs)))

        sys.stdout.write(f"\rCompleted Snapshot [{snap_idx + 1}/20]")
        sys.stdout.flush()

    print("\n\nAll 20 snapshots completed. Summary Statistics:")
    summary_results = {}
    for noise, lbl in zip(noise_levels, labels):
        r_list = noise_data[lbl]["ratios"]
        p_list = noise_data[lbl]["top_probs"]
        m_r = float(np.mean(r_list))
        s_r = float(np.std(r_list))
        ci_r = 1.96 * s_r / np.sqrt(len(r_list))

        summary_results[lbl] = {
            "noise_rate": noise,
            "mean_ratio": round(m_r, 4),
            "std_ratio": round(s_r, 4),
            "ci_95": round(ci_r, 4),
            "ci_range": [round(m_r - ci_r, 4), round(m_r + ci_r, 4)],
            "mean_top_prob": round(float(np.mean(p_list)), 4),
            "n_snapshots": len(r_list),
        }
        print(f"  {lbl:<20}: Approx Ratio = {m_r:.4f} +/- {ci_r:.4f} (95% CI) | Top State Prob = {np.mean(p_list):.4f}")

    os.makedirs("results", exist_ok=True)
    with open("results/qaoa_noise_data.json", "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)

    # Plot figure
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#111827")

    x_indices = np.arange(len(noise_levels))
    means = [summary_results[l]["mean_ratio"] for l in labels]
    ci_errs = [summary_results[l]["ci_95"] for l in labels]
    bar_colors = ["#22c55e", "#38bdf8", "#f59e0b", "#ef4444"]

    bars = ax.bar(x_indices, means, yerr=ci_errs, capsize=6, color=bar_colors, alpha=0.85, edgecolor="white", linewidth=1.2, width=0.52)
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, m / 2, f"{m:.3f}", ha="center", va="center", color="white", fontweight="bold", fontsize=11)

    ax.set_xticks(x_indices)
    ax.set_xticklabels(labels, color="#cbd5e1", fontsize=10)
    ax.set_ylabel("Expectation Ratio $\\alpha_{exp}$", color="#cbd5e1", fontsize=11, labelpad=8)
    ax.set_ylim(0.0, 1.12)
    ax.grid(True, linestyle=":", alpha=0.3, color="#475569", axis="y")
    ax.tick_params(colors="#94a3b8")

    plt.title("QAOA Expectation Value Under Depolarizing Noise (PennyLane default.mixed)\np=2 Layers, 6 Qubits, 20 Snapshots (Mean & 95% Confidence Intervals)", color="#f8fafc", fontsize=10, pad=12)
    plt.tight_layout()
    chart_path = "results/qaoa_noise_study.png"
    plt.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Chart saved to {chart_path} and data to results/qaoa_noise_data.json.")
    return summary_results


if __name__ == "__main__":
    run_noise_study()

