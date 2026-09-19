"""Rule-Based (Longest-Queue-First) Baseline Controller.

Evaluates approach queues every 10 seconds and grants green to the direction
with the larger queue, while enforcing a minimum green time to avoid signal flicker.
"""

from typing import Dict, Optional
from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.controllers.base import BaseController
from traffic_quantum.network import RoadNetwork


class RuleBasedController(BaseController):
    """Adaptive heuristic controller prioritizing the direction with the longest queue."""

    def __init__(
        self,
        network: RoadNetwork,
        config: Optional[MasterConfig] = None,
        eval_interval_sec: Optional[int] = None,
        min_green_sec: Optional[int] = None,
        hysteresis: int = 0,
    ):
        super().__init__(network, config)
        self.name = "Rule-Based (Longest Queue)"
        self.eval_interval = eval_interval_sec if eval_interval_sec is not None else self.config.baseline.rule_eval_interval_sec
        self.min_green = min_green_sec if min_green_sec is not None else self.config.baseline.rule_min_green_sec
        self.hysteresis = max(0, int(hysteresis))
        
        # State tracking per intersection
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

    def get_phases(self, current_tick: int, simulator) -> Dict[int, int]:
        """Periodically evaluates queue lengths and updates phases if minimum green duration has elapsed."""
        if current_tick % self.eval_interval == 0:
            for node in self.network.graph.nodes:
                q_lengths = simulator.get_approach_queue_lengths(node)
                q_ns = q_lengths.get("N", 0) + q_lengths.get("S", 0)
                q_ew = q_lengths.get("E", 0) + q_lengths.get("W", 0)

                current_phase = self.current_phases[node]
                desired_phase = current_phase

                if current_phase == self.config.simulation.phase_ns_green:
                    if (q_ew - q_ns) >= self.hysteresis and q_ew > q_ns:
                        desired_phase = self.config.simulation.phase_ew_green
                else:
                    if (q_ns - q_ew) >= self.hysteresis and q_ns > q_ew:
                        desired_phase = self.config.simulation.phase_ns_green

                time_since_last_switch = current_tick - self.last_switch_tick[node]
                if desired_phase != self.current_phases[node] and time_since_last_switch >= self.min_green:
                    self.current_phases[node] = desired_phase
                    self.last_switch_tick[node] = current_tick

        return dict(self.current_phases)
