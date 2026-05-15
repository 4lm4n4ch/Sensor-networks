# M4 Case Study - Environmental Monitoring WSN

## Scenario

Static environmental monitoring WSN with periodic sensor readings and anomaly/event traffic.

- Deterministic seed: `2026`
- Nodes: `35` sensors plus one sink
- Area: `100.0 m x 100.0 m`
- Sink position: `[50.0, 50.0]` m
- Traffic: `12` periodic reports per node with event probability `0.05`
- Payload: `48 B`

## Metrics

- PDR: delivered packet fraction.
- Mean latency: end-to-end latency proxy in seconds.
- Energy per delivered packet: joules per delivered report.
- Total transmitted bytes: data plus ACK/security overhead proxy.
- Lifetime proxy: node battery divided by estimated per-node energy.
- Communication saving ratio: reduction versus raw periodic forwarding.
- Security coverage and Edge AI overhead/saving metrics.

## Design alternatives

| ID | Design | MAC | Retry | Range m | Agg | Security | Edge AI | PDR | Energy J/deliv | Bytes | Pareto |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |
| alt_A_low_energy | Alternative A - low-energy baseline | csma | 0 | 40 | 0.45 | False | True | 0.846 | 0.000100 | 11091 | True |
| alt_B_reliability | Alternative B - reliability-oriented | csma | 4 | 55 | 0.00 | True | False | 0.930 | 0.000318 | 57175 | False |
| alt_C_balanced | Alternative C - balanced secured edge | csma | 2 | 55 | 0.45 | True | True | 0.945 | 0.000155 | 11042 | True |

## Automatic sweep and Pareto front

The automatic sweep evaluates `2` MAC choices, `3` retry settings, `3` radio ranges, `3` aggregation settings, security on/off, and Edge AI on/off. The CSV marks Pareto-efficient points in `reports/m4_final_results.csv`. Pareto candidates found: `11`.

## Recommended design point

`alt_C_balanced` (`Alternative C - balanced secured edge`) uses MAC `csma`, retry limit `2`, radio range `55 m`, aggregation threshold `0.45`, security `True`, and Edge AI `True`. It reaches PDR `0.945`, mean latency `0.0166 s`, energy per delivered packet `0.000155 J`, total transmitted bytes `11042`, and communication saving `0.726`.

This is the final recommendation because it is Pareto-efficient, keeps PDR high, includes replay protection, and cuts transmitted bytes using aggregation plus Edge AI. The reliability-oriented design has slightly stronger raw delivery but spends more bytes and energy; the low-energy baseline is cheaper but has no security coverage.

## Reproducibility

```bash
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

- Config dump: `reports/m4_final_config_dump.json`
- CSV results: `reports/m4_final_results.csv`
- Pareto figure: `reports/figures/m4_pareto_energy_vs_pdr.png`
- Latency/energy figure: `reports/figures/m4_latency_vs_energy.png`
- Alternative comparison figure: `reports/figures/m4_design_alternatives_comparison.png`
- Topology figure: `reports/figures/m4_final_topology.png`
