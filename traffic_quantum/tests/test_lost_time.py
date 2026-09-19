"""Unit tests for switch_lost_time_sec in TrafficSimulator."""

import pytest
from traffic_quantum.config import MasterConfig, SimulationConfig
from traffic_quantum.simulator import TrafficSimulator


def test_lost_time_zero_discharges_immediately():
    """Verify that when switch_lost_time_sec=0, discharge happens normally upon phase change."""
    sim = TrafficSimulator(switch_lost_time_sec=0, seed=42)
    sim.manual_traffic_mode = True
    # Put car at node 0, approach 'N' (NS green by default)
    sim.spawn_vehicle(origin_node=0, approach="N")
    assert len(sim.queues[0]["N"]) == 1

    # Switch to EW green (phase 1)
    sim.step(signal_phases={0: 1})
    assert sim.lost_time_remaining[0] == 0

    # Put car at node 0, approach 'E' (EW green active)
    sim.spawn_vehicle(origin_node=0, approach="E")
    assert len(sim.queues[0]["E"]) == 1

    # Step at even tick where discharge occurs
    sim.current_tick = 2  # tick % discharge_interval_ticks == 0
    res = sim.step(signal_phases={0: 1})
    assert res["discharged"] >= 1 or len(sim.queues[0]["E"]) == 0


def test_lost_time_blocks_discharge_during_penalty():
    """Verify that switch_lost_time_sec blocks discharge for N seconds after a phase change."""
    sim = TrafficSimulator(switch_lost_time_sec=2, seed=42)
    sim.manual_traffic_mode = True
    # Start at phase 0 (NS green)
    # Put vehicle in 'E' queue (currently red)
    sim.spawn_vehicle(origin_node=0, approach="E")
    assert len(sim.queues[0]["E"]) == 1

    # Switch to phase 1 (EW green) at tick 2 (which is normally a discharge tick)
    sim.current_tick = 2
    # Before step, lost_time_remaining is 0
    assert sim.lost_time_remaining[0] == 0

    res1 = sim.step(signal_phases={0: 1})
    # During tick 2, phase changed so lost_time_remaining was 2 during discharge -> blocked!
    assert res1["discharged"] == 0
    assert len(sim.queues[0]["E"]) == 1
    # After tick 2 finishes, counter was decremented from 2 to 1
    assert sim.lost_time_remaining[0] == 1

    # Tick 3: not a discharge tick (odd tick)
    res2 = sim.step(signal_phases={0: 1})
    # Decremented from 1 to 0
    assert sim.lost_time_remaining[0] == 0
    assert len(sim.queues[0]["E"]) == 1

    # Tick 4: even tick, lost_time_remaining is now 0 -> vehicle should discharge!
    res3 = sim.step(signal_phases={0: 1})
    assert res3["discharged"] == 1
    assert len(sim.queues[0]["E"]) == 0
