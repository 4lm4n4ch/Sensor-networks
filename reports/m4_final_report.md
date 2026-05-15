# M4 Final Report - wsnsim

## Project overview

`wsnsim` is a modular Python Wireless Sensor Network simulator used to study how radio, MAC, routing, reliability, energy, aggregation, security, Edge AI, Federated Learning, and optimization choices affect WSN performance.

## Implemented modules

- Simulator core and deterministic scheduler.
- Radio channel PRR(distance) model.
- Energy and lifetime accounting.
- ALOHA and simplified CSMA MAC models.
- Topology/connectivity generation.
- Flooding and sink-tree BFS routing.
- ACK/retry reliability.
- Time synchronization and RSSI localization.
- Aggregation and delta compression.
- Replay protection and security overhead.
- Edge AI anomaly detection.
- Federated Learning communication-cost baseline.
- Design-space sweep and Pareto optimization.

## Final case study

The final case study is `environmental_monitoring_wsn`: Static environmental monitoring WSN with periodic sensor readings and anomaly/event traffic. It uses seed `2026`, `35` nodes, a `100.0 m x 100.0 m` area, `12` reports per node, and `48 B` payloads.

## Design alternatives

| ID | Design | MAC | Retry | Range m | Agg | Security | Edge AI | PDR | Energy J/deliv | Bytes | Pareto |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |
| alt_A_low_energy | Alternative A - low-energy baseline | csma | 0 | 40 | 0.45 | False | True | 0.846 | 0.000100 | 11091 | True |
| alt_B_reliability | Alternative B - reliability-oriented | csma | 4 | 55 | 0.00 | True | False | 0.930 | 0.000318 | 57175 | False |
| alt_C_balanced | Alternative C - balanced secured edge | csma | 2 | 55 | 0.45 | True | True | 0.945 | 0.000155 | 11042 | True |

## Metrics

- `pdr`: packet delivery ratio, maximize.
- `latency_mean`: mean latency in seconds, minimize.
- `energy_per_delivered_packet`: joules per delivered packet, minimize.
- `total_tx_bytes`: transmitted data/ACK/security bytes, minimize.
- `security_coverage`: replay protection enabled, maximize.
- Supporting metrics: communication saving, lifetime proxy, Edge AI recall, and overhead terms.

## Experiment setup

- Config path: `configs/m4_final.json`
- Seed: `2026`
- Sweep configurations plus alternatives: `219`
- Sweep dimensions: MAC, retry limit, radio range, aggregation threshold, security enabled, and Edge AI enabled.

## Results

- CSV file: `reports/m4_final_results.csv`
- Figures: `reports/figures/m4_pareto_energy_vs_pdr.png`, `reports/figures/m4_latency_vs_energy.png`, `reports/figures/m4_design_alternatives_comparison.png`, `reports/figures/m4_final_topology.png`
- Pareto-efficient configurations: `11`
- Most reliable Pareto point: `sweep_214` with PDR `0.945`
- Lowest-energy Pareto point: `sweep_118` with energy per delivered packet `0.000098 J`

## Pareto-based decision

`alt_C_balanced` (`Alternative C - balanced secured edge`) uses MAC `csma`, retry limit `2`, radio range `55 m`, aggregation threshold `0.45`, security `True`, and Edge AI `True`. It reaches PDR `0.945`, mean latency `0.0166 s`, energy per delivered packet `0.000155 J`, total transmitted bytes `11042`, and communication saving `0.726`.

The final choice is a trade-off rather than a single-objective optimum. Alternative B prioritizes reliability and security but transmits more bytes. Alternative A reduces traffic and energy but leaves replay protection disabled. Alternative C is recommended because it remains Pareto-efficient while combining high PDR, security coverage, aggregation, and Edge AI traffic reduction.

## Reproducibility

```bash
python -m pytest -q
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

The command writes the exact config dump to `reports/m4_final_config_dump.json`, the CSV to `reports/m4_final_results.csv`, and regenerates all M4 figures.

## Known limitations

- The final evaluator is an analytic integration proxy, not a full packet-level simulation of every layer simultaneously.
- Radio propagation uses a simplified log-distance model.
- MAC, ARQ, aggregation, security, and Edge AI interactions are approximated with deterministic formulas.
- Energy values are useful for relative comparison but are not calibrated against hardware measurements.
- Security models replay protection and overhead, not real cryptography.
- Edge AI uses a lightweight synthetic anomaly detector.

## Future work

- Calibrate radio and energy parameters from measurements.
- Run larger topologies and repeated stochastic trials.
- Integrate full packet-level MAC/routing/reliability/security interactions.
- Add stronger security protocols and key-management assumptions.
- Replace the toy Edge AI and FL models with realistic workloads.
