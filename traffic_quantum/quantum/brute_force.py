"""Exact Brute-Force Optimizer for QUBO verification and classical comparison."""

import itertools
from typing import Dict, List, Optional, Tuple
import numpy as np


class BruteForceOptimizer:
    """Solves small QUBO instances exactly by evaluating all 2^n possible configurations."""

    @staticmethod
    def solve(Q: np.ndarray, C0: float = 0.0) -> Tuple[np.ndarray, float, List[Tuple[np.ndarray, float]]]:
        """Exhaustively searches all 2^n bitstrings for the minimum cost configuration.
        
        Args:
            Q: QUBO matrix of shape (n, n)
            C0: scalar constant offset
            
        Returns:
            best_x: 1D np.ndarray of optimal binary variables
            min_cost: minimum objective cost
            sorted_all: list of (x, cost) tuples ordered by increasing cost
        """
        n = Q.shape[0]
        results = []

        for combo in itertools.product([0, 1], repeat=n):
            x = np.array(combo, dtype=np.float64)
            cost = float(x.T @ Q @ x + C0)
            results.append((np.array(combo, dtype=np.int32), cost))

        results.sort(key=lambda item: item[1])
        best_x, min_cost = results[0]
        return best_x, min_cost, results
