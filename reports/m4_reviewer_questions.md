# M4 Reviewer Questions

## Why did you choose the final design point?

`alt_C_balanced` is Pareto-efficient in `reports/m4_final_results.csv`. It keeps
high PDR while enabling replay protection and using aggregation plus Edge AI to
reduce transmitted bytes and energy relative to the reliability-only design.

## What does the Pareto front optimize?

The M4 objectives are:

- maximize `pdr`;
- minimize `energy_per_delivered_packet`;
- minimize `latency_mean`;
- minimize `total_tx_bytes`;
- maximize `security_coverage`.

## How is randomness controlled?

The final config fixes seed `42069` in `configs/m4_final.json`. The experiment
dumps the exact config used to `reports/m4_final_config_dump.json`.

## What is simplified?

The M4 integration is analytic rather than a full packet-level cross-layer
simulation. Radio propagation, MAC contention, ARQ, aggregation, security, Edge
AI, Federated Learning, and energy are simplified and not hardware-calibrated.

## How can the results be reproduced?

```bash
python -m pytest -q
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

Use an environment with dependencies from `requirements.txt` installed.

## What would you improve next?

Add calibrated radio/energy parameters, larger topologies, repeated stochastic
trials, full packet-level cross-layer integration, stronger security models,
and more realistic Edge AI/Federated Learning workloads.
