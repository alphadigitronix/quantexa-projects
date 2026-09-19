"""PennyLane QAOA (Quantum Approximate Optimization Algorithm) Solver for Traffic QUBO.

Manually implements:
1. Hadamard state initialization
2. Cost Hamiltonian layer e^{-i gamma H_C} using RZ for h_i and CNOT-RZ-CNOT for J_ij
3. Mixer Hamiltonian layer e^{-i beta H_M} using RX
No black-box QAOA solvers are used so that each gate and parameter is fully transparent.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pennylane as qml
from scipy.optimize import minimize

from traffic_quantum.config import DEFAULT_CONFIG, MasterConfig
from traffic_quantum.quantum.ising import QUBOToIsingConverter
from traffic_quantum.quantum.qubo import TrafficQUBOBuilder


class QAOATrafficSolver:
    """Manual PennyLane QAOA implementation for multi-intersection traffic optimization."""

    def __init__(self, num_qubits: int, config: Optional[MasterConfig] = None):
        self.n = num_qubits
        self.config = config or DEFAULT_CONFIG
        self.p = self.config.qaoa.p_layers
        self.dev = qml.device(self.config.qaoa.device_name, wires=self.n)
        self.warm_start_params: Optional[np.ndarray] = None
        self.precomputed_bitstrings = self._generate_all_bitstrings(self.n)

    @staticmethod
    def _generate_all_bitstrings(n: int) -> np.ndarray:
        """Precomputes all 2^n binary vectors for fast expectation evaluation."""
        num_states = 1 << n
        bitstrings = np.zeros((num_states, n), dtype=np.int32)
        for i in range(num_states):
            for bit in range(n):
                bitstrings[i, n - 1 - bit] = (i >> bit) & 1
        return bitstrings

    def reset_cache(self) -> None:
        """Clears cached warm-start parameters."""
        self.warm_start_params = None

    def solve(
        self,
        Q: np.ndarray,
        C0: float = 0.0,
        exact_cost: Optional[float] = None,
    ) -> Dict[str, object]:
        """Runs QAOA on the QUBO problem instance.
        
        Args:
            Q: QUBO matrix of shape (n, n)
            C0: scalar constant offset
            exact_cost: optional ground-truth exact cost for approximation ratio logging
            
        Returns:
            Dictionary containing best bitstring, cost, probabilities, and approximation metrics.
        """
        # 1. Convert QUBO to Ising formulation
        h, J, offset = QUBOToIsingConverter.qubo_to_ising(Q, C0)
        
        # 2. Precompute QUBO costs for all 2^n states to evaluate expectation value fast
        all_x = self.precomputed_bitstrings
        costs = np.array([
            TrafficQUBOBuilder.evaluate_qubo(Q, C0, all_x[idx])
            for idx in range(len(all_x))
        ], dtype=np.float64)

        # 3. Define manual PennyLane QNode
        @qml.qnode(self.dev, interface="autograd")
        def qaoa_circuit(angles):
            # angles shape: (2, p) -> gamma = angles[0], beta = angles[1]
            gamma = angles[0]
            beta = angles[1]

            # Initial state: equal superposition |+>^n via Hadamard gates
            for wire in range(self.n):
                qml.Hadamard(wires=wire)

            # Apply p layers of Cost and Mixer unitaries
            for layer in range(self.p):
                g = gamma[layer]
                b = beta[layer]

                # --- Cost Layer: e^{-i gamma H_C} ---
                # Longitudinal single-qubit terms: h_i Z_i -> RZ(2 * g * h_i)
                for i in range(self.n):
                    if abs(h[i]) > 1e-7:
                        qml.RZ(2.0 * g * h[i], wires=i)

                # Two-qubit interaction terms: J_ij Z_i Z_j -> CNOT -> RZ(2 * g * J_ij) -> CNOT
                for i in range(self.n):
                    for j in range(i + 1, self.n):
                        if abs(J[i, j]) > 1e-7:
                            qml.CNOT(wires=[i, j])
                            qml.RZ(2.0 * g * J[i, j], wires=j)
                            qml.CNOT(wires=[i, j])

                # --- Mixer Layer: e^{-i beta H_M} where H_M = sum_i X_i ---
                for i in range(self.n):
                    qml.RX(2.0 * b, wires=i)

            return qml.probs(wires=range(self.n))

        # 4. Objective function for classical optimizer: <H_C> = sum_s P(s) * Cost(s)
        def objective_function(flat_params: np.ndarray) -> float:
            angles = flat_params.reshape((2, self.p))
            probs = qaoa_circuit(angles)
            expected_energy = float(np.dot(probs, costs))
            return expected_energy

        # 5. Initialize parameters (warm-start from previous round or default heuristic)
        if self.config.qaoa.warm_start and self.warm_start_params is not None:
            init_params = self.warm_start_params.copy()
        else:
            # Linear ramp schedule heuristic for initial angles
            gamma_init = np.linspace(0.1, 0.5, self.p)
            beta_init = np.linspace(0.5, 0.1, self.p)
            init_params = np.concatenate([gamma_init, beta_init])

        # 6. Optimize angles classically using COBYLA
        max_iter = self.config.qaoa.max_iterations
        opt_res = minimize(
            objective_function,
            init_params,
            method="COBYLA",
            options={"maxiter": max_iter, "tol": 1e-3},
        )

        optimal_flat_params = opt_res.x
        if self.config.qaoa.warm_start:
            self.warm_start_params = optimal_flat_params.copy()

        # 7. Sample final probability distribution
        optimal_angles = optimal_flat_params.reshape((2, self.p))
        final_probs = np.array(qaoa_circuit(optimal_angles), dtype=np.float64)

        # 8. Top-k bitstring selection
        top_k = min(self.config.qaoa.top_k_bitstrings, len(final_probs))
        top_indices = np.argsort(final_probs)[::-1][:top_k]

        best_idx = top_indices[0]
        best_cost = costs[best_idx]

        # Inspect top-k most probable to find the lowest-cost bitstring
        for idx in top_indices:
            if costs[idx] < best_cost:
                best_cost = costs[idx]
                best_idx = idx

        best_bitstring = all_x[best_idx]

        # 9. Approximation ratio and exact optimum comparison
        approx_ratio = 1.0
        found_exact = True
        if exact_cost is not None:
            # Shift costs so best cost >= 0 for a meaningful ratio
            min_c = np.min(costs)
            max_c = np.max(costs)
            range_c = max_c - min_c if max_c > min_c else 1.0
            
            # Standard approximation ratio: (max - qaoa) / (max - min)
            approx_ratio = float((max_c - best_cost) / range_c)
            found_exact = bool(abs(best_cost - exact_cost) < 1e-4)

        return {
            "solver": "qaoa",
            "best_bitstring": best_bitstring,
            "best_cost": float(best_cost),
            "exact_cost": float(exact_cost) if exact_cost is not None else None,
            "approximation_ratio": round(approx_ratio, 4),
            "found_exact_optimum": found_exact,
            "probabilities": final_probs,
            "top_indices": top_indices,
            "optimal_gammas": optimal_angles[0].tolist(),
            "optimal_betas": optimal_angles[1].tolist(),
            "p_layers": self.p,
            "qubits": self.n,
        }
