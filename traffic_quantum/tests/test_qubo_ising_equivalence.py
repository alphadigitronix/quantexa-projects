"""Test suite verifying mathematical equivalence between QUBO and Ising formulations across all 2^n bitstrings."""

import itertools
import pytest
import numpy as np
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder
from traffic_quantum.quantum.ising import QUBOToIsingConverter
from traffic_quantum.quantum.brute_force import BruteForceOptimizer


def test_qubo_ising_energy_equivalence_all_bitstrings():
    """Verify that Ising energy H(Z) identically equals QUBO cost x^T Q x + C0 for ALL 2^n bitstrings."""
    # Test on realistic QUBO generated from active simulation
    sim = TrafficSimulator(seed=101)
    for _ in range(30):
        sim.step()

    qubo_builder = TrafficQUBOBuilder(sim.network)
    Q, C0 = qubo_builder.build_qubo(sim)
    n = Q.shape[0]

    h, J, offset = QUBOToIsingConverter.qubo_to_ising(Q, C0)

    # Exhaustive evaluation across all 2^n bitstrings
    tested_count = 0
    for combo in itertools.product([0, 1], repeat=n):
        x = np.array(combo, dtype=np.float64)
        z = QUBOToIsingConverter.x_to_z(x)

        qubo_cost = TrafficQUBOBuilder.evaluate_qubo(Q, C0, x)
        ising_energy = QUBOToIsingConverter.evaluate_ising(h, J, offset, z)

        diff = abs(qubo_cost - ising_energy)
        assert diff < 1e-9, f"Mismatch on bitstring {combo}: QUBO={qubo_cost}, Ising={ising_energy}, diff={diff}"
        tested_count += 1

    assert tested_count == (2 ** n)


def test_qubo_ising_random_instances():
    """Verify equivalence on multiple arbitrary random symmetric and asymmetric Q matrices."""
    np.random.seed(42)
    for n in [4, 6]:
        Q = np.random.uniform(-10.0, 10.0, size=(n, n))
        C0 = float(np.random.uniform(-20.0, 20.0))

        h, J, offset = QUBOToIsingConverter.qubo_to_ising(Q, C0)

        for combo in itertools.product([0, 1], repeat=n):
            x = np.array(combo, dtype=np.float64)
            z = QUBOToIsingConverter.x_to_z(x)

            qubo_cost = float(x.T @ Q @ x + C0)
            ising_energy = QUBOToIsingConverter.evaluate_ising(h, J, offset, z)

            assert abs(qubo_cost - ising_energy) < 1e-9


def test_brute_force_solver_correctness():
    """Verify that brute-force solver identifies the exact global optimum."""
    Q = np.array([
        [5.0, -2.0],
        [-2.0, 3.0]
    ])
    C0 = 10.0
    # Possible x:
    # (0, 0) -> 10.0
    # (1, 0) -> 5 + 10 = 15.0
    # (0, 1) -> 3 + 10 = 13.0
    # (1, 1) -> 5 + 3 - 4 + 10 = 14.0
    best_x, min_cost, _ = BruteForceOptimizer.solve(Q, C0)
    assert np.array_equal(best_x, [0, 0])
    assert abs(min_cost - 10.0) < 1e-9
