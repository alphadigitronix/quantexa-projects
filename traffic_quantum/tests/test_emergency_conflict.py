"""Unit tests for Multi-Emergency Conflict Handling and Priority Arbitration."""

import pytest
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.emergency import EmergencyCorridorManager


def test_emergency_conflict_resolution_by_priority():
    """Verify that two conflicting ambulances at a shared junction resolve by priority deterministically."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    manager = EmergencyCorridorManager(network)

    # Ambulance 1: Path 0 -> 1 -> 2 (moving EW at junction 1)
    # Priority 2 (High: Code Red)
    amb1 = manager.dispatch_ambulance(
        origin=0, destination=2, simulator=sim, current_tick=0, priority=2
    )

    # Ambulance 2: Path 1 -> 4 (moving NS at junction 1)
    # Priority 1 (Standard: Code Yellow)
    amb2 = manager.dispatch_ambulance(
        origin=1, destination=4, simulator=sim, current_tick=0, priority=1
    )

    # Both ambulances approach junction 1 with conflicting required phases (EW vs NS)
    biases = manager.update_and_get_biases(current_tick=0, simulator=sim)

    # Junction 1 must resolve to Ambulance 1 ("EW") because priority 2 > priority 1
    assert 1 in biases
    assert biases[1] == "EW"
    assert len(manager.conflict_resolution_log) >= 1

    conflict = manager.conflict_resolution_log[0]
    assert conflict["node"] == 1
    assert conflict["winner_priority"] == 2
    assert conflict["loser_priority"] == 1
    assert conflict["winner_dir"] == "EW"


def test_conflict_clearing_and_sequential_passage():
    """Verify that once the winning ambulance passes, the secondary ambulance acquires the corridor, and both clear."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    manager = EmergencyCorridorManager(network)

    # Amb 1: 0 -> 1 -> 2 (EW at 1), priority 2
    amb1 = manager.dispatch_ambulance(origin=0, destination=2, simulator=sim, current_tick=0, priority=2)
    # Amb 2: 4 -> 1 -> 0 (NS at 1), priority 1
    amb2 = manager.dispatch_ambulance(origin=4, destination=0, simulator=sim, current_tick=0, priority=1)

    # Run for 40 ticks
    for tick in range(40):
        biases = manager.update_and_get_biases(current_tick=tick, simulator=sim)

    # Both missions should eventually complete
    assert amb1.completed is True
    assert amb2.completed is True

    # After both have cleared the network, all emergency biases must be removed
    final_biases = manager.update_and_get_biases(current_tick=50, simulator=sim)
    assert len(final_biases) == 0
