"""Test suite for Hybrid Controller timing and phase persistence."""

import pytest
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def test_hybrid_phase_persistence_across_reopts():
    """Verify that a chosen phase persists across successive intervals as long as the optimizer keeps selecting it."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    controller = HybridController(network, solver_mode="brute_force")

    # Re-optimization interval is 10s
    reopt_interval = controller.config.hybrid.reopt_interval_sec
    assert reopt_interval == 10

    # Initial tick
    phases_t0 = controller.get_phases(0, sim)
    assert 0 in phases_t0

    # Between ticks 1 and 9, phases remain identical without re-invoking optimizer
    for t in range(1, reopt_interval):
        p = controller.get_phases(t, sim)
        assert p == phases_t0
        sim.step(p)
    assert len(controller.optimization_history) == 1

    # At tick 10, re-optimization triggers
    phases_t10 = controller.get_phases(10, sim)
    assert len(controller.optimization_history) == 2


def test_hybrid_controller_qaoa_execution_in_sim():
    """Verify end-to-end execution of HybridController with QAOA backend in simulation loop."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    controller = HybridController(network, solver_mode="qaoa")

    for tick in range(35):
        phases = controller.get_phases(tick, sim)
        sim.step(phases)

    assert len(controller.optimization_history) >= 1
    last_opt = controller.optimization_history[-1]
    assert last_opt["solver"] == "qaoa"
    assert "approximation_ratio" in last_opt
    assert "probabilities" in last_opt


def test_reopt_interval_governs_phase_switching():
    """Verify that reopt_interval_sec controls simulation re-optimization frequency.
    
    Verifies that while classical clamp() computes theoretical green extension durations,
    actual phase updates in the simulation loop occur at every reopt_interval_sec.
    """
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    controller = HybridController(network, solver_mode="brute_force")

    # Reopt interval is 10s
    reopt_interval = controller.config.hybrid.reopt_interval_sec
    assert reopt_interval == 10

    # Step through simulation and record optimization ticks
    opt_ticks = []
    for tick in range(35):
        phases = controller.get_phases(tick, sim)
        sim.step(phases)
        if controller.optimization_history and controller.optimization_history[-1]["tick"] == tick:
            if not opt_ticks or opt_ticks[-1] != tick:
                opt_ticks.append(tick)

    # Optimization must trigger at tick 0, 10, 20, 30
    assert opt_ticks == [0, 10, 20, 30]

