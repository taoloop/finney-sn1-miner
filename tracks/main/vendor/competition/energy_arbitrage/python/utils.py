"""Utility functions: GP kernel, Cholesky decomposition, matrix inversion."""

import math

# TaoLoop line modification: upstream imports numpy unconditionally. When numpy is
# missing (offline hosts) the pure-Python fallbacks below are used instead. Scores
# differ from the numpy path only by float rounding; install the pinned
# requirements.txt to match the evaluator image exactly.
try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only without numpy
    np = None
from competition.energy_arbitrage.python import constants


class GPKernel:
    """Gaussian Process kernel for price generation."""

    def __init__(self):
        self.sigma_periodic: float = 10.0
        self.length_periodic: float = 2.0
        self.sigma_se: float = 5.0
        self.length_se: float = 4.0
        self.period_hours: float = 24.0

    def evaluate(self, t1: float, t2: float) -> float:
        # Convert step indices to hours
        h1 = t1 * constants.DELTA_T
        h2 = t2 * constants.DELTA_T
        tau = abs(h1 - h2)

        # Periodic component
        periodic = (self.sigma_periodic**2) * math.exp(
            -2.0 * math.sin(math.pi * tau / self.period_hours) ** 2 / self.length_periodic**2
        )

        # Squared exponential component
        se = (self.sigma_se**2) * math.exp(-(tau**2) / (2.0 * self.length_se**2))

        return periodic + se

    def covariance_matrix(self, n: int) -> list[list[float]]:
        k = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                k[i][j] = self.evaluate(float(i), float(j))
                if i == j:
                    k[i][j] += 1e-6  # Numerical stability
        return k


def cholesky(a: list[list[float]]) -> list[list[float]]:
    """Cholesky decomposition (lower triangular) using numpy."""
    n = len(a)
    if n == 0:
        return []
    if np is None:
        return _cholesky_py(a)
    matrix = np.array(a, dtype=np.float64)
    l_matrix = np.linalg.cholesky(matrix)
    return l_matrix.tolist()


def invert_matrix(a: list[list[float]]) -> list[list[float]]:
    """Matrix inversion via Cholesky decomposition (for symmetric positive definite matrices)."""
    n = len(a)
    if n == 0:
        return []
    if np is None:
        return _invert_spd_py(a)
    matrix = np.array(a, dtype=np.float64)
    l_matrix = np.linalg.cholesky(matrix)
    l_inv = np.linalg.inv(l_matrix)
    inverse = l_inv.T @ l_inv
    return inverse.tolist()


def _cholesky_py(a: list[list[float]]) -> list[list[float]]:
    """Pure-Python Cholesky (lower triangular); TaoLoop fallback when numpy is absent."""
    n = len(a)
    l_mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        row_i = l_mat[i]
        for j in range(i + 1):
            row_j = l_mat[j]
            s = a[i][j] - math.fsum(row_i[k] * row_j[k] for k in range(j))
            if i == j:
                if s <= 0.0:
                    raise ValueError("Matrix is not positive definite")
                row_i[j] = math.sqrt(s)
            else:
                row_i[j] = s / row_j[j]
    return l_mat


def _invert_spd_py(a: list[list[float]]) -> list[list[float]]:
    """Pure-Python SPD inverse via Cholesky; TaoLoop fallback when numpy is absent."""
    n = len(a)
    l_mat = _cholesky_py(a)
    # Invert the lower-triangular factor by forward substitution.
    l_inv = [[0.0] * n for _ in range(n)]
    for i in range(n):
        l_inv[i][i] = 1.0 / l_mat[i][i]
        for j in range(i):
            s = sum(l_mat[i][k] * l_inv[k][j] for k in range(j, i))
            l_inv[i][j] = -s / l_mat[i][i]
    # inverse = L^-T L^-1
    inv = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            v = sum(l_inv[k][i] * l_inv[k][j] for k in range(j, n))
            inv[i][j] = v
            inv[j][i] = v
    return inv
