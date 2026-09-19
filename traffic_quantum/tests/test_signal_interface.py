"""Unit tests for SignalControllerInterface, SoftwareConflictMonitor, and HardwareWatchdog."""

import pytest
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator
from traffic_quantum.signal_interface import (
    SimulatedSignalController,
    SoftwareConflictMonitor,
    HardwareWatchdog,
    IntersectionSignalState,
)


def test_conflict_monitor_enforces_minimum_green():
    """Verify that conflict monitor rejects phase switches that violate minimum green duration."""
    monitor = SoftwareConflictMonitor(min_green_sec=10, clearance_sec=2)
    state = IntersectionSignalState(intersection_id=0, current_phase=0, time_in_phase=4)

    # Attempt to switch to phase 1 after only 4 seconds of green
    approved, msg = monitor.can_transition(state, desired_phase=1)
    assert approved is False
    assert "Minimum green violation" in msg

    # After 10 seconds, transition must be approved
    state.time_in_phase = 10
    approved, msg = monitor.can_transition(state, desired_phase=1)
    assert approved is True


def test_conflict_monitor_clearance_interval():
    """Verify that signal enters clearance (yellow/all-red) before switching to green."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    ctrl = SimulatedSignalController(sim, min_green_sec=10, clearance_sec=2)

    # Intersection 0 starts in phase 0, let 10s elapse
    for _ in range(10):
        ctrl.tick()

    # Command switch to phase 1
    ok = ctrl.set_phase(0, phase=1)
    assert ok is True

    # State must be in clearance
    st = ctrl.get_state(0)
    assert st["in_clearance"] is True

    # After 2 ticks of clearance, phase must transition to 1
    ctrl.tick()
    ctrl.tick()
    st_after = ctrl.get_state(0)
    assert st_after["in_clearance"] is False
    assert st_after["current_phase"] == 1


def test_watchdog_fail_safe_fallback():
    """Verify that watchdog detects optimizer timeout and triggers safe fixed-timing fallback."""
    network = RoadNetwork()
    sim = TrafficSimulator(network=network, seed=42)
    ctrl = SimulatedSignalController(sim, watchdog_timeout_sec=0.1)

    # Simulate heartbeat
    ctrl.watchdog.heartbeat(tick=0)
    assert ctrl.watchdog.check_timeout(current_tick=1) is False

    # Simulate 30 ticks passing without optimizer heartbeat
    assert ctrl.watchdog.check_timeout(current_tick=35, max_tick_lag=20) is True

    # Call tick on controller -> triggers safe fallback
    ctrl.tick()
    st = ctrl.get_state(0)
    assert st["fallback_active"] is True
