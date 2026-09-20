"""Integration test verifying ambulance dispatch and preemption in the dashboard pipeline."""

from traffic_quantum.config import MasterConfig
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager
from traffic_quantum.controllers.hybrid import HybridController


def test_ambulance_dispatch_and_step_no_exception():
    config = MasterConfig()
    network = RoadNetwork(config.network)
    sim = TrafficSimulator(network=network, config=config, seed=42)
    em_mgr = EmergencyCorridorManager(network, config=config)
    event_mgr = EventManager(network)
    ctrl = HybridController(network, config=config, solver_mode="brute_force")

    # Dispatch an ambulance from Node 0 (Junction A) to Node 5 (Junction F)
    mission = em_mgr.dispatch_ambulance(
        origin=0,
        destination=5,
        simulator=sim,
        current_tick=sim.current_tick,
        driver_name="Unit 108 Emergency",
        priority=2,
        hard_preemption=False,
    )
    assert mission is not None
    assert len(mission.path) >= 2

    # Step simulation forward 15 ticks with emergency corridor active
    for tick in range(15):
        event_mgr.step(tick, sim, em_mgr)
        biases = em_mgr.update_and_get_biases(tick, sim)
        assert isinstance(biases, dict)
        phases = ctrl.get_phases(tick, sim, emergency_biases=biases)
        assert len(phases) == network.num_intersections
        sim.step(phases)

    # Verify read-only inspect also works cleanly
    assert hasattr(em_mgr, "get_emergency_biases")
    biases_inspect = em_mgr.get_emergency_biases(sim)
    assert isinstance(biases_inspect, dict)


def test_explainability_read_only_get_emergency_biases_does_not_mutate_state():
    """Asserts that calling get_emergency_biases repeatedly does not alter mission or simulator state."""
    config = MasterConfig()
    network = RoadNetwork(config.network)
    sim = TrafficSimulator(network=network, config=config, seed=101)
    em_mgr = EmergencyCorridorManager(network, config=config)

    mission = em_mgr.dispatch_ambulance(
        origin=0,
        destination=5,
        simulator=sim,
        current_tick=0,
        driver_name="Test Paramedic",
    )

    # Step simulator forward 8 seconds
    for t in range(8):
        em_mgr.update_and_get_biases(t, sim)
        sim.step()

    # Capture snapshot before calling read-only inspect
    idx_before = mission.current_index
    progress_before = mission.current_edge_progress_sec
    completed_before = mission.completed
    waiting_before = mission.waiting_at_red
    cars_before = mission.cars_ahead

    # Call get_emergency_biases twice (as when re-rendering explainability panel)
    biases_1 = em_mgr.get_emergency_biases(sim)
    biases_2 = em_mgr.get_emergency_biases(sim)

    assert biases_1 == biases_2
    assert mission.current_index == idx_before
    assert mission.current_edge_progress_sec == progress_before
    assert mission.completed == completed_before
    assert mission.waiting_at_red == waiting_before
    assert mission.cars_ahead == cars_before
