"""
utils/stats.py — Small statistics helpers for honest reporting.

A pass rate from 10 runs is a very rough estimate; these helpers put numbers on
how rough, so the UI can show a range instead of a falsely precise score.
"""

from math import erf, sqrt

Z95 = 1.959964


def wilson_interval(passed: int, total: int, z: float = Z95) -> tuple[float, float]:
    """95% Wilson score interval for a pass rate. Behaves well for small n and
    for rates near 0% or 100%, unlike the plain p ± 1.96·SE formula."""
    if total <= 0:
        return 0.0, 1.0
    p = passed / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def two_proportion_p_value(passed_a: int, total_a: int, passed_b: int, total_b: int) -> float | None:
    """Two-sided p-value for "pass rate A differs from pass rate B" (pooled z-test).
    Returns None when either side has no runs. Small p (< 0.05) means the
    difference is unlikely to be just run-to-run noise."""
    if total_a <= 0 or total_b <= 0:
        return None
    pooled = (passed_a + passed_b) / (total_a + total_b)
    se = sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    if se == 0:
        return 1.0
    z = abs(passed_a / total_a - passed_b / total_b) / se
    # two-sided tail of the standard normal
    return max(0.0, min(1.0, 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))))
