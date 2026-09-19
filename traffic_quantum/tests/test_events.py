"""Test suite for Dynamic Traffic Events (road closures, accidents, surges, and scripted scenarios)."""

import pytest
from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.events import EventManager, EventType, TrafficEvent
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def test_road_closure_and_accident_lifecycle():
    """Verify capacity reduction and automatic recovery for accidents and closures."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    em_mgr = EmergencyCorridorManager(network)
    evt_mgr = EventManager(network)

    base_cap = network.graph[1][2]["base_capacity"]

    # 1. Trigger accident for 20 seconds
    acc_event = TrafficEvent(
        id="acc_test",
        event_type=EventType.ACCIDENT,
        start_tick=5,
        duration_ticks=20,
        target_edge=(1, 2),
    )
    evt_mgr.schedule_event(acc_event)

    # Step simulator to tick 6
    for t in range(6):
        evt_mgr.step(t, sim, em_mgr)

    # Capacity should now be reduced by half
    assert network.graph[1][2]["status"] == "reduced"
    assert network.graph[1][2]["capacity"] == max(1, base_cap // 2)

    # Step beyond expiration (tick 30)
    for t in range(6, 30):
        evt_mgr.step(t, sim, em_mgr)

    # Capacity and status must be restored
    assert network.graph[1][2]["status"] == "open"
    assert network.graph[1][2]["capacity"] == base_cap
    assert acc_event.resolved is True


def test_congestion_surge_injection():
    """Verify that congestion surge increases vehicle arrivals at target boundary."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    em_mgr = EmergencyCorridorManager(network)
    evt_mgr = EventManager(network)

    surge_event = TrafficEvent(
        id="surge_test",
        event_type=EventType.CONGESTION_SURGE,
        start_tick=0,
        duration_ticks=25,
        target_entry=(0, "W"),
        surge_multiplier=4.0,
    )
    evt_mgr.trigger_event_now(surge_event, current_tick=0, simulator=sim, emergency_mgr=em_mgr)

    for t in range(20):
        evt_mgr.step(t, sim, em_mgr)
        sim.step()

    # The queue at junction 0 approach W should have received significant traffic
    q_w = len(sim.queues[0]["W"])
    assert q_w > 0


def test_scripted_scenario_loading():
    """Verify scripted scenario loading schedules proper dynamic events."""
    network = RoadNetwork()
    evt_mgr = EventManager(network)
    evt_mgr.load_scripted_scenario("accident_corridor")

    assert len(evt_mgr.scheduled_events) == 2
    types = [e.event_type for e in evt_mgr.scheduled_events]
    assert EventType.ACCIDENT in types
    assert EventType.EMERGENCY in types
