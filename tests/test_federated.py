"""Tests for Week 12 federated learning communication model."""

import numpy as np
import pytest

from wsnsim.models.federated import (
    FederatedConfig,
    estimate_centralized_comm_bytes,
    estimate_fl_comm_bytes,
    fedavg,
    run_federated_simulation,
)


def test_fedavg_returns_unweighted_average():
    result = fedavg([[1.0, 3.0], [3.0, 5.0], [5.0, 7.0]])

    np.testing.assert_allclose(result, [3.0, 5.0])


def test_fedavg_returns_weighted_average():
    result = fedavg([[0.0, 10.0], [10.0, 20.0]], weights=[1.0, 3.0])

    np.testing.assert_allclose(result, [7.5, 17.5])


def test_communication_cost_increases_with_model_nodes_and_rounds():
    base = estimate_fl_comm_bytes(n_nodes=2, model_size_params=4, rounds=3)[2]
    more_nodes = estimate_fl_comm_bytes(n_nodes=3, model_size_params=4, rounds=3)[2]
    larger_model = estimate_fl_comm_bytes(n_nodes=2, model_size_params=8, rounds=3)[2]
    more_rounds = estimate_fl_comm_bytes(n_nodes=2, model_size_params=4, rounds=4)[2]

    assert more_nodes > base
    assert larger_model > base
    assert more_rounds > base


def test_deterministic_seed_gives_repeatable_results():
    config = FederatedConfig(seed=77, n_nodes=8, model_size_params=4, rounds=6)

    first = run_federated_simulation(config)
    second = run_federated_simulation(config)

    np.testing.assert_allclose(first.global_model, second.global_model)
    assert first.total_fl_bytes == second.total_fl_bytes
    assert first.proxy_loss == pytest.approx(second.proxy_loss)
    assert first.round_metrics == second.round_metrics


def test_fl_cost_is_lower_than_centralized_raw_upload_in_documented_scenario():
    config = FederatedConfig(
        n_nodes=25,
        model_size_params=8,
        rounds=10,
        samples_per_node=250,
        raw_sample_bytes=16,
    )
    result = run_federated_simulation(config)

    centralized = estimate_centralized_comm_bytes(
        n_nodes=config.n_nodes,
        samples_per_node=config.samples_per_node,
        raw_sample_bytes=config.raw_sample_bytes,
        message_overhead_bytes=config.message_overhead_bytes,
    )

    assert result.total_fl_bytes < centralized
    assert result.communication_saving_ratio > 0.0


def test_proxy_loss_improves_in_controlled_toy_scenario():
    config = FederatedConfig(
        seed=1,
        n_nodes=6,
        model_size_params=3,
        rounds=5,
        local_steps=1,
        learning_rate=0.5,
        local_stat_std=0.0,
        participation_rate=1.0,
    )

    result = run_federated_simulation(config)
    losses = [round_metric.proxy_loss for round_metric in result.round_metrics]

    assert losses[-1] < losses[0]
    assert result.distance_to_target < result.round_metrics[0].distance_to_target
