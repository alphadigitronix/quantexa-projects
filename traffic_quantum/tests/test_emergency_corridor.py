"""Test suite for Emergency Green Corridor (routing, bias application, and post-clearance cleanup)."""

import pytest
from traffic_quantum.config import DEFAULT_CONFIG
from traffic_quantum.controllers.fixed import FixedController
from traffic_quantum.controllers.rule_based import RuleBasedController
from traffic_quantum.controllers.hybrid import HybridController
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.network import RoadNetwork
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder
from traffic_quantum.simulator import TrafficSimulator


def test_emergency_routing_bypasses_closed_roads():
    """Verify that ambulance routing avoids closed road segments."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    manager = EmergencyCorridorManager(network)

    # Normal shortest path from 0 to 2 along top row: 0 -> 1 -> 2
    normal_mission = manager.dispatch_ambulance(origin=0, destination=2, simulator=sim, current_tick=0)
    assert normal_mission.path == [0, 1, 2]

    # Close road 1 -> 2
    network.set_edge_status(1, 2, "closed")
    detour_mission = manager.dispatch_ambulance(origin=0, destination=2, simulator=sim, current_tick=0)
    # Detour must bypass segment (1, 2)
    assert (1, 2) not in zip(detour_mission.path[:-1], detour_mission.path[1:])
    assert detour_mission.path[-1] == 2


def test_emergency_bias_application_and_removal():
    """Verify that emergency biases are applied to upcoming nodes and cleanly removed once cleared."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    manager = EmergencyCorridorManager(network)

    mission = manager.dispatch_ambulance(origin=0, destination=2, simulator=sim, current_tick=0)
    assert mission.path == [0, 1, 2]

    # At start, intersection 0 and upcoming intersections within ETA should have bias
    biases_t0 = manager.update_and_get_biases(current_tick=0, simulator=sim)
    assert 0 in biases_t0
    assert biases_t0[0] == "EW"  # Moving 0 -> 1 is Eastbound

    # Verify that QUBO incorporates this emergency bias heavily favoring EW (x_0 = 1)
    builder = TrafficQUBOBuilder(network)
    Q_biased, C0_biased = builder.build_qubo(sim, emergency_biases=biases_t0)
    Q_normal, C0_normal = builder.build_qubo(sim, emergency_biases=None)
    assert Q_biased[0, 0] != Q_normal[0, 0]

    # Advance until ambulance clears intersection 0 and 1
    # Edge travel time is ~12s / 1.5 = 8s
    for tick in range(1, 30):
        manager.update_and_get_biases(current_tick=tick, simulator=sim)

    # Mission should now be completed
    assert mission.completed is True
    biases_end = manager.update_and_get_biases(current_tick=35, simulator=sim)
    assert len(biases_end) == 0  # All biases completely removed!


def test_ambulance_travel_time_benchmark():
    """Measures ambulance travel time under Fixed, Rule-Based, and Hybrid controllers."""
    results = {}
    for ctrl_name, ctrl_cls in [
        ("Fixed", FixedController),
        ("Rule-Based", RuleBasedController),
        ("Hybrid-QAOA", lambda net: HybridController(net, solver_mode="brute_force")),
    ]:
        network = RoadNetwork()
        sim = TrafficSimulator(network=network, seed=42)
        controller = ctrl_cls(network)
        manager = EmergencyCorridorManager(network)

        # Dispatch at tick 10 from node 0 to 5
        mission = manager.dispatch_ambulance(origin=0, destination=5, simulator=sim, current_tick=10)

        for tick in range(120):
            biases = manager.update_and_get_biases(current_tick=tick, simulator=sim)
            if hasattr(controller, "get_phases") and "emergency_biases" in controller.get_phases.__code__.co_varnames:
                phases = controller.get_phases(tick, sim, emergency_biases=biases)
            else:
                phases = controller.get_phases(tick, sim)
            sim.step(phases)

        travel_time = (mission.arrival_tick - mission.dispatch_tick) if mission.arrival_tick else 999
        results[ctrl_name] = travel_time
        print(f"Ambulance Travel Time under {ctrl_name}: {travel_time}s")

    assert results["Hybrid-QAOA"] < 999


def test_ambulance_does_not_advance_before_dispatch_tick():
    """Verify that an ambulance mission does not advance or emit biases before its dispatch tick."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    manager = EmergencyCorridorManager(network)

    dispatch_tick = 120
    mission = manager.dispatch_ambulance(
        origin=0,
        destination=5,
        simulator=sim,
        current_tick=dispatch_tick,
    )
    assert mission.dispatch_tick == dispatch_tick
    assert mission.current_index == 0
    assert mission.current_edge_progress_sec == 0.0
    assert mission.completed is False
    assert mission.arrival_tick is None

    # Step simulation from tick 0 to 119
    for tick in range(dispatch_tick):
        biases = manager.update_and_get_biases(current_tick=tick, simulator=sim)
        sim.step({n: 0 for n in range(6)})
        # Must not emit biases before dispatch
        assert len(biases) == 0, f"Biases emitted at tick {tick} before dispatch {dispatch_tick}"
        # Must not advance or accumulate wait ticks
        assert mission.current_index == 0
        assert mission.current_edge_progress_sec == 0.0
        assert mission.waiting_ticks == 0
        assert mission.completed is False
        assert mission.arrival_tick is None

    # At dispatch tick (120), biases and movement should activate
    biases_dispatch = manager.update_and_get_biases(current_tick=dispatch_tick, simulator=sim)
    assert len(biases_dispatch) > 0, "Biases should be active at dispatch tick"
    assert 0 in biases_dispatch

