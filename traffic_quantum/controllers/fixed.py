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

    def __init__(
        self,
        network: RoadNetwork,
        config: Optional[MasterConfig] = None,
        cycle_len_sec: Optional[int] = None,
        ns_green_sec: Optional[int] = None,
        name: Optional[str] = None,
    ):
        super().__init__(network, config)
        self.cycle_len = cycle_len_sec if cycle_len_sec is not None else self.config.baseline.fixed_cycle_sec
        self.ns_duration = ns_green_sec if ns_green_sec is not None else self.config.baseline.fixed_ns_green_sec
        if name is not None:
            self.name = name
        elif cycle_len_sec is not None or ns_green_sec is not None:
            self.name = "Fixed (tuned)"
        else:
            self.name = "Fixed-Timing Baseline"


    def get_phases(self, current_tick: int, simulator) -> Dict[int, int]:
        """Returns phase for each intersection based on cycle time."""
        time_in_cycle = current_tick % self.cycle_len
        phase = (
            self.config.simulation.phase_ns_green
            if time_in_cycle < self.ns_duration
            else self.config.simulation.phase_ew_green
        )
        return {node: phase for node in self.network.graph.nodes}
