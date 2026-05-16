# Slide 1 - Title

wsnsim: Wireless Sensor Network Simulator

# Slide 2 - Problem and goal

Study WSN design trade-offs among reliability, energy, latency, transmitted
bytes, and security coverage.

# Slide 3 - Simulator architecture

Deterministic scheduler -> channel/topology -> MAC/routing/reliability ->
energy/security/aggregation/Edge AI/FL -> metrics -> Pareto optimizer.

# Slide 4 - Scenario

Environmental monitoring WSN, seed `42069`, 35 sensor nodes, `100 m x 100 m`
area, center sink, 12 reports per node, 48 B payloads, anomaly/event traffic.
Topology figure: `reports/figures/m4_final_topology.png`.

# Slide 5 - Design alternatives

- Alternative A: low-energy baseline with aggregation and Edge AI, no replay protection.
- Alternative B: reliability-oriented design with retries and replay protection.
- Alternative C: balanced secured edge design with retries, aggregation, replay protection, and Edge AI.

# Slide 6 - Metrics and experiment method

Objectives: maximize `pdr` and `security_coverage`; minimize
`energy_per_delivered_packet`, `latency_mean`, and `total_tx_bytes`.
The experiment evaluates named alternatives plus a deterministic automatic sweep.

# Slide 7 - Results

- CSV: `reports/m4_final_results.csv`
- Pareto figure: `reports/figures/m4_pareto_energy_vs_pdr.png`
- Latency/energy figure: `reports/figures/m4_latency_vs_energy.png`
- Alternative comparison: `reports/figures/m4_design_alternatives_comparison.png`
- Evaluated configurations: 219
- Pareto-efficient configurations: 11

# Slide 8 - Pareto decision

Recommended design: `alt_C_balanced`. It is Pareto-efficient and reaches PDR
`0.945`, mean latency `0.0166 s`, energy `0.000155 J/delivered packet`, total
transmitted bytes `11042`, and communication saving `0.726`.

# Slide 9 - Reproducibility

```bash
python -m pytest -q
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

Outputs: `reports/m4_final_config_dump.json`, `reports/m4_final_results.csv`,
and M4 figures under `reports/figures/`.

# Slide 10 - Limitations and lessons learned

The final evaluator is an analytic integration proxy, not a full packet-level
cross-layer simulator. Security, Edge AI, FL, radio, and energy models are
simplified. The main lesson is that Pareto analysis makes the final design
choice evidence-based rather than single-metric.
