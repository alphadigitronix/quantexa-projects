"""Unit tests for MaxPressureController."""

import pytest
from traffic_quantum.config import MasterConfig
from traffic_quantum.controllers.max_pressure import MaxPressureController
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def test_max_pressure_controller_init_and_phases():
    config = MasterConfig()
    network = RoadNetwork(config.network)
    sim = TrafficSimulator(network=network, config=config, seed=42)
    ctrl = MaxPressureController(network, config, eval_interval_sec=5, min_green_sec=10, hysteresis=1)

    # Initial phases should be all NS (0)
    phases = ctrl.get_phases(0, sim)
    assert len(phases) == network.num_intersections
    assert all(p == 0 for p in phases.values())

    # Spawn 10 vehicles on East approach of junction 0
    for _ in range(10):
        sim.spawn_vehicle(0, "E")

    # Tick 5: eval_interval reached, but min_green has not elapsed (last_switch=0, time=5 < 10)
    phases_5 = ctrl.get_phases(5, sim)
    assert phases_5[0] == 0

    # Tick 10: eval_interval reached and min_green=10 elapsed -> should switch to EW (1)
    phases_10 = ctrl.get_phases(10, sim)
    assert phases_10[0] == 1

    ctrl.reset()
    assert ctrl.last_switch_tick[0] == 0
