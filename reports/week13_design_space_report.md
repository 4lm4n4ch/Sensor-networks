# Week 13 - Design Space and Optimization

## Goal

Design-space exploration helps compare WSN configurations under competing objectives. Here the simulator evaluates a small deterministic parameter grid and extracts Pareto-efficient configurations that are not strictly worse than another candidate on reliability, energy, latency, and bytes.

## Design variables

- `node_count`: changes contention and total sensing traffic.
- `mac`: compares ALOHA and CSMA behavior.
- `retry_limit`: changes reliability versus retry overhead.
- `radio_range_m`: changes hop count, link budget, and TX energy.
- `aggregation_threshold`: suppresses redundant readings.
- `security_enabled`: adds authentication bytes, CPU energy, and processing latency.

## Objectives

- Maximize `pdr`.
- Minimize `energy_per_delivered_packet`.
- Minimize `latency_mean`.
- Minimize `total_tx_bytes`.

## Method

The experiment uses a deterministic grid with two seeds and 288 total configurations. Each candidate is evaluated with a lightweight analytic WSN model: channel PRR comes from the Week 2 log-distance channel, retry behavior follows the Week 7 link-attempt logic, aggregation reduces generated packets, and Week 10 security settings add byte, CPU-energy, and latency overhead. Pareto dominance means a candidate is at least as good on every objective and strictly better on one objective. Non-dominated candidates form the Pareto front.

## Results

- CSV path: `reports/week13_design_space_optimization.csv`
- Figure: `reports/figures/week13_pareto_energy_vs_pdr.png`
- Figure: `reports/figures/week13_pareto_latency_vs_energy.png`
- Figure: `reports/figures/week13_design_space_scatter.png`
- Evaluated configurations: `288`
- Pareto-efficient configurations: `26`

## Interpretation

Energy-efficient configurations use aggregation and avoid unnecessary security/retry overhead when the channel is already strong. Reliability-oriented configurations favor CSMA, more retries, and larger radio range because those choices improve delivery probability. The balanced recommendation is `cfg_047`: MAC `csma`, retry limit `0`, range `55.0` m, aggregation threshold `0.35`, security `False`. It is recommended because it lies on the Pareto front and has the best average normalized score across the implemented objectives.

The lowest-energy Pareto point is `cfg_039` with `0.000160` J per delivered packet. The highest-reliability Pareto point is `cfg_071` with PDR `0.960`.

## Reproducibility

```bash
.venv/bin/python -m pytest -q tests/test_optimization.py
.venv/bin/python experiments/week13_design_space_optimization.py
```

## Known limitations

- The parameter grid is intentionally small.
- The evaluator is analytic and simplified rather than a full packet-level end-to-end simulation.
- Stochastic repetition is limited to two deterministic seeds.
- No advanced optimizer or metaheuristic is used.
- The model is not calibrated against a real deployment.
