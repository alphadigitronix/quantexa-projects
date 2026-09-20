"""QUBO (Quadratic Unconstrained Binary Optimization) construction for urban traffic signals.

Variables: x_i in {0, 1} for intersection i in {0, ..., N-1}
  x_i = 0: North-South phase GREEN (East-West RED)
  x_i = 1: East-West phase GREEN (North-South RED)
"""

from typing import Dict, Optional, Tuple
import numpy as np
from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.network import RoadNetwork
from traffic_quantum.simulator import TrafficSimulator


class TrafficQUBOBuilder:
    """Constructs the QUBO matrix Q and constant offset C0 from network traffic state."""

    def __init__(self, network: RoadNetwork, config: Optional[MasterConfig] = None):
        self.network = network
        self.config = config or DEFAULT_CONFIG
        self.n = network.num_intersections

    def build_qubo(
        self,
        simulator: TrafficSimulator,
        emergency_biases: Optional[Dict[int, str]] = None,
    ) -> Tuple[np.ndarray, float]:
        """Builds the QUBO matrix Q (n x n) and constant offset C0.
        
        Cost function: Cost(x) = x^T Q x + C0
        
        Args:
            simulator: Current traffic simulation instance.
            emergency_biases: Optional dict mapping intersection ID to required direction ('NS' or 'EW').
            
        Returns:
            Tuple of (Q_matrix: np.ndarray of shape (n, n), C0: float)
        """
        Q = np.zeros((self.n, self.n), dtype=np.float64)
        C0 = 0.0
        
        w_queue = self.config.qubo.w_queue
        w_coord = self.config.qubo.w_coord
        w_spill = self.config.qubo.w_spillback
        w_emerg = self.config.qubo.w_emergency
        spill_thresh = self.config.qubo.spillback_threshold

        # 1. Linear queue delay penalty: cost_i = q_EW*(1 - x_i) + q_NS*x_i
        use_wait_weight = getattr(self.config.qubo, "use_wait_weighted_queue", False)
        w_wait_weight = getattr(self.config.qubo, "w_wait_weight", 0.05)
        use_lookahead = getattr(self.config.qubo, "use_in_transit_lookahead", False)
        w_lookahead = getattr(self.config.qubo, "w_in_transit_lookahead", 0.5)

        for i in range(self.n):
            q_lens = simulator.get_approach_queue_lengths(i)
            
            if use_wait_weight:
                # Wait-weighted queue: scale queue by average wait time in queue
                def get_wait_weighted_q(app: str) -> float:
                    raw_q = simulator.queues[i].get(app, [])
                    if not raw_q:
                        return 0.0
                    avg_wait = sum(getattr(veh, "wait_ticks", 0) for veh in raw_q) / len(raw_q)
                    return len(raw_q) * (1.0 + w_wait_weight * avg_wait)
                
                q_ns = get_wait_weighted_q("N") + get_wait_weighted_q("S")
                q_ew = get_wait_weighted_q("E") + get_wait_weighted_q("W")
            else:
                q_ns = float(q_lens.get("N", 0) + q_lens.get("S", 0))
                q_ew = float(q_lens.get("E", 0) + q_lens.get("W", 0))

            # Lookahead: add vehicles currently in transit toward this junction
            if use_lookahead and hasattr(simulator, "in_transit"):
                for (u, v), trans_vehs in simulator.in_transit.items():
                    if v == i and trans_vehs:
                        target_app = self.network.graph[u][v].get("target_approach", "N")
                        added_load = w_lookahead * len(trans_vehs)
                        if target_app in ("N", "S"):
                            q_ns += added_load
                        else:
                            q_ew += added_load
            
            # cost_i = w_queue * [ q_ew + (q_ns - q_ew)*x_i ]
            C0 += w_queue * q_ew
            Q[i, i] += w_queue * (q_ns - q_ew)


        # 2. Quadratic coupling between connected neighbors for green waves
        for u, v in self.network.graph.edges:
            if u < v:  # Process each undirected connection once
                edge_data = self.network.graph[u][v]
                direction = edge_data["direction"]
                
                # Both connected along East-West (same row) or North-South (same col)
                # Coordination penalty when phases mismatch: w_coord * (x_u - x_v)^2
                # (x_u - x_v)^2 = x_u + x_v - 2*x_u*x_v
                Q[u, u] += w_coord
                Q[v, v] += w_coord
                Q[u, v] -= w_coord
                Q[v, u] -= w_coord

        # 3. Spillback penalty: discharging into full downstream road
        for u in range(self.n):
            for v in self.network.graph.neighbors(u):
                edge = self.network.graph[u][v]
                cap = edge["capacity"]
                if cap <= 0:
                    continue
                
                target_app = edge["target_approach"]
                current_load = (
                    len(simulator.in_transit.get((u, v), [])) +
                    len(simulator.queues[v].get(target_app, []))
                )
                
                if current_load >= cap * spill_thresh:
                    direction = edge["direction"]
                    # If road is East-West: u discharges on EW (x_u=1), v drains on EW (x_v=1)
                    # Hazard when x_u = 1 and x_v = 0: x_u*(1 - x_v) = x_u - x_u*x_v
                    if direction in ("E", "W"):
                        Q[u, u] += w_spill
                        Q[u, v] -= w_spill / 2.0
                        Q[v, u] -= w_spill / 2.0
                    # If road is North-South: u discharges on NS (x_u=0), v drains on NS (x_v=0)
                    # Hazard when x_u = 0 and x_v = 1: (1 - x_u)*x_v = x_v - x_u*x_v
                    elif direction in ("N", "S"):
                        Q[v, v] += w_spill
                        Q[u, v] -= w_spill / 2.0
                        Q[v, u] -= w_spill / 2.0

        # 3b. Optional throughput coupling term: for directed link u->v,
        # u discharging toward v is more effective if v is also green for that approach
        w_tc = getattr(self.config.qubo, "w_throughput_coupling", 0.0)
        if w_tc > 0.0:
            app_map = {"E": "W", "W": "E", "S": "N", "N": "S"}
            for u in range(self.n):
                for v in self.network.graph.neighbors(u):
                    edge = self.network.graph[u][v]
                    direction = edge.get("direction", "E")
                    app_u = app_map.get(direction, "W")
                    load = (
                        len(simulator.queues[u].get(app_u, [])) +
                        len(simulator.in_transit.get((u, v), []))
                    )
                    if load <= 0:
                        continue
                    coeff = w_tc * load
                    if direction in ("E", "W"):
                        # Coordinated EW green: benefit when x_u = 1 and x_v = 1
                        # Term: -coeff * x_u * x_v
                        Q[u, v] -= coeff / 2.0
                        Q[v, u] -= coeff / 2.0
                    elif direction in ("N", "S"):
                        # Coordinated NS green: benefit when x_u = 0 and x_v = 0
                        # Term: -coeff * (1 - x_u)*(1 - x_v) = -coeff * (1 - x_u - x_v + x_u*x_v)
                        C0 -= coeff
                        Q[u, u] += coeff
                        Q[v, v] += coeff
                        Q[u, v] -= coeff / 2.0
                        Q[v, u] -= coeff / 2.0

        # 3c. Optional downstream-space term for spillback based on remaining capacity
        use_space = getattr(self.config.qubo, "use_downstream_space", False)
        w_space = getattr(self.config.qubo, "w_downstream_space", 0.5)
        if use_space and w_space > 0.0:
            for u in range(self.n):
                for v in self.network.graph.neighbors(u):
                    edge = self.network.graph[u][v]
                    cap = edge.get("capacity", 20)
                    if cap <= 0:
                        continue
                    target_app = edge.get("target_approach", "N")
                    current_load = (
                        len(simulator.in_transit.get((u, v), [])) +
                        len(simulator.queues[v].get(target_app, []))
                    )
                    rem_space = max(0.0, float(cap - current_load)) / float(cap)
                    space_penalty = w_space * (1.0 - rem_space)
                    direction = edge.get("direction", "E")
                    if direction in ("E", "W"):
                        Q[u, u] += space_penalty
                    elif direction in ("N", "S"):
                        C0 += space_penalty
                        Q[u, u] -= space_penalty

        # 4. Emergency Green Corridor preemption bias
        if emergency_biases:
            for node, req_dir in emergency_biases.items():
                if 0 <= node < self.n:
                    if req_dir == "NS":
                        # Strongly favor x_node = 0 (penalize x_node = 1)
                        Q[node, node] += w_emerg
                    elif req_dir == "EW":
                        # Strongly favor x_node = 1 (penalize x_node = 0)
                        # Penalty: w_emerg * (1 - x_node) = w_emerg - w_emerg * x_node
                        C0 += w_emerg
                        Q[node, node] -= w_emerg

        # 5. Pedestrian demand and wait penalty:
        w_ped = getattr(self.config.qubo, "w_pedestrian", 2.0)
        max_ped_wait_sec = getattr(getattr(self.config, "pedestrian", None), "max_wait_sec", 45)
        if hasattr(simulator, "get_pedestrian_counts"):
            for i in range(self.n):
                ped_counts = simulator.get_pedestrian_counts(i)
                ped_ns = ped_counts.get("NS", 0)
                ped_ew = ped_counts.get("EW", 0)

                # Check if pedestrian max wait threshold exceeded -> add urgency bias
                if hasattr(simulator, "get_pedestrian_max_wait"):
                    max_waits = simulator.get_pedestrian_max_wait(i)
                    if max_waits.get("NS", 0) >= max_ped_wait_sec:
                        ped_ns += 20
                    if max_waits.get("EW", 0) >= max_ped_wait_sec:
                        ped_ew += 20

                # NS green (x_i=0) serves NS peds. EW green (x_i=1) serves EW peds.
                # Penalty: w_ped * [ ped_ew * (1 - x_i) + ped_ns * x_i ]
                C0 += w_ped * ped_ew
                Q[i, i] += w_ped * (ped_ns - ped_ew)

        # 6. Switching penalty: cost for changing current phase (stabilizes phase flipping)
        w_switch = getattr(self.config.qubo, "w_switch", 2.5)
        if w_switch > 0 and hasattr(simulator, "signal_phases"):
            for i in range(self.n):
                current_phase = simulator.signal_phases.get(i, 0)
                if current_phase == 0:
                    # Current is NS (0). Switching to EW (1) costs w_switch * x_i
                    Q[i, i] += w_switch
                else:
                    # Current is EW (1). Switching to NS (0) costs w_switch * (1 - x_i) = w_switch - w_switch * x_i
                    C0 += w_switch
                    Q[i, i] -= w_switch

        return Q, float(C0)

    @staticmethod
    def evaluate_qubo(Q: np.ndarray, C0: float, x: np.ndarray) -> float:
        """Evaluates QUBO cost: x^T Q x + C0."""
        return float(x.T @ Q @ x + C0)

    @staticmethod
    def count_nonzero_interactions(Q: np.ndarray, tol: float = 1e-6) -> int:
        """Counts the number of non-zero quadratic interaction terms J_ij (i < j) in the Ising Hamiltonian."""
        from traffic_quantum.quantum.ising import QUBOToIsingConverter
        _, J, _ = QUBOToIsingConverter.qubo_to_ising(Q, 0.0)
        n = Q.shape[0]
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                if abs(J[i, j]) > tol:
                    count += 1
        return count

