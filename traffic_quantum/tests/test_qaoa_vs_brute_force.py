"""Test suite comparing manual PennyLane QAOA against exact brute-force solutions."""

import pytest
import numpy as np
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.quantum.ising import QUBOToIsingConverter
from traffic_quantum.quantum.brute_force import BruteForceOptimizer
from traffic_quantum.quantum.qaoa import QAOATrafficSolver


def test_qaoa_circuit_probabilities_sum_to_one():
    """Verify that manual QAOA circuit creates a normalized quantum state (probabilities sum to 1.0)."""
    n = 4
    solver = QAOATrafficSolver(num_qubits=n)
    
    # Simple test QUBO
    Q = np.array([
        [2.0, -1.0, 0.0, 0.0],
        [-1.0, 3.0, -1.0, 0.0],
        [0.0, -1.0, 2.0, -1.0],
        [0.0, 0.0, -1.0, 4.0],
    ])
    C0 = 5.0
    
    exact_x, exact_cost, _ = BruteForceOptimizer.solve(Q, C0)
    res = solver.solve(Q, C0, exact_cost=exact_cost)
    
    probs = res["probabilities"]
    assert len(probs) == (2 ** n)
    assert abs(np.sum(probs) - 1.0) < 1e-5
    assert res["best_cost"] >= exact_cost - 1e-5
    assert res["approximation_ratio"] >= 0.70


def test_qaoa_vs_brute_force_on_traffic_instance():
    """Test QAOA optimization on a 6-qubit instance against brute-force exact optimum."""
    n = 6
    solver = QAOATrafficSolver(num_qubits=n)

    # Realistic symmetric traffic QUBO
    np.random.seed(42)
    A = np.random.uniform(-3.0, 4.0, size=(n, n))
    Q = (A + A.T) / 2.0
    C0 = 12.0

    exact_x, exact_cost, _ = BruteForceOptimizer.solve(Q, C0)
    res = solver.solve(Q, C0, exact_cost=exact_cost)

    print(f"\nExact Cost: {exact_cost:.3f}, QAOA Best Cost: {res['best_cost']:.3f}")
    print(f"Approximation Ratio: {res['approximation_ratio']:.4f}, Found Exact: {res['found_exact_optimum']}")

    assert res["approximation_ratio"] >= 0.75
    assert len(res["best_bitstring"]) == n


def test_qaoa_warm_start_caching():
    """Verify that warm-start parameter caching stores parameters across consecutive rounds."""
    n = 4
    solver = QAOATrafficSolver(num_qubits=n)
    solver.reset_cache()
    assert solver.warm_start_params is None

    Q1 = np.eye(n) * 2.0
    solver.solve(Q1, 0.0)
    assert solver.warm_start_params is not None
    cached_first = solver.warm_start_params.copy()

    # Next round with slight perturbation uses cached angles
    Q2 = Q1 + np.eye(n) * 0.1
    solver.solve(Q2, 0.0)
    assert solver.warm_start_params is not None
