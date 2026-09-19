"""Road network construction using NetworkX.

Supports configurable 2D grid networks (e.g., 2x2=4 up to 2x4=8, default 2x3=6 intersections).
Each road segment (directed edge) models length, capacity, and operational status
('open', 'closed', 'reduced').
"""

from typing import Dict, List, Optional, Tuple
import networkx as nx
from traffic_quantum.config import NetworkConfig, DEFAULT_CONFIG


class RoadNetwork:
    """Represents the urban road network graph with intersections and directed road segments."""

    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or DEFAULT_CONFIG.network
        self.rows = self.config.grid_rows
        self.cols = self.config.grid_cols
        self.num_intersections = self.rows * self.cols
        self.graph = nx.DiGraph()
        self._build_grid_network()

    def _build_grid_network(self) -> None:
        """Constructs the NetworkX directed graph for the grid."""
        # Add nodes with grid coordinates and geographical metadata
        for r in range(self.rows):
            for c in range(self.cols):
                node_id = r * self.cols + c
                geo = self.config.chennai_junctions.get(node_id, {
                    "name": f"Junction_{r}_{c}",
                    "lat": 13.000 + r * 0.015,
                    "lon": 80.200 + c * 0.015,
                })
                self.graph.add_node(
                    node_id,
                    row=r,
                    col=c,
                    name=geo["name"],
                    lat=geo["lat"],
                    lon=geo["lon"],
                )

        # Add bidirectional edges between adjacent grid intersections
        for r in range(self.rows):
            for c in range(self.cols):
                u = r * self.cols + c
                
                # East-West connections
                if c + 1 < self.cols:
                    v = r * self.cols + (c + 1)
                    # u -> v: vehicle moves East (enters v at 'W' approach)
                    self._add_road_edge(u, v, direction="E", target_approach="W")
                    # v -> u: vehicle moves West (enters u at 'E' approach)
                    self._add_road_edge(v, u, direction="W", target_approach="E")
                
                # North-South connections
                if r + 1 < self.rows:
                    v = (r + 1) * self.cols + c
                    # u -> v: vehicle moves South (enters v at 'N' approach)
                    self._add_road_edge(u, v, direction="S", target_approach="N")
                    # v -> u: vehicle moves North (enters u at 'S' approach)
                    self._add_road_edge(v, u, direction="N", target_approach="S")

    def _add_road_edge(self, u: int, v: int, direction: str, target_approach: str) -> None:
        """Adds a directed road edge with capacity and state."""
        self.graph.add_edge(
            u,
            v,
            direction=direction,
            target_approach=target_approach,
            length_m=self.config.default_road_length_m,
            base_capacity=self.config.default_capacity,
            capacity=self.config.default_capacity,
            status="open",  # 'open', 'closed', 'reduced'
            free_flow_travel_time=self.config.free_flow_travel_time_sec,
        )

    def set_edge_status(self, u: int, v: int, status: str) -> None:
        """Modifies edge operational status ('open', 'closed', 'reduced') and adjusts effective capacity."""
        if not self.graph.has_edge(u, v):
            raise ValueError(f"Road segment ({u}, {v}) does not exist.")
        
        status = status.lower()
        if status not in ("open", "closed", "reduced"):
            raise ValueError(f"Invalid status '{status}'. Must be 'open', 'closed', or 'reduced'.")
        
        base_cap = self.graph[u][v]["base_capacity"]
        self.graph[u][v]["status"] = status
        
        if status == "open":
            self.graph[u][v]["capacity"] = base_cap
        elif status == "reduced":
            self.graph[u][v]["capacity"] = max(1, base_cap // 2)
        elif status == "closed":
            self.graph[u][v]["capacity"] = 0

    def get_neighbors(self, node_id: int) -> List[int]:
        """Returns neighboring intersection IDs."""
        return list(self.graph.neighbors(node_id))

    def get_edge_data(self, u: int, v: int) -> Dict:
        """Returns road edge metadata."""
        return self.graph[u][v]

    def get_node_coords(self, node_id: int) -> Tuple[float, float]:
        """Returns (lat, lon) coordinates of an intersection."""
        node = self.graph.nodes[node_id]
        return node["lat"], node["lon"]

    def get_boundary_approaches(self) -> List[Tuple[int, str]]:
        """Identifies boundary entry queues that receive external incoming traffic.
        
        Returns list of (intersection_id, approach_direction) tuples.
        """
        boundaries = []
        for r in range(self.rows):
            for c in range(self.cols):
                u = r * self.cols + c
                if r == 0:
                    boundaries.append((u, "N"))  # Inflow from North
                if r == self.rows - 1:
                    boundaries.append((u, "S"))  # Inflow from South
                if c == 0:
                    boundaries.append((u, "W"))  # Inflow from West
                if c == self.cols - 1:
                    boundaries.append((u, "E"))  # Inflow from East
        return boundaries
