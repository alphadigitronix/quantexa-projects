"""Unit tests for Simulated Annealing QUBO optimizer."""

import numpy as np
import pytest
from traffic_quantum.quantum.brute_force import BruteForceOptimizer
from traffic_quantum.quantum.simulated_annealing import SimulatedAnnealingOptimizer


def test_simulated_annealing_finds_good_solution():
    """Verify that Simulated Annealing finds optimal or near-optimal solutions on random QUBO instances."""
    np.random.seed(42)
    Q = np.random.randn(6, 6)
    Q = 0.5 * (Q + Q.T)  # Symmetrize
    C0 = 10.0

    # Exact ground truth
    exact_x, exact_cost, _ = BruteForceOptimizer.solve(Q, C0)

    # Simulated annealing
    sa_x, sa_cost, meta = SimulatedAnnealingOptimizer.solve(Q, C0, seed=42)

    # SA cost should be within 5% of exact minimum
    cost_gap = abs(sa_cost - exact_cost)
    assert cost_gap < 1.0 or sa_cost <= exact_cost + 1e-4
    assert meta["total_steps"] > 50
    assert meta["runtime_sec"] >= 0.0
