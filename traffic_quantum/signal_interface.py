"""Hardware-Ready Signal Controller Interface and Software Conflict Monitor.

Provides an abstract hardware abstraction layer (HAL) for urban traffic controllers:
- SignalControllerInterface: ABC for physical or simulated signal heads
- SoftwareConflictMonitor: Safety layer preventing conflicting greens, enforcing
  minimum green, and defining yellow/all-red clearance intervals
- HardwareWatchdog: Fail-safe watchdog timer that automatically falls back to
  fixed-timing if the adaptive optimizer stalls or crashes.

NOTE: This is an architectural abstraction layer for future field deployment.
The clearance interval logic (yellow/all-red clearance) is a hardware-layer safety
concept designed for physical controller field interfacing; it is NOT exercised
by the discrete-tick simulation engine (which operates strictly on binary green/red phases).
No physical signal hardware is currently integrated.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Tuple


@dataclass
class IntersectionSignalState:
    """Represents the physical or simulated signal head state at an intersection."""
    intersection_id: int
    current_phase: int  # 0 = NS Green, 1 = EW Green
    time_in_phase: int = 0
    in_clearance: bool = False
    clearance_ticks_remaining: int = 0
    pending_phase: Optional[int] = None
    is_preempted: bool = False
    last_command_tick: int = 0


class SoftwareConflictMonitor:
    """Safety interlock layer enforcing NEMA/170 signal safety standards.
    
    Rules enforced:
    1. Conflicting Greens: NS Green (0) and EW Green (1) can never display concurrently.
    2. Minimum Green: An active green phase cannot be terminated before min_green_sec.
    3. Clearance Interval: Phase transitions must enforce a yellow/all-red clearance interval.
    """

    def __init__(self, min_green_sec: int = 10, clearance_sec: int = 2):
        self.min_green_sec = min_green_sec
        self.clearance_sec = clearance_sec

    def can_transition(
        self,
        state: IntersectionSignalState,
        desired_phase: int,
        force_override: bool = False,
    ) -> Tuple[bool, str]:
        """Evaluates whether transitioning to desired_phase is legally and physically safe."""
        if desired_phase == state.current_phase and not state.in_clearance:
            return True, "Phase maintained"

        if state.in_clearance:
            return False, f"Intersection {state.intersection_id} is in yellow/all-red clearance"

        if not force_override and state.time_in_phase < self.min_green_sec:
            return (
                False,
                f"Minimum green violation: in phase {state.time_in_phase}s < {self.min_green_sec}s",
            )

        return True, "Transition approved"


class SignalControllerInterface(ABC):
    """Abstract Interface for traffic signal controllers (field hardware or simulator)."""

    @abstractmethod
    def set_phase(self, intersection_id: int, phase: int, duration: int = 10) -> bool:
        """Commands a signal phase change at an intersection."""
        pass

    @abstractmethod
    def get_state(self, intersection_id: int) -> Dict[str, object]:
        """Queries the current signal head state."""
        pass

    @abstractmethod
    def emergency_preempt(
        self,
        intersection_id: int,
        phase: int,
        duration: int = 30,
        token: Optional[str] = None,
    ) -> bool:
        """Forces priority preemption for emergency vehicles with authorization."""
        pass

    @abstractmethod
    def safe_fallback(self) -> None:
        """Engages fail-safe mode (standard fixed-timing cycle or all-red flash)."""
        pass


class HardwareWatchdog:
    """Watchdog monitor detecting optimizer failure or communication loss."""

    def __init__(self, timeout_sec: float = 30.0):
        self.timeout_sec = timeout_sec
        self.last_heartbeat_time: float = time.time()
        self.last_heartbeat_tick: Optional[int] = None
        self.is_fallback_active: bool = False

    def heartbeat(self, tick: Optional[int] = None) -> None:
        """Resets the watchdog timer."""
        self.last_heartbeat_time = time.time()
        if tick is not None:
            self.last_heartbeat_tick = tick
        self.is_fallback_active = False

    def check_timeout(self, current_tick: Optional[int] = None, max_tick_lag: int = 25) -> bool:
        """Checks whether optimizer has timed out.
        
        Returns:
            True if timed out and fallback should be engaged, False if healthy.
        """
        now = time.time()
        wall_timeout = (now - self.last_heartbeat_time) > self.timeout_sec
        tick_timeout = False
        if current_tick is not None and self.last_heartbeat_tick is not None:
            tick_timeout = (current_tick - self.last_heartbeat_tick) > max_tick_lag

        if wall_timeout or tick_timeout:
            self.is_fallback_active = True
            return True
        return False


class SimulatedSignalController(SignalControllerInterface):
    """Concrete implementation of SignalControllerInterface routing commands to simulator."""

    def __init__(
        self,
        simulator,
        min_green_sec: int = 10,
        clearance_sec: int = 2,
        watchdog_timeout_sec: float = 30.0,
    ):
        self.simulator = simulator
        self.conflict_monitor = SoftwareConflictMonitor(
            min_green_sec=min_green_sec, clearance_sec=clearance_sec
        )
        self.watchdog = HardwareWatchdog(timeout_sec=watchdog_timeout_sec)
        
        self.states: Dict[int, IntersectionSignalState] = {
            node: IntersectionSignalState(
                intersection_id=node,
                current_phase=self.simulator.signal_phases.get(node, 0),
            )
            for node in self.simulator.network.graph.nodes
        }

    def tick(self) -> None:
        """Advances internal signal head timers, managing clearance intervals and watchdog."""
        current_tick = self.simulator.current_tick
        
        # Check watchdog health
        if self.watchdog.check_timeout(current_tick):
            self.safe_fallback()
            return

        for node, state in self.states.items():
            if state.in_clearance:
                state.clearance_ticks_remaining -= 1
                if state.clearance_ticks_remaining <= 0:
                    state.in_clearance = False
                    if state.pending_phase is not None:
                        state.current_phase = state.pending_phase
                        state.pending_phase = None
                        state.time_in_phase = 0
                        self.simulator.signal_phases[node] = state.current_phase
            else:
                state.time_in_phase += 1

    def set_phase(self, intersection_id: int, phase: int, duration: int = 10) -> bool:
        """Applies requested phase subject to conflict monitor validation."""
        if intersection_id not in self.states:
            return False

        state = self.states[intersection_id]
        approved, reason = self.conflict_monitor.can_transition(
            state=state, desired_phase=phase, force_override=state.is_preempted
        )

        if not approved:
            return False

        if phase != state.current_phase:
            if self.conflict_monitor.clearance_sec > 0:
                state.in_clearance = True
                state.clearance_ticks_remaining = self.conflict_monitor.clearance_sec
                state.pending_phase = phase
            else:
                state.current_phase = phase
                state.time_in_phase = 0
                self.simulator.signal_phases[intersection_id] = phase

        state.last_command_tick = self.simulator.current_tick
        return True

    def get_state(self, intersection_id: int) -> Dict[str, object]:
        """Queries signal state at intersection."""
        if intersection_id not in self.states:
            return {}
        s = self.states[intersection_id]
        return {
            "intersection_id": s.intersection_id,
            "current_phase": s.current_phase,
            "time_in_phase": s.time_in_phase,
            "in_clearance": s.in_clearance,
            "is_preempted": s.is_preempted,
            "fallback_active": self.watchdog.is_fallback_active,
        }

    def emergency_preempt(
        self,
        intersection_id: int,
        phase: int,
        duration: int = 30,
        token: Optional[str] = None,
    ) -> bool:
        """Applies emergency preemption directly overriding minimum green."""
        if intersection_id not in self.states:
            return False
        state = self.states[intersection_id]
        state.is_preempted = True
        state.current_phase = phase
        state.time_in_phase = 0
        state.in_clearance = False
        self.simulator.signal_phases[intersection_id] = phase
        return True

    def safe_fallback(self) -> None:
        """Executes fail-safe fixed timing (30s NS, 30s EW)."""
        tick = self.simulator.current_tick
        fixed_phase = (tick // 30) % 2
        for node, state in self.states.items():
            state.is_preempted = False
            state.in_clearance = False
            state.current_phase = fixed_phase
            self.simulator.signal_phases[node] = fixed_phase
