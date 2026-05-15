"""Tests for Week 13 design-space optimization helpers."""

from wsnsim.models.optimization import (
    DesignPoint,
    Objective,
    OptimizationResult,
    dominates,
    grid_search,
    pareto_front,
)


OBJECTIVES = [
    Objective("pdr", "maximize"),
    Objective("energy_per_delivered_packet", "minimize"),
]


def _result(
    config_id: str,
    *,
    pdr: float,
    energy: float,
) -> OptimizationResult:
    return OptimizationResult(
        design_point=DesignPoint(config_id, {}),
        metrics={
            "pdr": pdr,
            "energy_per_delivered_packet": energy,
        },
    )


def test_better_design_point_dominates_worse_one():
    better = _result("better", pdr=0.95, energy=0.20)
    worse = _result("worse", pdr=0.90, energy=0.30)

    assert dominates(better, worse, OBJECTIVES)
    assert not dominates(worse, better, OBJECTIVES)


def test_tradeoff_point_is_not_incorrectly_dominated():
    reliable = _result("reliable", pdr=0.98, energy=0.40)
    efficient = _result("efficient", pdr=0.90, energy=0.20)

    assert not dominates(reliable, efficient, OBJECTIVES)
    assert not dominates(efficient, reliable, OBJECTIVES)


def test_pareto_front_returns_expected_subset():
    reliable = _result("reliable", pdr=0.98, energy=0.40)
    efficient = _result("efficient", pdr=0.90, energy=0.20)
    dominated = _result("dominated", pdr=0.85, energy=0.50)

    front = pareto_front([reliable, efficient, dominated], OBJECTIVES)

    assert {result.config_id for result in front} == {"reliable", "efficient"}


def test_objective_directions_are_respected_for_minimize_and_maximize():
    low_latency_objectives = [
        Objective("pdr", "maximize"),
        Objective("latency_mean", "minimize"),
    ]
    faster = OptimizationResult(
        DesignPoint("faster", {}),
        {"pdr": 0.90, "latency_mean": 0.10},
    )
    slower = OptimizationResult(
        DesignPoint("slower", {}),
        {"pdr": 0.90, "latency_mean": 0.25},
    )

    assert dominates(faster, slower, low_latency_objectives)
    assert not dominates(slower, faster, low_latency_objectives)


def test_grid_search_evaluates_all_parameter_combinations():
    seen: list[dict[str, object]] = []

    def evaluator(point: DesignPoint) -> dict[str, float]:
        seen.append(dict(point.parameters))
        return {"score": float(len(seen))}

    results = grid_search(
        {"mac": ["aloha", "csma"], "retry_limit": [0, 2, 4]},
        evaluator,
    )

    assert len(results) == 6
    assert len(seen) == 6
    assert results[0].config_id == "cfg_001"
    assert seen[0] == {"mac": "aloha", "retry_limit": 0}
    assert seen[-1] == {"mac": "csma", "retry_limit": 4}


def test_deterministic_seed_in_grid_gives_repeatable_results():
    def evaluator(point: DesignPoint) -> dict[str, float]:
        seed = int(point.parameters["seed"])
        retry_limit = int(point.parameters["retry_limit"])
        return {"score": float(seed + retry_limit)}

    grid = {"seed": [7], "retry_limit": [0, 3]}

    first = grid_search(grid, evaluator)
    second = grid_search(grid, evaluator)

    assert first == second
