"""Dynamic Events Engine.

Supports real-time and scripted traffic disruptions:
1. Emergency vehicle dispatch
2. Road closure (capacity = 0 with dynamic vehicle rerouting)
3. Traffic accident (capacity halved for a set duration, then restored)
4. Sudden congestion surge at designated entry boundaries
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from traffic_quantum.emergency import EmergencyCorridorManager
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


class EventType(str, Enum):
    """Supported dynamic event types."""
    EMERGENCY = "emergency"
    ROAD_CLOSURE = "road_closure"
    ACCIDENT = "accident"
    CONGESTION_SURGE = "congestion_surge"


@dataclass
class TrafficEvent:
    """Represents a scheduled or live-triggered dynamic event."""
    id: str
    event_type: EventType
    start_tick: int
    duration_ticks: Optional[int] = None
    target_edge: Optional[Tuple[int, int]] = None
    target_entry: Optional[Tuple[int, str]] = None  # (node_id, approach)
    surge_multiplier: float = 3.0
    ambulance_origin: Optional[int] = None
    ambulance_destination: Optional[int] = None
    active: bool = False
    resolved: bool = False


class EventManager:
    """Coordinates the injection, active maintenance, and resolution of dynamic events."""

    def __init__(self, network: RoadNetwork):
        self.network = network
        self.scheduled_events: List[TrafficEvent] = []
        self.active_events: List[TrafficEvent] = []
        self.history: List[TrafficEvent] = []
        self.active_surges: Dict[Tuple[int, str], float] = {}

    def schedule_event(self, event: TrafficEvent) -> None:
        """Schedules a future event for scripted scenarios."""
        self.scheduled_events.append(event)

    def trigger_event_now(
        self,
        event: TrafficEvent,
        current_tick: int,
        simulator: TrafficSimulator,
        emergency_mgr: EmergencyCorridorManager,
    ) -> None:
        """Immediately executes an event live (e.g., from Streamlit dashboard)."""
        event.start_tick = current_tick
        self._activate_event(event, simulator, emergency_mgr)

    def _activate_event(
        self,
        event: TrafficEvent,
        simulator: TrafficSimulator,
        emergency_mgr: EmergencyCorridorManager,
    ) -> None:
        """Applies event effects to network and simulator state."""
        event.active = True
        self.active_events.append(event)
        self.history.append(event)

        if event.event_type == EventType.ROAD_CLOSURE and event.target_edge:
            u, v = event.target_edge
            self.network.set_edge_status(u, v, "closed")

        elif event.event_type == EventType.ACCIDENT and event.target_edge:
            u, v = event.target_edge
            self.network.set_edge_status(u, v, "reduced")

        elif event.event_type == EventType.CONGESTION_SURGE and event.target_entry:
            self.active_surges[event.target_entry] = event.surge_multiplier

        elif event.event_type == EventType.EMERGENCY:
            origin = event.ambulance_origin if event.ambulance_origin is not None else 0
            dest = event.ambulance_destination if event.ambulance_destination is not None else 5
            emergency_mgr.dispatch_ambulance(
                origin=origin,
                destination=dest,
                simulator=simulator,
                current_tick=event.start_tick,
            )

    def step(
        self,
        current_tick: int,
        simulator: TrafficSimulator,
        emergency_mgr: EmergencyCorridorManager,
    ) -> List[TrafficEvent]:
        """Evaluates active events, triggers scheduled ones, and resolves expired events."""
        # 1. Trigger scheduled events that have arrived
        for event in list(self.scheduled_events):
            if current_tick >= event.start_tick:
                self.scheduled_events.remove(event)
                self._activate_event(event, simulator, emergency_mgr)

        # 2. Check and expire temporary events
        resolved_this_tick = []
        for event in list(self.active_events):
            if event.duration_ticks is not None:
                if current_tick >= event.start_tick + event.duration_ticks:
                    event.active = False
                    event.resolved = True
                    self.active_events.remove(event)
                    resolved_this_tick.append(event)

                    # Restore modified network capacities
                    if event.event_type in (EventType.ACCIDENT, EventType.ROAD_CLOSURE) and event.target_edge:
                        u, v = event.target_edge
                        self.network.set_edge_status(u, v, "open")
                    elif event.event_type == EventType.CONGESTION_SURGE and event.target_entry:
                        self.active_surges.pop(event.target_entry, None)

        # 3. Inject vehicles for active congestion surges
        for (node, app), mult in self.active_surges.items():
            # Extra stochastic arrivals proportional to multiplier
            rate = simulator.config.simulation.base_arrival_rate * (mult - 1.0)
            if simulator.rng.random() < rate:
                simulator.spawn_vehicle(origin_node=node, approach=app)

        return resolved_this_tick

    def load_scripted_scenario(self, scenario_name: str) -> None:
        """Populates scheduled events for standardized benchmark scenarios."""
        self.scheduled_events.clear()
        
        if scenario_name == "accident_corridor":
            # Accident on edge (1, 2) at tick 30 lasting 60s
            self.schedule_event(TrafficEvent(
                id="acc_1_2",
                event_type=EventType.ACCIDENT,
                start_tick=30,
                duration_ticks=60,
                target_edge=(1, 2),
            ))
            # Emergency dispatch at tick 45
            self.schedule_event(TrafficEvent(
                id="amb_0_5",
                event_type=EventType.EMERGENCY,
                start_tick=45,
                ambulance_origin=0,
                ambulance_destination=5,
            ))
        elif scenario_name == "rush_hour_surge":
            # Congestion surge at West entry point of junction 0
            self.schedule_event(TrafficEvent(
                id="surge_0_w",
                event_type=EventType.CONGESTION_SURGE,
                start_tick=20,
                duration_ticks=80,
                target_entry=(0, "W"),
                surge_multiplier=3.5,
            ))
            # Temporary closure of link (3, 4)
            self.schedule_event(TrafficEvent(
                id="closure_3_4",
                event_type=EventType.ROAD_CLOSURE,
                start_tick=40,
                duration_ticks=50,
                target_edge=(3, 4),
            ))
