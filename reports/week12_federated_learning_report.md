# Week 12 - Federated Learning in WSN

## Goal

Federated Learning is relevant for WSNs because sensor nodes can keep raw measurements local and exchange compact model updates with a sink or gateway. This Week 12 model focuses on the communication trade-off: repeated model upload/download messages versus one centralized upload of all raw samples.

## Implemented module

`wsnsim.models.federated` implements `FederatedConfig`, `FederatedNode`, `FederatedServer`, `fedavg`, `estimate_fl_comm_bytes`, `estimate_centralized_comm_bytes`, and `run_federated_simulation`. Nodes hold deterministic local target vectors, perform simple local movement toward those targets, and the server aggregates participating model vectors with sample-weighted FedAvg.

## Simulation setup

- Number of nodes: `25`
- Model size: `8` parameters
- Rounds: `20`
- Local update rule: `2` steps with learning rate `0.35` toward local synthetic statistics
- Update-period sweep: `1, 2, 4, 5` rounds
- Participation rate: `1.0`
- Deterministic seed: `2026`

## Communication cost model

Each FL model message costs:

```text
message_overhead_bytes + model_size_params * bytes_per_param
```

For each active communication round, participating nodes download the global model and upload a local model update. The centralized baseline uploads all raw samples once:

```text
n_nodes * samples_per_node * (raw_sample_bytes + overhead)
```

This is a simplified byte model: it does not simulate packet loss, MAC contention, routing hops, or compression.

## Results

- CSV path: `reports/week12_federated_learning.csv`
- Figure: `reports/figures/week12_update_period_vs_comm_cost.png`
- Figure: `reports/figures/week12_rounds_vs_convergence.png`
- Figure: `reports/figures/week12_fl_vs_centralized_comm_cost.png`
- Figure: `reports/figures/week12_comm_cost_vs_proxy_accuracy.png`
- Best proxy accuracy: update period `1` with accuracy `1.000` and FL bytes `48000`.
- Lowest FL communication: update period `5` with FL bytes `9600` and proxy accuracy `0.917`.

## Interpretation

FL saves communication when the model exchanged over several rounds is smaller than the raw sensor history. Increasing the update period reduces active communication rounds, so byte cost falls. The remaining cost is repeated model broadcast and model upload. The proxy convergence metric shows the expected trade-off: less frequent updates save bytes but usually leave the global model farther from the synthetic target.

## Reproducibility

```bash
.venv/bin/python -m pytest -q tests/test_federated.py
.venv/bin/python experiments/week12_federated_learning.py
```

## Known limitations

- Toy numeric model, not a trained neural network.
- Simplified local learning toward synthetic statistics.
- No real privacy guarantee or secure aggregation.
- No wireless contention, routing-hop, or packet-loss model.
- No integration with Week 10 security overhead.
