# wsnsim - Wireless Sensor Network Simulator

`wsnsim` is a modular Python simulator for Wireless Sensor Network coursework.
It combines a deterministic event core with radio, energy, MAC, topology,
routing, reliability, synchronization/localization, aggregation, security,
Edge AI, Federated Learning, and Pareto optimization models.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

If you use the already-created repository environment, the equivalent command is:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python experiments/m4_final_case_study.py --config configs/m4_final.json
```

## What is simulated?

The final M4 case study is an environmental monitoring WSN with static sensor
nodes, one sink, periodic sensor reports, and anomaly/event traffic.

- Topology: 35 sensors in a `100 m x 100 m` area with the sink at the center.
- Traffic: 12 periodic reports per node, 48 B payloads, event probability 0.05.
- Seed: `42069`.
- Metrics: PDR, mean latency, energy per delivered packet, total transmitted
  bytes, communication saving ratio, lifetime proxy, security coverage, and
  Edge AI overhead/recall.

## Implemented modules

- `wsnsim.sim`: deterministic scheduler and simulation clock.
- `wsnsim.models.channel`: log-distance PRR(distance) radio channel.
- `wsnsim.models.energy`: state-based energy/lifetime accounting.
- `wsnsim.models.mac`: ALOHA and simplified CSMA/backoff.
- `wsnsim.models.topology`: deterministic topology/connectivity helpers.
- `wsnsim.models.routing`: Flooding and sink-tree BFS routing.
- `wsnsim.models.reliability`: ACK/retry ARQ.
- `wsnsim.models.sync_localization`: clock drift, sync, RSSI localization.
- `wsnsim.models.aggregation`: aggregation and delta compression.
- `wsnsim.models.security`: replay protection and overhead accounting.
- `wsnsim.models.edge_ai`: anomaly detection and communication saving metrics.
- `wsnsim.models.federated`: toy FedAvg communication-cost baseline.
- `wsnsim.models.optimization`: grid search, Pareto front, candidate ranking.


## Weekly and milestone commits

| Checkpoint | Last/representative commit | Note |
| --- | --- | --- |
| Week 1 | `25bd3c0` | `first week` |
| Week 2 | `16e2ec6` | No separate Week 2 commit was listed; M1 commit contains the Week 2 evidence. |
| Week 3 | `cfbc5a7` | `Week3 implementation` |
| Week 4 | `b6d0a9e` | `week 4 commit` |
| Week 5 | `95d8f21` | `Week 5 commit` |
| Week 6 | `9092f7f` | No separate Week 6 commit was listed; closest routing/protocol checkpoint. |
| Week 7 | `c25d52c` | Latest Week 7 checkpoint, `WEEK 7.` |
| Week 8 | `4587a78` | `Week 8` |
| Week 9 | `e3074fb` | `Week 9 commit` |
| Week 10 | `b31bd55` | `Week 10` |
| Week 11 | `81fda9c` | `week 11` |
| Week 12 | `dedb8ed` | `week 12` |
| Week 13 | `2682e58` | Latest Week 13 checkpoint, `week 13 don` |
| Week 14 | `018878e` | `week 14` |
| Milestone 1 | `16e2ec6` | `milestone 1 commit` |
| Milestone 2 | `c25d52c` | Protocol milestone represented by the latest Week 7 checkpoint. |
| Milestone 3 | `e5962b2` | `m3` |
| Milestone 4 | `347c80f` | Latest M4 checkpoint, `M4 v2` |

A fuller audit table is also kept in `reports/weekly_commit_shas.md`.

## Final M4 case study

Compared alternatives:

- Alternative A: low-energy baseline with CSMA, no retries, aggregation, Edge AI,
  and no replay protection.
- Alternative B: reliability-oriented design with CSMA, retries, large radio
  range, and replay protection.
- Alternative C: balanced secured edge design with CSMA, moderate retries,
  large radio range, aggregation, replay protection, and Edge AI.

Pareto objectives:

- Maximize `pdr`.
- Minimize `energy_per_delivered_packet`.
- Minimize `latency_mean`.
- Minimize `total_tx_bytes`.
- Maximize `security_coverage`.

Recommended design: `alt_C_balanced`. It is Pareto-efficient in the generated
M4 CSV and is chosen because it keeps high delivery and security coverage while
using aggregation plus Edge AI to reduce transmitted bytes and energy.

## Reproducibility

Main command:

```bash
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

Generated artifacts:

- Config dump: `reports/m4_final_config_dump.json`
- Results CSV: `reports/m4_final_results.csv`
- Summary: `reports/m4_final_summary.md`
- Case study: `reports/m4_case_study.md`
- Final report: `reports/m4_final_report.md`
- Reproducibility checklist: `reports/m4_reproducibility_checklist.md`
- Presentation: `presentation/m4_wsnsim_presentation.md`

Figures:

- `reports/figures/m4_pareto_energy_vs_pdr.png`
- `reports/figures/m4_latency_vs_energy.png`
- `reports/figures/m4_design_alternatives_comparison.png`
- `reports/figures/m4_final_topology.png`

## Results

The generated M4 run evaluates 219 configurations and identifies 11
Pareto-efficient points. The recommended `alt_C_balanced` configuration reaches
PDR `0.945`, mean latency `0.0166 s`, energy per delivered packet
`0.000155 J`, total transmitted bytes `11042`, and communication saving ratio
`0.726`.

The figures show that lower-energy points exist, but they either disable replay
protection or give less reliability margin. The final choice is therefore a
trade-off rather than the winner of a single metric.

## Limitations

- The M4 evaluator is an analytic integration proxy, not a full packet-level
  simulation of every layer interacting simultaneously.
- Radio propagation, MAC contention, retry behavior, aggregation, security, and
  Edge AI are simplified and deterministic.
- Energy values support relative comparison but are not hardware-calibrated.
- Security covers replay protection and overhead, not real cryptography.
- Edge AI and Federated Learning use lightweight synthetic workloads.
