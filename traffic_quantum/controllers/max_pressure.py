"""Max-Pressure Adaptive Signal Controller.

Implements the classical Max-Pressure network flow control algorithm (Varaiya 2013).
At each intersection, phase pressure is computed as the queue on the approaches
it serves minus the queue on the downstream links those approaches feed.
Enforces minimum green and hysteresis to prevent signal flickering.
"""

from typing import Dict, Optional
from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.base import BaseController
from traffic_quantum.network import RoadNetwork


class MaxPressureController(BaseController):
    """Classical adaptive controller maximizing queue differential between upstream and downstream links."""

    def __init__(
        self,
        network: RoadNetwork,
        config: Optional[MasterConfig] = None,
        eval_interval_sec: int = 5,
        min_green_sec: int = 10,
        hysteresis: int = 0,
    ):
        super().__init__(network, config)
        self.name = "Max-Pressure (tuned)"
        self.eval_interval = eval_interval_sec
        self.min_green = min_green_sec
        self.hysteresis = max(0, int(hysteresis))

        self.current_phases: Dict[int, int] = {
            node: self.config.simulation.phase_ns_green
            for node in self.network.graph.nodes
        }
        self.last_switch_tick: Dict[int, int] = {
            node: 0 for node in self.network.graph.nodes
        }

    def reset(self) -> None:
        """Resets controller state."""
        self.current_phases = {
            node: self.config.simulation.phase_ns_green
            for node in self.network.graph.nodes
        }
        self.last_switch_tick = {
            node: 0 for node in self.network.graph.nodes
        }

    def _compute_approach_pressure(self, node: int, app: str, simulator) -> float:
        """Computes upstream queue minus downstream approach queue for a given approach."""
        q_in = len(simulator.queues[node].get(app, []))
        downstream = simulator._get_target_neighbor(node, app)
        if downstream is None:
            q_out = 0.0
        else:
            target_node, target_app = downstream
            q_out = len(simulator.queues[target_node].get(target_app, []))
        return float(q_in - q_out)

    def get_phases(self, current_tick: int, simulator) -> Dict[int, int]:
        """Evaluates max-pressure at each intersection and switches phase if min green is satisfied."""
        if current_tick % self.eval_interval == 0:
            for node in self.network.graph.nodes:
                press_n = self._compute_approach_pressure(node, "N", simulator)
                press_s = self._compute_approach_pressure(node, "S", simulator)
                pressure_ns = press_n + press_s

                press_e = self._compute_approach_pressure(node, "E", simulator)
                press_w = self._compute_approach_pressure(node, "W", simulator)
                pressure_ew = press_e + press_w

                current_phase = self.current_phases[node]
                desired_phase = current_phase

                if current_phase == self.config.simulation.phase_ns_green:
                    if (pressure_ew - pressure_ns) >= self.hysteresis and pressure_ew > pressure_ns:
                        desired_phase = self.config.simulation.phase_ew_green
                else:
                    if (pressure_ns - pressure_ew) >= self.hysteresis and pressure_ns > pressure_ew:
                        desired_phase = self.config.simulation.phase_ns_green

                time_since_switch = current_tick - self.last_switch_tick[node]
                if desired_phase != current_phase and time_since_switch >= self.min_green:
                    self.current_phases[node] = desired_phase
                    self.last_switch_tick[node] = current_tick

        return dict(self.current_phases)
