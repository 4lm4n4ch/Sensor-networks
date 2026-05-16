# Slide 1 - Title

wsnsim: Wireless Sensor Network Simulator

# Slide 2 - Problem and goal

Study WSN trade-offs between delivery reliability, energy, latency, transmitted bytes, and security coverage for environmental monitoring.

# Slide 3 - Simulator architecture

Core scheduler -> channel/topology -> MAC/routing/reliability -> energy/security/aggregation/Edge AI/FL -> metrics -> Pareto optimizer.

# Slide 4 - Scenario

Seed `42069`, `35` nodes, `100.0 m x 100.0 m`, `12` reports per node, `48 B` payloads. Figure: `reports/figures/m4_final_topology.png`.

# Slide 5 - Design alternatives

| ID | Design | MAC | Retry | Range m | Agg | Security | Edge AI | PDR | Energy J/deliv | Bytes | Pareto |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |
| alt_A_low_energy | Alternative A - low-energy baseline | csma | 0 | 40 | 0.45 | False | True | 0.846 | 0.000100 | 11091 | True |
| alt_B_reliability | Alternative B - reliability-oriented | csma | 4 | 55 | 0.00 | True | False | 0.930 | 0.000318 | 57175 | False |
| alt_C_balanced | Alternative C - balanced secured edge | csma | 2 | 55 | 0.45 | True | True | 0.945 | 0.000155 | 11042 | True |

# Slide 6 - Metrics and experiment method

Objectives: maximize PDR and security coverage; minimize energy per delivered packet, mean latency, and transmitted bytes. Automatic sweep varies MAC, retry limit, range, aggregation, security, and Edge AI.

# Slide 7 - Results

Pareto figure: `reports/figures/m4_pareto_energy_vs_pdr.png`. Alternative comparison: `reports/figures/m4_design_alternatives_comparison.png`. Best normalized-rank point: `sweep_144`. Most reliable Pareto point: `sweep_214` with PDR `0.945`. Lowest-energy Pareto point: `sweep_118` with `0.000098 J`.

# Slide 8 - Pareto decision

`alt_C_balanced` (`Alternative C - balanced secured edge`) uses MAC `csma`, retry limit `2`, radio range `55 m`, aggregation threshold `0.45`, security `True`, and Edge AI `True`. It reaches PDR `0.945`, mean latency `0.0166 s`, energy per delivered packet `0.000155 J`, total transmitted bytes `11042`, and communication saving `0.726`.

Decision: choose Alternative C because it keeps high delivery and security while using aggregation plus Edge AI to avoid the bytes/energy cost of the reliability-only design.

# Slide 9 - Reproducibility

```bash
python -m pytest -q
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

Outputs: `reports/m4_final_results.csv`, `reports/m4_final_config_dump.json`, and M4 figures under `reports/figures/`.

# Slide 10 - Limitations and lessons learned

Simplifications: analytic layer integration, simplified channel/MAC, toy Edge AI/FL, replay-only security, uncalibrated energy. Lesson: Pareto analysis exposes why the final choice is a defensible compromise, not the winner of only one metric.

## Possible reviewer questions

- Why not pick the lowest-energy point? Because it disables security and sacrifices reliability margin.
- Why not pick the highest-PDR point? Because it spends more bytes and energy.
- Is the result reproducible? Yes: one command, fixed seed, config dump, CSV, and regenerated figures.
