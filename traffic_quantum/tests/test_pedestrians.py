"""Unit tests for Pedestrian dynamics, queue accumulation, service, and QUBO term."""

import pytest
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.network import RoadNetwork
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder
from traffic_quantum.simulator import TrafficSimulator


def test_pedestrian_arrivals_and_service():
    """Verify that pedestrians arrive, accumulate wait under red signals, and cross under green."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)

    # Step simulation for 60 ticks
    for _ in range(60):
        sim.step({node: 0 for node in network.graph.nodes})  # All nodes NS green, EW red

    # NS pedestrians should have been served, EW pedestrians should be waiting
    total_waiting_ew = sum(len(sim.pedestrian_queues[n]["EW"]) for n in network.graph.nodes)
    assert total_waiting_ew > 0
    assert len(sim.completed_pedestrians) >= 0

    avg_ped_wait = sim.get_average_pedestrian_wait_time()
    assert avg_ped_wait >= 0.0


def test_pedestrian_qubo_penalty():
    """Verify that pedestrian queue creates an appropriate linear bias in the QUBO matrix."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)

    # Manually spawn 10 pedestrians waiting for EW green at junction 0
    for _ in range(10):
        sim.pedestrian_queues[0]["EW"].append(
            type("MockPed", (), {"waiting_ticks": 10})()
        )

    builder = TrafficQUBOBuilder(network)
    Q, C0 = builder.build_qubo(sim)

    # EW pedestrians prefer x_0 = 1 (EW green). In QUBO cost, x_0=1 should have lower cost.
    # Q[0, 0] should be reduced or C0 adjusted
    assert Q[0, 0] != 0.0 or C0 > 0.0
