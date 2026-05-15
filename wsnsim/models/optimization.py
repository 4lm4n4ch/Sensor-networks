"""Week 13 design-space exploration and Pareto optimization helpers.

The module is intentionally small and deterministic. It provides generic
multi-objective utilities that can be reused by experiments without depending
on a heavy optimization library.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Literal, Mapping, Sequence


ObjectiveDirection = Literal["minimize", "maximize"]


@dataclass(frozen=True)
class Objective:
    """One scalar optimization objective and its preferred direction."""

    name: str
    direction: ObjectiveDirection

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("objective name must not be empty")
        if self.direction not in ("minimize", "maximize"):
            raise ValueError("direction must be 'minimize' or 'maximize'")


@dataclass(frozen=True)
class DesignPoint:
    """One candidate configuration in a parameter sweep."""

    config_id: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.config_id:
            raise ValueError("config_id must not be empty")


@dataclass(frozen=True)
class OptimizationResult:
    """Metrics produced by evaluating one design point."""

    design_point: DesignPoint
    metrics: Mapping[str, float]

    @property
    def config_id(self) -> str:
        """Return the design-point identifier for convenience."""
        return self.design_point.config_id


Evaluator = Callable[[DesignPoint], Mapping[str, float] | OptimizationResult]


def dominates(
    a: OptimizationResult,
    b: OptimizationResult,
    objectives: Sequence[Objective],
) -> bool:
    """Return True when ``a`` Pareto-dominates ``b`` for all objectives."""
    if not objectives:
        raise ValueError("objectives must not be empty")

    strictly_better = False
    for objective in objectives:
        a_value = _metric_value(a, objective.name)
        b_value = _metric_value(b, objective.name)
        if objective.direction == "maximize":
            if a_value < b_value:
                return False
            if a_value > b_value:
                strictly_better = True
        else:
            if a_value > b_value:
                return False
            if a_value < b_value:
                strictly_better = True

    return strictly_better


def pareto_front(
    results: Sequence[OptimizationResult],
    objectives: Sequence[Objective],
) -> list[OptimizationResult]:
    """Return the non-dominated subset of evaluated design points."""
    return [
        candidate
        for candidate in results
        if not any(
            dominates(other, candidate, objectives)
            for other in results
            if other is not candidate
        )
    ]


def grid_search(
    parameter_grid: Mapping[str, Sequence[Any]],
    evaluator: Evaluator,
) -> list[OptimizationResult]:
    """Evaluate every parameter combination in deterministic insertion order."""
    if not parameter_grid:
        raise ValueError("parameter_grid must not be empty")

    names = list(parameter_grid)
    values = []
    for name in names:
        options = list(parameter_grid[name])
        if not options:
            raise ValueError(f"parameter grid entry '{name}' must not be empty")
        values.append(options)

    results: list[OptimizationResult] = []
    for index, combination in enumerate(product(*values), start=1):
        parameters = dict(zip(names, combination))
        design_point = DesignPoint(
            config_id=f"cfg_{index:03d}",
            parameters=parameters,
        )
        evaluated = evaluator(design_point)
        if isinstance(evaluated, OptimizationResult):
            results.append(evaluated)
        else:
            results.append(
                OptimizationResult(
                    design_point=design_point,
                    metrics=dict(evaluated),
                )
            )
    return results


def dominance_counts(
    results: Sequence[OptimizationResult],
    objectives: Sequence[Objective],
) -> dict[str, tuple[int, int]]:
    """Return ``config_id -> (dominates_count, dominated_by_count)``."""
    counts: dict[str, tuple[int, int]] = {}
    for candidate in results:
        dominates_count = sum(
            1
            for other in results
            if other is not candidate and dominates(candidate, other, objectives)
        )
        dominated_by_count = sum(
            1
            for other in results
            if other is not candidate and dominates(other, candidate, objectives)
        )
        counts[candidate.config_id] = (dominates_count, dominated_by_count)
    return counts


def normalize_objectives(
    results: Sequence[OptimizationResult],
    objectives: Sequence[Objective],
) -> dict[str, dict[str, float]]:
    """Return min-max normalized objective scores where larger is better."""
    if not results:
        return {}

    normalized: dict[str, dict[str, float]] = {
        result.config_id: {} for result in results
    }
    for objective in objectives:
        values = [_metric_value(result, objective.name) for result in results]
        minimum = min(values)
        maximum = max(values)
        span = maximum - minimum
        for result, value in zip(results, values):
            if span == 0.0:
                score = 1.0
            elif objective.direction == "maximize":
                score = (value - minimum) / span
            else:
                score = (maximum - value) / span
            normalized[result.config_id][objective.name] = score
    return normalized


def rank_pareto_candidates(
    results: Sequence[OptimizationResult],
    objectives: Sequence[Objective],
) -> list[OptimizationResult]:
    """Rank candidates by Pareto status and normalized balanced score."""
    counts = dominance_counts(results, objectives)
    front_ids = {result.config_id for result in pareto_front(results, objectives)}
    normalized = normalize_objectives(results, objectives)

    def sort_key(result: OptimizationResult) -> tuple[int, float, int, str]:
        scores = normalized.get(result.config_id, {})
        mean_score = (
            sum(scores.values()) / len(scores)
            if scores
            else 0.0
        )
        dominates_count, dominated_by_count = counts[result.config_id]
        pareto_score = 0 if result.config_id in front_ids else 1
        return (pareto_score, -mean_score, -dominates_count, result.config_id)

    return sorted(results, key=sort_key)


def _metric_value(result: OptimizationResult, name: str) -> float:
    """Return one metric as a float, raising a clear error if missing."""
    if name not in result.metrics:
        raise KeyError(f"missing objective metric '{name}'")
    return float(result.metrics[name])
