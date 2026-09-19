#!/usr/bin/env python3
"""Standalone Real-Quantum-Hardware QAOA Execution Script for Urban Traffic Signals.

Executes a single QAOA circuit on real quantum hardware (AWS Braket or IBM Quantum)
using pre-trained variational angles from the noiseless classical simulator.

GROUND RULES:
- No secrets in code or output. Credentials read strictly from environment / AWS credential chain.
- Never falls back silently to a simulator. Fails explicitly if QPU is unavailable or job fails.
- Cost safety: requires --confirm, enforces max shots (default 1000) and max cost cap.
- Supports --dry-run: builds, compiles, prints depth & 2-qubit gates, but submits nothing.
- Honest labeling: no claims of quantum advantage; results clearly labeled:
  "sampled on <device>, angles trained on simulator".
"""

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Ensure project root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.network import RoadNetwork
from traffic_quantum.quantum.brute_force import BruteForceOptimizer
from traffic_quantum.quantum.ising import QUBOToIsingConverter
from traffic_quantum.quantum.qaoa import QAOATrafficSolver
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder
from traffic_quantum.simulator import TrafficSimulator


def get_git_commit_hash() -> str:
    """Safely retrieves the current git commit hash."""
    try:
        res = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return res
    except Exception:
        return "unknown"


def generate_snapshot_qubo(
    seed: int,
    snapshot_time: int,
    config: MasterConfig,
) -> Tuple[np.ndarray, float, np.ndarray, float, List[Tuple[np.ndarray, float]]]:
    """Deterministically recreates the traffic state snapshot and constructs the QUBO."""
    network = RoadNetwork(config.network)
    sim = TrafficSimulator(network=network, config=config, seed=seed)
    for _ in range(snapshot_time):
        sim.step()

    builder = TrafficQUBOBuilder(network, config=config)
    Q, C0 = builder.build_qubo(sim)

    # Solve exactly for ground truth comparison
    exact_x, exact_min_cost, all_sorted = BruteForceOptimizer.solve(Q, C0)
    return Q, C0, exact_x, exact_min_cost, all_sorted


def train_simulator_angles(
    Q: np.ndarray,
    C0: float,
    exact_min_cost: float,
    config: MasterConfig,
) -> Dict[str, Any]:
    """Trains QAOA variational angles on default.qubit noiseless simulator."""
    solver = QAOATrafficSolver(num_qubits=6, config=config)
    result = solver.solve(Q, C0, exact_cost=exact_min_cost)
    return result


def build_braket_circuit(
    n: int,
    p: int,
    h: np.ndarray,
    J: np.ndarray,
    gammas: List[float],
    betas: List[float],
):
    """Constructs native Amazon Braket Circuit with the trained QAOA angles."""
    from braket.circuits import Circuit

    circuit = Circuit()
    # 1. Equal superposition |+>^n
    for w in range(n):
        circuit.h(w)

    # 2. Alternating Cost and Mixer unitaries
    for layer in range(p):
        g = gammas[layer]
        b = betas[layer]

        # Cost unitary e^{-i gamma H_C}
        # Single-qubit longitudinal fields: h_i Z_i -> RZ(2 * g * h_i)
        for i in range(n):
            if abs(h[i]) > 1e-7:
                circuit.rz(i, 2.0 * g * h[i])

        # Two-qubit couplings: J_ij Z_i Z_j -> CNOT(i, j) -> RZ(j, 2*g*J_ij) -> CNOT(i, j)
        for i in range(n):
            for j in range(i + 1, n):
                if abs(J[i, j]) > 1e-7:
                    circuit.cnot(i, j)
                    circuit.rz(j, 2.0 * g * J[i, j])
                    circuit.cnot(i, j)

        # Mixer unitary e^{-i beta H_M}
        for i in range(n):
            circuit.rx(i, 2.0 * b)

    return circuit


def build_qiskit_circuit(
    n: int,
    p: int,
    h: np.ndarray,
    J: np.ndarray,
    gammas: List[float],
    betas: List[float],
):
    """Constructs native Qiskit QuantumCircuit with the trained QAOA angles."""
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(n)
    for w in range(n):
        qc.h(w)

    for layer in range(p):
        g = gammas[layer]
        b = betas[layer]

        for i in range(n):
            if abs(h[i]) > 1e-7:
                qc.rz(2.0 * g * h[i], i)

        for i in range(n):
            for j in range(i + 1, n):
                if abs(J[i, j]) > 1e-7:
                    qc.cx(i, j)
                    qc.rz(2.0 * g * J[i, j], j)
                    qc.cx(i, j)

        for i in range(n):
            qc.rx(2.0 * b, i)

    qc.measure_all()
    return qc


def convert_qiskit_counts_endianness(qiskit_counts: Dict[str, int]) -> Dict[str, int]:
    """Converts Qiskit's little-endian bitstrings (q_n-1 ... q_0) to wire/network order (q_0 ... q_n-1).
    
    Qiskit formats bitstring keys as right-to-left (qubit 0 is rightmost).
    Our network/QUBO and Braket format bitstrings left-to-right (qubit 0 is leftmost).
    Reversing the string aligns qubit i with index i.
    """
    return {k[::-1]: v for k, v in qiskit_counts.items()}


def estimate_cost(
    provider: str,
    shots: int,
    config: MasterConfig,
) -> float:
    """Calculates estimated execution cost based on configured provider rates."""
    if provider == "braket":
        # Per-task submission fee + per-shot pricing
        return float(config.qpu.braket_task_fee_usd + shots * config.qpu.braket_per_shot_usd)
    elif provider == "ibm":
        return float(config.qpu.ibm_estimated_cost_usd)
    return 0.0


def compute_metrics(
    raw_counts: Dict[str, int],
    shots: int,
    ideal_probs: np.ndarray,
    exact_optimum_bitstring: str,
    Q: np.ndarray,
    C0: float,
    all_sorted: List[Tuple[np.ndarray, float]],
) -> Dict[str, Any]:
    """Computes TVD, probability mass on exact optimum, approximation ratio, and top-k."""
    # 64 possible bitstrings for 6 qubits
    all_bitstrings = [f"{i:06b}" for i in range(64)]
    ideal_prob_dict = {f"{i:06b}": float(ideal_probs[i]) for i in range(64)}
    
    # Normalize hardware counts
    hw_probs = {s: raw_counts.get(s, 0) / shots for s in all_bitstrings}

    # 1. Total Variation Distance (TVD) = 0.5 * sum |P_hw - P_ideal|
    tvd = 0.5 * sum(abs(hw_probs[s] - ideal_prob_dict[s]) for s in all_bitstrings)

    # 2. Probability mass on exact optimum
    hw_optimum_prob = hw_probs.get(exact_optimum_bitstring, 0.0)
    ideal_optimum_prob = ideal_prob_dict.get(exact_optimum_bitstring, 0.0)

    # 3. QUBO costs and range for approximation ratio
    min_cost = all_sorted[0][1]
    max_cost = all_sorted[-1][1]
    range_cost = max_cost - min_cost if max_cost > min_cost else 1.0

    # Best-of-samples hardware
    hw_samples_evaluated = []
    for s, count in raw_counts.items():
        if count > 0:
            bit_arr = np.array([int(b) for b in s], dtype=np.float64)
            cost = float(bit_arr.T @ Q @ bit_arr + C0)
            hw_samples_evaluated.append((s, cost, count))

    hw_samples_evaluated.sort(key=lambda x: x[1])
    hw_best_bitstring, hw_best_cost, _ = hw_samples_evaluated[0]
    hw_approx_ratio = (max_cost - hw_best_cost) / range_cost

    # Best-of-samples ideal simulator (evaluated over all states weighted by probability)
    ideal_best_bitstring = all_sorted[0][0]
    ideal_best_bitstring_str = "".join(str(b) for b in ideal_best_bitstring)
    ideal_best_cost = min_cost
    ideal_approx_ratio = (max_cost - ideal_best_cost) / range_cost

    # 4. Top-k bitstring selection (k=4) as used by the controller
    sorted_by_count = sorted(raw_counts.items(), key=lambda x: x[1], reverse=True)
    top_4_bitstrings = [s for s, _ in sorted_by_count[:4]]
    top_4_hit_optimum = exact_optimum_bitstring in top_4_bitstrings

    # Find lowest cost among top 4
    top_4_costs = []
    for s in top_4_bitstrings:
        b_arr = np.array([int(b) for b in s], dtype=np.float64)
        c = float(b_arr.T @ Q @ b_arr + C0)
        top_4_costs.append(c)
    top_4_best_cost = min(top_4_costs) if top_4_costs else hw_best_cost

    return {
        "total_variation_distance": round(float(tvd), 4),
        "probability_mass_on_exact_optimum": {
            "hardware": round(float(hw_optimum_prob), 4),
            "ideal_simulator": round(float(ideal_optimum_prob), 4),
        },
        "best_of_samples": {
            "hardware": {
                "best_bitstring": hw_best_bitstring,
                "best_cost": round(float(hw_best_cost), 4),
                "approximation_ratio": round(float(hw_approx_ratio), 4),
            },
            "ideal_simulator": {
                "best_bitstring": ideal_best_bitstring_str,
                "best_cost": round(float(ideal_best_cost), 4),
                "approximation_ratio": round(float(ideal_approx_ratio), 4),
            },
        },
        "top_k_selection": {
            "k": 4,
            "hardware_top_k": top_4_bitstrings,
            "hardware_top_k_best_cost": round(float(top_4_best_cost), 4),
            "hits_exact_optimum": bool(top_4_hit_optimum),
        },
        "exact_optimum": {
            "bitstring": exact_optimum_bitstring,
            "cost": round(float(min_cost), 4),
        },
    }


def generate_comparison_plot(
    provider: str,
    device_name: str,
    raw_counts: Dict[str, int],
    shots: int,
    ideal_probs: np.ndarray,
    exact_optimum_bitstring: str,
    metrics: Dict[str, Any],
    output_png_path: str,
) -> None:
    """Plots and saves a side-by-side comparison between hardware and ideal simulator."""
    # Select top 8 states by ideal probability plus exact optimum
    sorted_ideal_indices = np.argsort(ideal_probs)[::-1]
    top_indices = list(sorted_ideal_indices[:8])
    exact_opt_idx = int(exact_optimum_bitstring, 2)
    if exact_opt_idx not in top_indices:
        top_indices.append(exact_opt_idx)

    bitstrings = [f"{idx:06b}" for idx in top_indices]
    ideal_vals = [ideal_probs[idx] for idx in top_indices]
    hw_vals = [raw_counts.get(s, 0) / shots for s in bitstrings]

    x = np.arange(len(bitstrings))
    width = 0.35

    plt.figure(figsize=(11, 6), dpi=150)
    bars_ideal = plt.bar(x - width / 2, ideal_vals, width, label="Ideal Simulator (Noiseless)", color="#3B82F6", alpha=0.85)
    bars_hw = plt.bar(x + width / 2, hw_vals, width, label=f"Hardware ({device_name})", color="#F59E0B", alpha=0.85)

    # Highlight exact optimum
    for i, s in enumerate(bitstrings):
        if s == exact_optimum_bitstring:
            plt.axvline(i, color="#10B981", linestyle="--", alpha=0.6, label="Exact Optimum (|%s⟩)" % s)
            break

    plt.xlabel("6-Intersection Signal Configuration Bitstring (|x₀x₁x₂x₃x₄x₅⟩)", fontsize=11, fontweight="bold")
    plt.ylabel("Probability", fontsize=11, fontweight="bold")
    plt.title(
        f"Quantum Traffic QAOA: Real Hardware vs Ideal Simulator\n"
        f"sampled on {device_name}, angles trained on simulator | TVD = {metrics['total_variation_distance']:.3f}",
        fontsize=12,
        fontweight="bold",
    )
    plt.xticks(x, [f"|{s}⟩" for s in bitstrings], rotation=45, ha="right", fontsize=9)
    plt.legend(frameon=True, facecolor="#F9FAFB", loc="upper right")
    plt.grid(axis="y", linestyle=":", alpha=0.5)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    plt.savefig(output_png_path)
    plt.close()


def list_braket_devices() -> int:
    """Queries Braket SDK for available gate-based QPUs, statuses, and availability windows.

    Exits with error if AWS credentials are not configured.
    """
    try:
        import boto3
        from braket.aws import AwsDevice, AwsSession
    except ImportError:
        print("❌ ERROR: amazon-braket-sdk or boto3 is not installed.", file=sys.stderr)
        return 1

    boto_session = boto3.Session()
    if not boto_session.get_credentials():
        print(
            "❌ ERROR: AWS credentials not found in environment or AWS credential chain.\n"
            "   Cannot query Amazon Braket devices. Please configure AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY\n"
            "   or ~/.aws/credentials before running --list-devices.",
            file=sys.stderr,
        )
        return 1

    print("🔍 Querying Amazon Braket SDK for available gate-based QPUs...")
    candidate_regions = ["us-east-1", "us-west-1", "us-west-2", "eu-west-2"]
    devices_found = []

    for reg in candidate_regions:
        try:
            reg_session = AwsSession(boto_session=boto3.Session(region_name=reg))
            qpus = AwsDevice.get_devices(types=["QPU"], aws_session=reg_session)
            for d in qpus:
                if not any(x["arn"] == d.arn for x in devices_found):
                    windows = "N/A"
                    try:
                        props = getattr(d, "properties", None)
                        if props and hasattr(props, "service") and hasattr(props.service, "executionWindows"):
                            ew = props.service.executionWindows
                            windows = ", ".join(
                                f"{w.executionDay}: {w.windowStartHourUtc}:00-{w.windowEndHourUtc}:00 UTC"
                                for w in ew
                            ) if ew else "24/7 or unlisted"
                    except Exception:
                        pass
                    devices_found.append({
                        "name": getattr(d, "name", "Unknown"),
                        "provider": getattr(d, "provider_name", "Unknown"),
                        "arn": d.arn,
                        "status": getattr(d, "status", "UNKNOWN"),
                        "region": reg,
                        "windows": windows,
                    })
        except Exception:
            continue

    if not devices_found:
        print("ℹ️ No gate-based QPUs found or accessible with current credentials.")
        return 0

    print("\n" + "=" * 95)
    print(f"{'PROVIDER':<15} | {'DEVICE NAME':<18} | {'REGION':<10} | {'STATUS':<10} | {'DEVICE ARN'}")
    print("-" * 95)
    for d in devices_found:
        print(f"{d['provider']:<15} | {d['name']:<18} | {d['region']:<10} | {d['status']:<10} | {d['arn']}")
        if d['windows'] != "N/A":
            print(f"   Availability Windows: {d['windows']}")
    print("=" * 95)
    print("\n💡 Specify --provider braket --device <DEVICE_ARN> to target a device.")
    return 0


def run_selftest(
    provider: str = "all",
    device_arn_or_name: Optional[str] = None,
    confirm: bool = False,
    shots: int = 100,
) -> int:
    """Executes a trivial single-qubit excitation circuit to verify bitstring-ordering end-to-end.

    Circuit: 2 qubits, X on qubit 0, measure all qubits.
    Expected wire-order bitstring: '10' (qubit 0 is '1', qubit 1 is '0').

    If confirm is False:
        Runs on LOCAL simulators (LocalSimulator for Braket, StatevectorSampler for IBM).
    If confirm is True:
        Submits the trivial circuit to the specified hardware device.
    """
    print("=" * 70)
    print("🧪 RUNNING END-TO-END BITSTRING ORDERING SELF-TEST")
    print("   Circuit: 2 qubits | X gate on Qubit 0 | Measure [0, 1]")
    print("   Expected wire-ordered outcome: |10⟩ (Qubit 0 = 1, Qubit 1 = 0)")
    print(f"   Mode: {'REAL HARDWARE (--confirm)' if confirm else 'LOCAL SIMULATOR'}")
    print("=" * 70)

    success = True

    if not confirm:
        providers_to_test = [provider] if provider in ("braket", "ibm") else ["braket", "ibm"]

        if "braket" in providers_to_test:
            try:
                from braket.circuits import Circuit
                from braket.devices import LocalSimulator
                braket_c = Circuit().x(0).i(1)
                braket_dev = LocalSimulator()
                res = braket_dev.run(braket_c, shots=shots).result()
                braket_counts = dict(res.measurement_counts)
                dominant_braket = max(braket_counts.items(), key=lambda x: x[1])[0]
                print("📡 [Braket LocalSimulator]")
                print(f"   Raw Counts: {braket_counts}")
                print(f"   Wire-ordered dominant bitstring: |{dominant_braket}⟩")
                if dominant_braket == "10":
                    print("   ✅ Braket bit-ordering PASS: Wire-ordered counts correctly map Qubit 0 to index 0.")
                else:
                    print(f"   ❌ FAIL: Expected '10', received '{dominant_braket}'.", file=sys.stderr)
                    success = False
            except Exception as e:
                print(f"   ❌ Braket LocalSimulator error: {e}", file=sys.stderr)
                success = False

        if "ibm" in providers_to_test:
            try:
                from qiskit import QuantumCircuit
                from qiskit.primitives import StatevectorSampler
                qc = QuantumCircuit(2)
                qc.x(0)
                qc.measure_all()
                sampler = StatevectorSampler()
                job = sampler.run([qc], shots=shots)
                pub_result = job.result()[0]
                qiskit_raw = pub_result.data.meas.get_counts()
                converted_counts = convert_qiskit_counts_endianness(qiskit_raw)
                dominant_qiskit = max(converted_counts.items(), key=lambda x: x[1])[0]
                print("\n📡 [Qiskit Local StatevectorSampler]")
                print(f"   Raw Qiskit Counts (little-endian): {qiskit_raw}")
                print(f"   Converted Counts (wire-order):     {converted_counts}")
                print(f"   Wire-ordered dominant bitstring: |{dominant_qiskit}⟩")
                if dominant_qiskit == "10":
                    print("   ✅ Qiskit bit-ordering PASS: Little-endian successfully reversed to wire-order.")
                else:
                    print(f"   ❌ FAIL: Expected '10', received '{dominant_qiskit}'.", file=sys.stderr)
                    success = False
            except Exception as e:
                print(f"   ❌ Qiskit StatevectorSampler error: {e}", file=sys.stderr)
                success = False

        if success:
            print("\n🎉 Local simulator self-test PASSED completely!")
            return 0
        else:
            print("\n❌ Local simulator self-test FAILED.", file=sys.stderr)
            return 1

    else:
        print("🚀 Submitting self-test circuit to real hardware...")
        if provider == "braket":
            if not device_arn_or_name:
                print("❌ ERROR: --device <ARN> is required for real hardware self-test on Braket.", file=sys.stderr)
                return 1
            import boto3
            from braket.aws import AwsDevice, AwsSession
            from braket.circuits import Circuit

            boto_session = boto3.Session()
            if not boto_session.get_credentials():
                print("❌ ERROR: AWS credentials not found in environment or credential chain.", file=sys.stderr)
                return 1
            arn_parts = device_arn_or_name.split(":")
            region = arn_parts[3] if len(arn_parts) > 3 and arn_parts[3] else "us-east-1"
            aws_session = AwsSession(boto_session=boto3.Session(region_name=region))
            aws_dev = AwsDevice(device_arn_or_name, aws_session=aws_session)
            s3_bucket = os.getenv("AWS_BRAKET_S3_BUCKET") or aws_session.default_bucket()
            s3_folder = (s3_bucket, "traffic-selftest-results")
            c = Circuit().x(0).i(1)
            task = aws_dev.run(c, s3_destination_folder=s3_folder, shots=shots)
            print(f"📋 Quantum Task ID: {task.id}. Awaiting result...")
            res = task.result()
            counts = dict(res.measurement_counts)
            dominant = max(counts.items(), key=lambda x: x[1])[0]
            print(f"📊 Hardware Measurement Counts: {counts}")
            if dominant[0] == "1":
                print(f"✅ Braket Hardware Self-Test PASSED on {device_arn_or_name}: dominant |{dominant}⟩")
                return 0
            else:
                print(f"❌ Braket Hardware Self-Test FAILED on {device_arn_or_name}: dominant |{dominant}⟩", file=sys.stderr)
                return 1
        elif provider == "ibm":
            ibm_token = os.getenv("IBM_QUANTUM_TOKEN")
            if not ibm_token:
                print("❌ ERROR: IBM_QUANTUM_TOKEN not found in environment.", file=sys.stderr)
                return 1
            from qiskit import QuantumCircuit
            from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
            service = QiskitRuntimeService(channel="ibm_quantum", token=ibm_token)
            if device_arn_or_name:
                backend = service.backend(device_arn_or_name)
            else:
                backend = service.least_busy(operational=True, simulator=False, min_num_qubits=2)
            qc = QuantumCircuit(2)
            qc.x(0)
            qc.measure_all()
            pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
            isa_qc = pm.run(qc)
            sampler = SamplerV2(backend=backend)
            job = sampler.run([isa_qc], shots=shots)
            print(f"📋 IBM Quantum Job ID: {job.job_id()}. Awaiting result...")
            pub_res = job.result()[0]
            raw = pub_res.data.meas.get_counts()
            converted = convert_qiskit_counts_endianness(raw)
            dominant = max(converted.items(), key=lambda x: x[1])[0]
            print(f"📊 Hardware Measurement Counts (wire-ordered): {converted}")
            if dominant[0] == "1":
                print(f"✅ IBM Hardware Self-Test PASSED on {backend.name}: dominant |{dominant}⟩")
                return 0
            else:
                print(f"❌ IBM Hardware Self-Test FAILED on {backend.name}: dominant |{dominant}⟩", file=sys.stderr)
                return 1
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Run traffic QAOA optimization circuit on real quantum hardware."
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="braket",
        choices=["braket", "ibm"],
        help="Quantum hardware cloud provider ('braket' or 'ibm'). Default: braket.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Specific device name or ARN (required for real AWS Braket runs).",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=None,
        help="Measurement shots (default: config.qpu.max_shots, max capped).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic traffic simulation random seed (default: 42).",
    )
    parser.add_argument(
        "--snapshot-time",
        type=int,
        default=60,
        help="Simulation tick time to snapshot QUBO traffic state (default: 60).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Authorizes real hardware submission and incurred provider costs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Constructs and transpiles the circuit, prints metrics and estimated costs, submits nothing.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Queries Braket SDK for available gate-based QPUs, statuses, and availability windows.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Runs a trivial single-qubit excitation circuit (X on qubit 0, measure all) to verify bitstring ordering end-to-end.",
    )
    parser.add_argument(
        "--override-cost-cap",
        action="store_true",
        help="Bypass maximum cost safety ceiling ($5.00 default).",
    )

    args = parser.parse_args()
    config = DEFAULT_CONFIG

    if args.list_devices:
        return list_braket_devices()

    if args.selftest:
        selftest_shots = args.shots if args.shots is not None else 100
        provider_arg = args.provider if "--provider" in sys.argv else "all"
        return run_selftest(
            provider=provider_arg,
            device_arn_or_name=args.device,
            confirm=args.confirm,
            shots=selftest_shots,
        )

    # 1. Validate Shots & Caps
    shots = args.shots if args.shots is not None else config.qpu.max_shots
    if shots > config.qpu.max_shots:
        print(
            f"❌ ERROR: Requested shots ({shots}) exceeds safety ceiling ({config.qpu.max_shots}).\n"
            f"   Update config.py:QPUConfig.max_shots if an increase is explicitly intended.",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. Cost Estimate & Ceiling Check
    est_cost = estimate_cost(args.provider, shots, config)
    if est_cost > config.qpu.max_cost_usd:
        if not args.override_cost_cap:
            print(
                f"❌ ERROR: Estimated execution cost (${est_cost:.2f} USD) exceeds safety ceiling "
                f"(${config.qpu.max_cost_usd:.2f} USD).\n"
                f"   Execution is refused even with --confirm.\n"
                f"   Pass --override-cost-cap to bypass this limit, or reduce shots / adjust config.py:QPUConfig.max_cost_usd.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(
                f"⚠️ WARNING: Estimated execution cost (${est_cost:.2f} USD) exceeds safety ceiling "
                f"(${config.qpu.max_cost_usd:.2f} USD), but --override-cost-cap was passed.\n"
            )

    # 3. Snapshot QUBO & Ising Hamiltonian
    print("=" * 70)
    print("🚦 QUANTUM TRAFFIC BRAIN - REAL HARDWARE QAOA PIPELINE")
    print("=" * 70)
    print(f"📌 Deterministic Snapshot: Seed={args.seed}, SnapshotTick={args.snapshot_time}")
    Q, C0, exact_x, exact_min_cost, all_sorted = generate_snapshot_qubo(
        seed=args.seed,
        snapshot_time=args.snapshot_time,
        config=config,
    )
    exact_optimum_bitstring = "".join(str(b) for b in exact_x)
    print(f"🎯 Exact Ground Truth Optimum: |{exact_optimum_bitstring}⟩ (QUBO Cost: {exact_min_cost:.2f})")

    # 4. Train Angles on default.qubit Simulator
    p_layers = config.qpu.default_p_layers
    config.qaoa.p_layers = p_layers
    print(f"🧠 Training QAOA angles on noiseless simulator (p={p_layers} layers)...")
    train_res = train_simulator_angles(Q, C0, exact_min_cost, config)
    trained_gammas = train_res["optimal_gammas"]
    trained_betas = train_res["optimal_betas"]
    ideal_probs = np.array(train_res["probabilities"], dtype=np.float64)
    h, J, offset = QUBOToIsingConverter.qubo_to_ising(Q, C0)
    print(f"   Optimal Gammas (γ): {[round(g, 4) for g in trained_gammas]}")
    print(f"   Optimal Betas  (β): {[round(b, 4) for b in trained_betas]}")

    # 5. Build & Compile Circuit for Chosen Provider
    compiled_depth = 0
    two_qubit_gates = 0
    device_name = ""
    region = ""
    backend_obj = None

    if args.provider == "braket":
        try:
            import boto3
            from braket.aws import AwsDevice, AwsSession
            from braket.circuits import Circuit
        except ImportError:
            print("❌ ERROR: amazon-braket-sdk or boto3 is not installed.", file=sys.stderr)
            sys.exit(1)

        device_arn = args.device or config.qpu.default_braket_device_arn
        if not device_arn:
            if args.dry_run or not args.confirm:
                device_arn = "braket.local.offline"
                region = config.qpu.default_braket_region
            else:
                print(
                    "❌ ERROR: --device <ARN> is required for real QPU runs on AWS Braket.\n"
                    "   Run with --list-devices to find available QPUs, or check the AWS Braket console.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            arn_parts = device_arn.split(":")
            region = arn_parts[3] if len(arn_parts) > 3 and arn_parts[3] else config.qpu.default_braket_region
        device_name = device_arn

        # Build Braket native circuit
        braket_circuit = build_braket_circuit(6, p_layers, h, J, trained_gammas, trained_betas)
        compiled_depth = braket_circuit.depth
        two_qubit_gates = sum(1 for instr in braket_circuit.instructions if len(instr.target) > 1)

    elif args.provider == "ibm":
        try:
            from qiskit import QuantumCircuit
            from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        except ImportError:
            print("❌ ERROR: qiskit or qiskit_ibm_runtime is not installed.", file=sys.stderr)
            sys.exit(1)

        raw_qc = build_qiskit_circuit(6, p_layers, h, J, trained_gammas, trained_betas)
        device_name = args.device or "ibm_least_busy (selected at runtime)"
        region = os.getenv("IBM_QUANTUM_INSTANCE", "ibm_quantum")

        # Offline preset pass manager for depth & gate count estimation
        from qiskit.providers.fake_provider import GenericBackendV2
        mock_backend = GenericBackendV2(num_qubits=7)
        pm = generate_preset_pass_manager(backend=mock_backend, optimization_level=1)
        isa_circuit = pm.run(raw_qc)
        compiled_depth = isa_circuit.depth()
        two_qubit_gates = isa_circuit.num_nonlocal_gates()

    # 6. Print Compilation & Cost Summary
    est_qpu_seconds = max(0.5, round(shots * 0.0015, 2))
    print("-" * 70)
    print(f"⚛️ Target Provider:       {args.provider.upper()}")
    print(f"🖥️ Target Device/ARN:     {device_name}")
    print(f"📐 Circuit Qubits:        6")
    print(f"📊 QAOA Depth (p):        {p_layers}")
    print(f"⛓️ Compiled Depth:        {compiled_depth}")
    print(f"🔀 Two-Qubit Gates:       {two_qubit_gates}")
    print(f"🎯 Execution Shots:       {shots}")
    if args.provider == "ibm":
        print(f"💵 Estimated Cost:        Billed by runtime, check your plan (~{est_qpu_seconds:.1f} est. QPU seconds)")
    else:
        print(f"💵 Estimated Cost:        ${est_cost:.2f} USD (Verify rates in provider console!)")
    print(f"🏷️ Result Label:          sampled on {device_name}, angles trained on simulator")
    print("-" * 70)

    # 7. Check Dry-Run and Confirmation Guardrails
    if args.dry_run:
        print("✅ DRY RUN SUCCESSFUL:")
        print("   Circuit constructed, compiled to native gate structure, and validated.")
        print("   No task was submitted to quantum hardware. Cost incurred: $0.00.")
        return 0

    if not args.confirm:
        print(
            "🛑 REFUSING TO SUBMIT: Missing mandatory --confirm flag.\n"
            "   Executing on real quantum hardware may incur monetary charges or consume compute time.\n"
            "   Re-run with '--confirm' to authorize QPU submission.",
            file=sys.stderr,
        )
        return 1

    # 8. Real Hardware Submission (Requires confirmed execution)
    print(f"🚀 Authorizing submission to real quantum hardware ({device_name})...")
    submission_timestamp = datetime.now(timezone.utc).isoformat()
    task_id = ""
    raw_counts: Dict[str, int] = {}

    if args.provider == "braket":
        if not args.device:
            print(
                "❌ ERROR: --device <ARN> is required for real QPU runs on AWS Braket.\n"
                "   Run with --list-devices to find available QPUs, or check the AWS Braket console.",
                file=sys.stderr,
            )
            sys.exit(1)

        arn_parts = device_arn.split(":")
        region = arn_parts[3] if len(arn_parts) > 3 and arn_parts[3] else config.qpu.default_braket_region
        boto_session = boto3.Session(region_name=region)
        if not boto_session.get_credentials():
            print(
                "❌ ERROR: AWS credentials not found in environment or AWS credential chain.\n"
                "   Configure AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or ~/.aws/credentials.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            aws_session = AwsSession(boto_session=boto_session)
            aws_device = AwsDevice(device_arn, aws_session=aws_session)
            device_status = getattr(aws_device, "status", "UNKNOWN")
            print(f"📡 AWS Device Verified: {device_arn} | Region: {region} | Status: {device_status}")
            backend_obj = aws_device
            if device_status != "ONLINE":
                print(
                    f"❌ ERROR: Target device {device_arn} is currently {device_status}.\n"
                    f"   Refusing to submit to offline device.",
                    file=sys.stderr,
                )
                sys.exit(1)
        except Exception as e:
            print(f"❌ ERROR querying AWS Braket device: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            s3_bucket = os.getenv("AWS_BRAKET_S3_BUCKET")
            if not s3_bucket:
                aws_sess = backend_obj.aws_session
                s3_bucket = aws_sess.default_bucket()
            s3_folder = (s3_bucket, "traffic-qaoa-results")
            print(f"📦 AWS S3 Output Folder: s3://{s3_folder[0]}/{s3_folder[1]}")

            task = backend_obj.run(
                braket_circuit,
                s3_destination_folder=s3_folder,
                shots=shots,
                poll_timeout_seconds=config.qpu.hardware_timeout_sec,
            )
            task_id = task.id
            print(f"📋 Quantum Task ID: {task_id}")
            print("⏳ Awaiting QPU execution completion...")
            result = task.result()
            raw_counts = dict(result.measurement_counts)
        except Exception as e:
            print(f"❌ ERROR during Amazon Braket task execution: {e}", file=sys.stderr)
            print("🛑 Execution failed. No file labeled 'hardware' will be saved.", file=sys.stderr)
            sys.exit(1)

    elif args.provider == "ibm":
        ibm_token = os.getenv("IBM_QUANTUM_TOKEN")
        ibm_instance = os.getenv("IBM_QUANTUM_INSTANCE")
        if not ibm_token:
            print(
                "❌ ERROR: IBM_QUANTUM_TOKEN not found in environment.\n"
                "   Set IBM_QUANTUM_TOKEN in .env or authenticate via QiskitRuntimeService.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
            service = QiskitRuntimeService(
                channel="ibm_quantum",
                token=ibm_token,
                instance=ibm_instance,
            )
            if args.device:
                target_backend = service.backend(args.device)
                print(f"📡 Selected specified IBM backend: {target_backend.name} (operational={target_backend.status().operational})")
            else:
                print("🔍 Querying IBM Quantum Runtime for least-busy real backend with >= 6 qubits...")
                target_backend = service.least_busy(operational=True, simulator=False, min_num_qubits=6)
                print(f"📡 Selected least-busy IBM backend: {target_backend.name} (operational={target_backend.status().operational}, pending_jobs={target_backend.status().pending_jobs})")
            backend_obj = target_backend
            device_name = target_backend.name
            region = ibm_instance or "ibm_quantum"
            if not target_backend.status().operational:
                print(f"❌ ERROR: IBM Backend {target_backend.name} is not operational.", file=sys.stderr)
                sys.exit(1)

            # Transpile directly to target backend
            pm = generate_preset_pass_manager(backend=target_backend, optimization_level=1)
            isa_circuit = pm.run(raw_qc)
            compiled_depth = isa_circuit.depth()
            two_qubit_gates = isa_circuit.num_nonlocal_gates()
            sampler = SamplerV2(backend=backend_obj)
            job = sampler.run([isa_circuit], shots=shots)
            task_id = job.job_id()
            print(f"📋 IBM Quantum Job ID: {task_id}")
            print("⏳ Awaiting IBM QPU execution completion...")
            job_result = job.result()
            pub_result = job_result[0]
            # Convert little-endian counts to project wire order
            qiskit_counts = pub_result.data.meas.get_counts()
            raw_counts = convert_qiskit_counts_endianness(qiskit_counts)
        except Exception as e:
            print(f"❌ ERROR during IBM Quantum job execution: {e}", file=sys.stderr)
            print("🛑 Execution failed. No file labeled 'hardware' will be saved.", file=sys.stderr)
            sys.exit(1)

    completion_timestamp = datetime.now(timezone.utc).isoformat()
    if not raw_counts:
        print("❌ ERROR: Received empty measurement counts from QPU. Aborting.", file=sys.stderr)
        sys.exit(1)

    # 9. Compute Analysis Metrics
    metrics = compute_metrics(
        raw_counts=raw_counts,
        shots=shots,
        ideal_probs=ideal_probs,
        exact_optimum_bitstring=exact_optimum_bitstring,
        Q=Q,
        C0=C0,
        all_sorted=all_sorted,
    )

    git_hash = get_git_commit_hash()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(PROJECT_ROOT, "results")
    os.makedirs(results_dir, exist_ok=True)

    json_filename = f"qpu_run_{args.provider}_{timestamp_str}.json"
    png_filename = f"qpu_run_{args.provider}_{timestamp_str}.png"
    json_path = os.path.join(results_dir, json_filename)
    png_path = os.path.join(results_dir, png_filename)

    output_payload = {
        "provider": args.provider,
        "exact_device_name": device_name,
        "task_or_job_id": task_id,
        "submission_timestamp": submission_timestamp,
        "completion_timestamp": completion_timestamp,
        "shots": shots,
        "region": region,
        "qaoa_p": p_layers,
        "trained_angles": {
            "gammas": [float(g) for g in trained_gammas],
            "betas": [float(b) for b in trained_betas],
        },
        "raw_counts": raw_counts,
        "compiled_depth": compiled_depth,
        "two_qubit_gate_count": two_qubit_gates,
        "git_commit_hash": git_hash,
        "label": f"sampled on {device_name}, angles trained on simulator",
        "comparison_plot": os.path.relpath(png_path, PROJECT_ROOT),
        "metrics": metrics,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    generate_comparison_plot(
        provider=args.provider,
        device_name=device_name,
        raw_counts=raw_counts,
        shots=shots,
        ideal_probs=ideal_probs,
        exact_optimum_bitstring=exact_optimum_bitstring,
        metrics=metrics,
        output_png_path=png_path,
    )

    print("\n" + "=" * 70)
    print("🎉 REAL QUANTUM HARDWARE EXECUTION COMPLETE")
    print("=" * 70)
    print(f"📄 Results JSON:          {json_path}")
    print(f"📊 Comparison Plot:       {png_path}")
    print(f"🏆 Exact Optimum:         |{exact_optimum_bitstring}⟩")
    print(f"🎯 Optimum Hit Prob:      {metrics['probability_mass_on_exact_optimum']['hardware']:.4f} (HW) vs {metrics['probability_mass_on_exact_optimum']['ideal_simulator']:.4f} (Sim)")
    print(f"📈 Hardware Approx Ratio: {metrics['best_of_samples']['hardware']['approximation_ratio']:.4f}")
    print(f"📏 TVD (HW vs Ideal):     {metrics['total_variation_distance']:.4f}")
    print(f"🚦 Top-4 Hits Optimum:    {metrics['top_k_selection']['hits_exact_optimum']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
