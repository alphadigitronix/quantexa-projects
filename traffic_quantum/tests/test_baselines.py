"""Test suite for baseline traffic signal controllers (Fixed vs Rule-Based)."""

import pytest
import pandas as pd
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def run_controller_simulation(controller, seed: int = 42, duration: int = 240):
    """Executes a simulation with the given controller and extracts key metrics."""
    network = RoadNetwork(DEFAULT_CONFIG.network)
    sim = TrafficSimulator(network=network, config=DEFAULT_CONFIG, seed=seed)
    controller.reset()

    for tick in range(duration):
        phases = controller.get_phases(tick, sim)
        sim.step(phases)

    avg_wait = sim.get_average_wait_time()
    throughput = len(sim.completed_vehicles)
    
    # Average queue length across all ticks and all intersections
    all_queue_counts = [
        sum(tick_queues.values()) for tick_queues in sim.queue_length_history
    ]
    avg_queue = sum(all_queue_counts) / len(all_queue_counts) if all_queue_counts else 0.0

    return {
        "controller": controller.name,
        "avg_wait_sec": round(avg_wait, 2),
        "throughput_cars": throughput,
        "avg_queue_cars": round(avg_queue, 2),
    }


def test_baseline_controllers_comparison():
    """Runs Fixed, Rule-Based, and Hybrid controllers on identical seeded scenario and prints comparison table."""
    seed = 42
    duration = 240
    network = RoadNetwork(DEFAULT_CONFIG.network)

    fixed_ctrl = FixedController(network)
    rule_ctrl = RuleBasedController(network)
    hybrid_ctrl = HybridController(network, solver_mode="brute_force")

    res_fixed = run_controller_simulation(fixed_ctrl, seed=seed, duration=duration)
    res_rule = run_controller_simulation(rule_ctrl, seed=seed, duration=duration)
    res_hybrid = run_controller_simulation(hybrid_ctrl, seed=seed, duration=duration)

    df = pd.DataFrame([res_fixed, res_rule, res_hybrid])
    print("\n--- CONTROLLERS BENCHMARK TABLE (FIXED vs RULE-BASED vs HYBRID) ---")
    print(df.to_string(index=False))
    print("-------------------------------------------------------------------")

    assert res_fixed["throughput_cars"] > 0
    assert res_rule["throughput_cars"] > 0
    assert res_hybrid["throughput_cars"] > 0
    # Confirm hybrid controller matches or beats the fixed baseline
    assert res_hybrid["avg_wait_sec"] <= res_fixed["avg_wait_sec"]

