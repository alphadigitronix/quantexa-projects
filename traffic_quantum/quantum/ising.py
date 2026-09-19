"""Conversion from QUBO formulation to Ising Hamiltonian.

Uses the transformation:
    x_i = (1 - Z_i) / 2
where x_i in {0, 1} and Z_i in {+1, -1}.

Yields the standard Ising Hamiltonian:
    H(Z) = sum_{i < j} J_ij Z_i Z_j + sum_i h_i Z_i + C_offset
such that:
    x^T Q x + C0 == H(Z)  for all bitstrings.
"""

from typing import Dict, Tuple
import numpy as np


class QUBOToIsingConverter:
    """Converts a QUBO matrix and offset into Ising h, J couplings and constant offset."""

    @staticmethod
    def qubo_to_ising(Q: np.ndarray, C0: float = 0.0) -> Tuple[np.ndarray, np.ndarray, float]:
        """Converts QUBO matrix Q (n x n) and constant offset C0 to Ising Hamiltonian.
        
        Args:
            Q: np.ndarray of shape (n, n)
            C0: scalar constant offset
            
        Returns:
            h: 1D np.ndarray of shape (n,) containing single-qubit longitudinal fields
            J: 2D np.ndarray of shape (n, n) where J[i, j] for i < j are interaction couplings
            offset: float constant energy shift
        """
        n = Q.shape[0]
        # Symmetrize Q
        S = (Q + Q.T) / 2.0
        
        h = np.zeros(n, dtype=np.float64)
        J = np.zeros((n, n), dtype=np.float64)
        
        # J_ij = S_ij / 2 for i < j
        for i in range(n):
            for j in range(i + 1, n):
                J[i, j] = S[i, j] / 2.0
                J[j, i] = J[i, j]  # Symmetric storage for convenience

        # h_i = -S_ii / 2 - sum_{j != i} (S_ij / 2)
        for i in range(n):
            sum_cross = sum(S[i, j] / 2.0 for j in range(n) if j != i)
            h[i] = -(S[i, i] / 2.0) - sum_cross

        # Offset = C0 + sum_i (S_ii / 2) + sum_{i < j} (S_ij / 2)
        offset = float(C0) + sum(S[i, i] / 2.0 for i in range(n))
        for i in range(n):
            for j in range(i + 1, n):
                offset += S[i, j] / 2.0

        return h, J, float(offset)

    @staticmethod
    def x_to_z(x: np.ndarray) -> np.ndarray:
        """Maps binary vector x in {0, 1}^n to spin vector Z in {+1, -1}^n."""
        return 1 - 2 * x

    @staticmethod
    def z_to_x(z: np.ndarray) -> np.ndarray:
        """Maps spin vector Z in {+1, -1}^n to binary vector x in {0, 1}^n."""
        return (1 - z) // 2

    @staticmethod
    def evaluate_ising(h: np.ndarray, J: np.ndarray, offset: float, z: np.ndarray) -> float:
        """Evaluates Ising energy: sum_{i < j} J_ij Z_i Z_j + sum_i h_i Z_i + offset."""
        n = len(h)
        energy = offset + float(np.dot(h, z))
        for i in range(n):
            for j in range(i + 1, n):
                energy += J[i, j] * z[i] * z[j]
        return float(energy)
