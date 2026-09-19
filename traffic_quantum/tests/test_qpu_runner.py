"""Unit tests for Real-Quantum-Hardware runner (scripts/run_on_qpu.py).

All tests run completely offline without requiring active network, AWS credentials,
or IBM Quantum tokens.
"""

import json
import subprocess
import sys
import numpy as np
import pytest

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig, QPUConfig
from scripts.run_on_qpu import (
    convert_qiskit_counts_endianness,
    estimate_cost,
    compute_metrics,
    build_braket_circuit,
    build_qiskit_circuit,
)


def test_bit_order_endianness_conversion():
    """Verifies that Qiskit's little-endian bitstrings are correctly converted to wire order."""
    # Suppose qubit 0 is |1> and qubit 1 is |0>.
    # In Qiskit little-endian notation: bitstring key is "01" (qubit 1, qubit 0).
    # In wire/network notation (qubit 0, qubit 1): bitstring key must be "10".
    raw_qiskit = {"01": 100, "10": 20, "00": 5}
    converted = convert_qiskit_counts_endianness(raw_qiskit)
    
    assert "10" in converted
    assert converted["10"] == 100  # former "01" where qubit 0 was 1
    assert "01" in converted
    assert converted["01"] == 20   # former "10" where qubit 1 was 1
    assert converted["00"] == 5

    # 6-qubit test: state where only qubit 0 is 1:
    # Qiskit: "000001" (rightmost is qubit 0)
    # Wire order: "100000" (leftmost is qubit 0)
    six_qubit_qiskit = {"000001": 500}
    six_qubit_converted = convert_qiskit_counts_endianness(six_qubit_qiskit)
    assert "100000" in six_qubit_converted
    assert six_qubit_converted["100000"] == 500


def test_cost_cap_enforcement():
    """Verifies that cost estimation accurately computes costs and triggers cap."""
    cfg = MasterConfig()
    cfg.qpu.braket_task_fee_usd = 0.30
    cfg.qpu.braket_per_shot_usd = 0.03
    cfg.qpu.max_cost_usd = 10.0

    # 1000 shots on Braket = 0.30 + 1000 * 0.03 = $30.30 > $10.00
    cost = estimate_cost("braket", 1000, cfg)
    assert cost == pytest.approx(30.30, rel=1e-3)
    assert cost > cfg.qpu.max_cost_usd

    # With 100 shots = 0.30 + 100 * 0.03 = $3.30 <= $10.00
    cost_small = estimate_cost("braket", 100, cfg)
    assert cost_small == pytest.approx(3.30, rel=1e-3)
    assert cost_small <= cfg.qpu.max_cost_usd


def test_cli_refusal_without_confirm():
    """Verifies that the runner CLI explicitly refuses to submit when --confirm is omitted."""
    cmd = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--provider", "braket",
        "--shots", "100",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    # Must exit with non-zero code and emit refusal message
    assert proc.returncode != 0
    assert "REFUSING TO SUBMIT" in proc.stderr or "REFUSING TO SUBMIT" in proc.stdout
    assert "--confirm" in proc.stderr or "--confirm" in proc.stdout


def test_cli_shots_safety_cap():
    """Verifies that the runner CLI blocks runs exceeding config.qpu.max_shots."""
    cmd = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--provider", "braket",
        "--shots", "5000",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode != 0
    assert "exceeds safety ceiling" in proc.stderr or "exceeds safety ceiling" in proc.stdout


def test_cli_dry_run_produces_no_submission():
    """Verifies that --dry-run completes successfully without submitting any hardware tasks."""
    cmd = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--provider", "braket",
        "--shots", "100",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0
    assert "DRY RUN SUCCESSFUL" in proc.stdout
    assert "No task was submitted to quantum hardware" in proc.stdout


def test_cli_cost_cap_and_override():
    """Verifies that cost cap blocks excessive cost and --override-cost-cap allows it."""
    # 1000 shots on Braket is $30.30 > $5.00 default cap
    cmd_fail = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--provider", "braket",
        "--dry-run",
    ]
    proc_fail = subprocess.run(cmd_fail, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc_fail.returncode != 0
    assert "exceeds safety ceiling" in proc_fail.stderr or "exceeds safety ceiling" in proc_fail.stdout

    cmd_pass = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--provider", "braket",
        "--override-cost-cap",
        "--dry-run",
    ]
    proc_pass = subprocess.run(cmd_pass, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc_pass.returncode == 0
    assert "DRY RUN SUCCESSFUL" in proc_pass.stdout


def test_cli_selftest_end_to_end():
    """Verifies that --selftest runs trivial circuit on local simulator and verifies bit ordering."""
    cmd = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--selftest",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0
    assert "Braket bit-ordering PASS" in proc.stdout
    assert "Qiskit bit-ordering PASS" in proc.stdout
    assert "PASSED completely!" in proc.stdout


def test_cli_list_devices_stops_on_missing_credentials():
    """Verifies that --list-devices stops cleanly with error if AWS credentials are not configured."""
    cmd = [
        sys.executable,
        "scripts/run_on_qpu.py",
        "--list-devices",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode != 0
    assert "AWS credentials not found" in proc.stderr or "AWS credentials not found" in proc.stdout


def test_dashboard_hardware_audit_fields_validation():
    """Verifies that hardware JSON files missing mandatory audit fields are rejected."""
    from dashboard import REQUIRED_HARDWARE_FIELDS

    expected_fields = {"provider", "exact_device_name", "task_or_job_id", "submission_timestamp", "region", "shots"}
    assert expected_fields.issubset(set(REQUIRED_HARDWARE_FIELDS))

    # Test rejection logic: payload missing 'task_or_job_id' and 'region'
    sample_bad_payload = {
        "provider": "braket",
        "exact_device_name": "test-device",
        "submission_timestamp": "2026-09-19T00:00:00Z",
        "shots": 100,
    }
    missing = [f for f in REQUIRED_HARDWARE_FIELDS if not sample_bad_payload.get(f)]
    assert "task_or_job_id" in missing
    assert "region" in missing


def test_metrics_and_json_schema():
    """Verifies that compute_metrics produces the exact expected structure and valid values."""
    # Create synthetic counts for 6 qubits
    all_bitstrings = [f"{i:06b}" for i in range(64)]
    raw_counts = {s: 10 for s in all_bitstrings}
    raw_counts["101111"] = 150  # Give elevated counts to optimum
    shots = sum(raw_counts.values())

    # Uniform ideal probabilities
    ideal_probs = np.full(64, 1.0 / 64)

    # Simple diagonal QUBO
    Q = np.diag([-1.0, 2.0, -3.0, 1.0, -2.0, 1.0])
    C0 = 5.0
    all_sorted = [(np.array([1, 0, 1, 0, 1, 0]), 0.0), (np.array([0, 0, 0, 0, 0, 0]), 10.0)]

    metrics = compute_metrics(
        raw_counts=raw_counts,
        shots=shots,
        ideal_probs=ideal_probs,
        exact_optimum_bitstring="101111",
        Q=Q,
        C0=C0,
        all_sorted=all_sorted,
    )

    # Schema validation
    assert "total_variation_distance" in metrics
    assert 0.0 <= metrics["total_variation_distance"] <= 1.0

    assert "probability_mass_on_exact_optimum" in metrics
    assert "hardware" in metrics["probability_mass_on_exact_optimum"]
    assert "ideal_simulator" in metrics["probability_mass_on_exact_optimum"]
    assert metrics["probability_mass_on_exact_optimum"]["hardware"] > 0.1

    assert "best_of_samples" in metrics
    assert "hardware" in metrics["best_of_samples"]
    assert "ideal_simulator" in metrics["best_of_samples"]

    assert "top_k_selection" in metrics
    assert metrics["top_k_selection"]["k"] == 4
    assert len(metrics["top_k_selection"]["hardware_top_k"]) == 4
    assert metrics["top_k_selection"]["hits_exact_optimum"] is True
