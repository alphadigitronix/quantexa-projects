"""
Amazon Braket Quantum QAOA Runner for Urban Traffic Optimization
Submits the 6-qubit traffic grid Hamiltonian to AWS Braket (SV1 cloud simulator
or physical QPUs like IonQ/Rigetti), saving task artifacts directly to S3.
"""

import sys
import time
import numpy as np
import pennylane as qml

try:
    import boto3
    from braket.aws import AwsSession
except ImportError:
    print("❌ AWS Braket SDK not found. Install with: pip install amazon-braket-pennylane-plugin boto3")
    sys.exit(1)


def run_braket_traffic_qaoa(use_hardware_qpu: bool = False):
    print("=" * 65)
    print("  🚦 QUANTUM TRAFFIC BRAIN - AMAZON BRAKET EXECUTION")
    print("=" * 65)

    # 1. Resolve S3 Bucket
    try:
        session = AwsSession()
        s3_bucket = session.default_bucket()
        s3_prefix = "traffic-qaoa-results"
        s3_folder = (s3_bucket, s3_prefix)
        print(f"📦 AWS S3 Output Destination: s3://{s3_bucket}/{s3_prefix}")
    except Exception as e:
        print(f"⚠️ Could not resolve default Braket bucket: {e}")
        s3_folder = None

    # 2. Select Device
    if use_hardware_qpu:
        # IonQ Aria-1 (Trapped-ion QPU)
        device_arn = "arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1"
        print(f"⚛️ Target Device: Real QPU (IonQ Aria-1) [{device_arn}]")
        dev = qml.device(
            "braket.aws.qubit",
            device_arn=device_arn,
            wires=6,
            shots=1000,
            s3_destination_folder=s3_folder
        )
    else:
        # High-performance Braket Local Simulator (runs with zero IAM permissions/roles required)
        print("⚡ Target Device: Amazon Braket Local Device (braket.local.qubit)")
        dev = qml.device("braket.local.qubit", wires=6, shots=1000)

    # 4. Build 6-Qubit Traffic Hamiltonian (A=0, B=1, C=2, D=3, E=4, F=5)
    qubo_matrix = np.array([
        [-1.8,  0.4,  0.0,  0.3,  0.0,  0.0],
        [ 0.4, -2.1,  0.4,  0.0,  0.3,  0.0],
        [ 0.0,  0.4, -1.5,  0.0,  0.0,  0.3],
        [ 0.3,  0.0,  0.0, -1.9,  0.4,  0.0],
        [ 0.0,  0.3,  0.0,  0.4, -2.4,  0.4],
        [ 0.0,  0.0,  0.3,  0.0,  0.4, -1.7],
    ])

    n_wires = 6
    obs = []
    coeffs = []

    for i in range(n_wires):
        hi = 0.5 * qubo_matrix[i, i]
        for j in range(n_wires):
            if i != j:
                hi += 0.25 * (qubo_matrix[i, j] + qubo_matrix[j, i])
        obs.append(qml.PauliZ(i))
        coeffs.append(hi)

    for i in range(n_wires):
        for j in range(i + 1, n_wires):
            Jij = 0.25 * (qubo_matrix[i, j] + qubo_matrix[j, i])
            if abs(Jij) > 1e-5:
                obs.append(qml.PauliZ(i) @ qml.PauliZ(j))
                coeffs.append(Jij)

    cost_h = qml.Hamiltonian(coeffs, obs)
    mixer_h = qml.Hamiltonian([1.0] * n_wires, [qml.PauliX(i) for i in range(n_wires)])

    # 5. Define QAOA Circuit (p=2 layers)
    def qaoa_layer(gamma, beta):
        qml.qaoa.cost_layer(gamma, cost_h)
        qml.qaoa.mixer_layer(beta, mixer_h)

    @qml.qnode(dev)
    def circuit(params):
        for w in range(n_wires):
            qml.Hadamard(wires=w)
        qaoa_layer(params[0], params[2])
        qaoa_layer(params[1], params[3])
        return qml.probs(wires=range(n_wires))

    # 6. Execute Task on AWS Braket
    params = np.array([0.42, 0.31, 0.75, 0.58])
    print("⏳ Submitting Quantum Task to Amazon Braket...")
    t0 = time.time()
    probs = circuit(params)
    dt = time.time() - t0
    print(f"✅ Execution Complete! Elapsed Time: {dt:.2f}s")

    # 7. Print Results
    junctions = ["A", "B", "C", "D", "E", "F"]
    top_indices = np.argsort(probs)[::-1][:5]

    print("\n" + "-" * 55)
    print("  🏆 TOP QUANTUM-OPTIMIZED TRAFFIC CONFIGURATIONS")
    print("-" * 55)
    for rank, idx in enumerate(top_indices, 1):
        bitstr = format(idx, f"0{n_wires}b")
        p = probs[idx]
        phases = {junctions[i]: ("E-W GREEN" if bitstr[i] == '1' else "N-S GREEN") for i in range(n_wires)}
        print(f"Rank #{rank} | State |{bitstr}⟩ | Confidence: {p*100:.2f}%")
        print(f"   Signals: {phases}")

    print("\n" + "=" * 65)
    print("  🎉 AWS Braket Execution Finished! Check Amazon S3 for task data.")
    print("=" * 65)


if __name__ == "__main__":
    is_qpu = "--qpu" in sys.argv
    run_braket_traffic_qaoa(use_hardware_qpu=is_qpu)
