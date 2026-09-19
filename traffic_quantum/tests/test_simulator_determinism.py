"""Test suite verifying simulation determinism and grid configurability."""

import pytest
from traffic_quantum.config import MasterConfig, NetworkConfig
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


def test_simulation_determinism():
    """Verify that two simulation runs with identical seeds produce identical traffic trajectories."""
    seed = 12345
    duration = 100

    sim_a = TrafficSimulator(seed=seed)
    sim_b = TrafficSimulator(seed=seed)

    for tick in range(duration):
        # Alternate phases every 20 ticks
        phase = 0 if (tick // 20) % 2 == 0 else 1
        signals = {node: phase for node in sim_a.network.graph.nodes}
        
        res_a = sim_a.step(signals)
        res_b = sim_b.step(signals)

        assert res_a == res_b, f"Mismatch at tick {tick}: A={res_a}, B={res_b}"

    # Verify trajectory histories
    assert sim_a.throughput_history == sim_b.throughput_history
    assert sim_a.queue_length_history == sim_b.queue_length_history
    assert len(sim_a.completed_vehicles) == len(sim_b.completed_vehicles)
    
    for v_a, v_b in zip(sim_a.completed_vehicles, sim_b.completed_vehicles):
        assert v_a.id == v_b.id
        assert v_a.entry_tick == v_b.entry_tick
        assert v_a.waiting_ticks == v_b.waiting_ticks
        assert v_a.travel_ticks == v_b.travel_ticks


def test_grid_configurability_4_to_8_nodes():
    """Verify support for configurable network sizes between 4 and 8 intersections."""
    configs = [
        (2, 2, 4),  # 4 intersections
        (2, 3, 6),  # 6 intersections
        (2, 4, 8),  # 8 intersections
    ]

    for rows, cols, expected_nodes in configs:
        net_cfg = NetworkConfig(grid_rows=rows, grid_cols=cols, num_intersections=expected_nodes)
        cfg = MasterConfig(network=net_cfg)
        net = RoadNetwork(config=net_cfg)
        
        assert net.graph.number_of_nodes() == expected_nodes
        assert net.num_intersections == expected_nodes

        sim = TrafficSimulator(network=net, config=cfg, seed=99)
        step_res = sim.step({i: 0 for i in range(expected_nodes)})
        assert step_res["tick"] == 1
