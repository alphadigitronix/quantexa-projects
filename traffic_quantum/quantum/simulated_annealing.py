"""Classical Simulated Annealing Solver for Traffic QUBO.

Provides a heuristic classical baseline for solving the traffic QUBO matrix,
allowing direct comparison of solution quality, convergence, and execution time
against exact Brute Force and PennyLane QAOA.
"""

import math
import random
import time
from typing import Dict, List, Optional, Tuple
import numpy as np


class SimulatedAnnealingOptimizer:
    """Classical Simulated Annealing optimizer for binary quadratic problems (QUBO)."""

    @staticmethod
    def solve(
        Q: np.ndarray,
        C0: float = 0.0,
        initial_temp: float = 15.0,
        final_temp: float = 0.05,
        cooling_rate: float = 0.92,
        steps_per_temp: int = 15,
        seed: Optional[int] = None,
    ) -> Tuple[np.ndarray, float, Dict[str, object]]:
        """Solves the QUBO via simulated annealing with Metropolis-Hastings acceptance.
        
        Cost function: Cost(x) = x^T Q x + C0
        
        Args:
            Q: QUBO matrix of shape (n, n)
            C0: scalar offset
            initial_temp: starting annealing temperature
            final_temp: termination temperature
            cooling_rate: geometric temperature decay factor
            steps_per_temp: Metropolis iterations per temperature step
            seed: random seed for determinism
            
        Returns:
            Tuple of (best_bitstring, best_cost, metadata_dict)
        """
        rng = random.Random(seed)
        n = Q.shape[0]
        start_time = time.time()

        # Initial random bitstring
        current_x = np.array([rng.randint(0, 1) for _ in range(n)], dtype=np.float64)
        current_cost = float(current_x.T @ Q @ current_x + C0)

        best_x = current_x.copy()
        best_cost = current_cost

        T = initial_temp
        step_count = 0

        while T > final_temp:
            for _ in range(steps_per_temp):
                step_count += 1
                # Single-bit flip neighborhood
                flip_idx = rng.randint(0, n - 1)
                candidate_x = current_x.copy()
                candidate_x[flip_idx] = 1.0 - candidate_x[flip_idx]

                candidate_cost = float(candidate_x.T @ Q @ candidate_x + C0)
                delta_e = candidate_cost - current_cost

                # Metropolis acceptance criterion
                if delta_e < 0.0 or rng.random() < math.exp(-delta_e / max(1e-8, T)):
                    current_x = candidate_x
                    current_cost = candidate_cost

                    if current_cost < best_cost:
                        best_cost = current_cost
                        best_x = current_x.copy()

            T *= cooling_rate

        runtime_sec = time.time() - start_time
        return best_x.astype(np.int32), best_cost, {
            "solver": "simulated_annealing",
            "best_cost": best_cost,
            "runtime_sec": round(runtime_sec, 5),
            "total_steps": step_count,
            "final_temp": round(T, 4),
        }
