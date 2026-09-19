"""Fixed-Timing Baseline Controller.

Implements a predictable, cyclical 30s North-South / 30s East-West signal plan
(60-second cycle) at every intersection.
"""

from typing import Dict, Optional
from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.base import BaseController
from traffic_quantum.network import RoadNetwork


class FixedController(BaseController):
    """Fixed-time signal controller with 30s NS / 30s EW alternating phases."""

    def __init__(self, network: RoadNetwork, config: Optional[MasterConfig] = None):
        super().__init__(network, config)
        self.name = "Fixed-Timing Baseline"
        self.cycle_len = self.config.baseline.fixed_cycle_sec
        self.ns_duration = self.config.baseline.fixed_ns_green_sec

    def get_phases(self, current_tick: int, simulator) -> Dict[int, int]:
        """Returns phase for each intersection based on cycle time."""
        time_in_cycle = current_tick % self.cycle_len
        phase = (
            self.config.simulation.phase_ns_green
            if time_in_cycle < self.ns_duration
            else self.config.simulation.phase_ew_green
        )
        return {node: phase for node in self.network.graph.nodes}
