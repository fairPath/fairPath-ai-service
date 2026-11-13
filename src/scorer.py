"""The Scorer: pure code that turns component values into Scores."""
import math
from collections.abc import Mapping
from fractions import Fraction

from analysis_config import WEIGHTS
from contract import Category, Scores

# Component values are shares such as 3/5; as floats (0.6) they carry binary
# error that can push an exact .5 below the rounding line. Score in exact
# fractions instead, recovering each value as the nearest simple fraction.
_MAX_DENOMINATOR = 10**6


def _exact(value: float) -> Fraction:
    return Fraction(value).limit_denominator(_MAX_DENOMINATOR)


def _round_half_up(x: Fraction) -> int:
    return math.floor(x + Fraction(1, 2))


def score(
    values: Mapping[str, float | None],
    weights: Mapping[Category, Mapping[str, int]] = WEIGHTS,
) -> Scores:
    """Score each Category as round(100 × Σ weight·value / Σ weight).

    `values` maps a component name to a value in [0, 1], or None when the
    component is not applicable. Components missing from `values` (not built
    yet) and None values drop out of both sums. A Category with nothing left
    scores 100: nothing was found wrong. Overall is the equal-weight average
    of the three Category Scores.
    """
    known = {component for components in weights.values() for component in components}
    unknown = set(values) - known
    if unknown:
        raise KeyError(f"Unknown score components: {sorted(unknown)}")

    category_scores: dict[str, int] = {}
    for category, components in weights.items():
        applicable = [
            (weight, _exact(values[name]))
            for name, weight in components.items()
            if values.get(name) is not None
        ]
        total_weight = sum(weight for weight, _ in applicable)
        if total_weight == 0:
            category_scores[category] = 100
        else:
            weighted = sum(weight * value for weight, value in applicable)
            category_scores[category] = _round_half_up(100 * weighted / total_weight)

    overall = _round_half_up(Fraction(sum(category_scores.values()), len(category_scores)))
    return Scores(**category_scores, overall=overall)
