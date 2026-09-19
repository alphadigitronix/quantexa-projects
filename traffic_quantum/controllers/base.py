"""Abstract Base Signal Controller interface."""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.network import RoadNetwork


class BaseController(ABC):
    """Abstract base class for all traffic signal controllers."""

    def __init__(self, network: RoadNetwork, config: Optional[MasterConfig] = None):
        self.network = network
        self.config = config or DEFAULT_CONFIG
        self.name: str = "BaseController"

    @abstractmethod
    def get_phases(self, current_tick: int, simulator) -> Dict[int, int]:
        """Calculates and returns signal phases {node_id: phase} for the current simulation tick.
        
        Phase convention:
            0: North-South Green (East-West Red)
            1: East-West Green (North-South Red)
        """
        pass

    def reset(self) -> None:
        """Resets any internal controller state."""
        pass
