# Repository Audit

## Structure

The repository is a coherent Python package:

- `wsnsim/`: simulator source code.
- `wsnsim/sim/`: discrete-event scheduler and clock.
- `wsnsim/core/`: shared packet/link dataclasses.
- `wsnsim/models/`: WSN models from channel through optimization.
- `wsnsim/scenarios/`: scenario helper namespace.
- `wsnsim/metrics/`: simple metric helpers.
- `tests/`: pytest coverage for critical modules.
- `experiments/`: weekly and M4 experiment scripts.
- `configs/`: final M4 JSON config.
- `reports/`: CSVs, mini reports, final report, checklist, audit artifacts.
- `reports/figures/`: generated plots.
- `presentation/`: M4 presentation markdown.

This structure matches the PDF's intent even though it is not a byte-for-byte
copy of the suggested tree.

## Implemented modules

- `wsnsim.sim.sim`: deterministic event scheduler, clock, and event queue.
- `wsnsim.utils.logger`: trace logger.
- `wsnsim.utils.rng`: deterministic RNG wrapper.
- `wsnsim.models.channel`: log-distance radio channel and PRR model.
- `wsnsim.models.energy`: TX/RX/IDLE/SLEEP energy accounting.
- `wsnsim.models.mac`: ALOHA and simplified CSMA/backoff.
- `wsnsim.models.topology`: random, grid, and clustered topologies plus graphs.
- `wsnsim.models.routing`: flooding and sink-tree BFS routing.
- `wsnsim.models.reliability`: ACK/retry ARQ.
- `wsnsim.models.sync_localization`: clock drift and RSSI trilateration.
- `wsnsim.models.aggregation`: raw forwarding, tree aggregation, delta suppression.
- `wsnsim.models.security`: replay protection and overhead model.
- `wsnsim.models.edge_ai`: synthetic sensor signals and anomaly detection.
- `wsnsim.models.federated`: FedAvg-style baseline and communication model.
- `wsnsim.models.optimization`: grid search, dominance, Pareto front, ranking.

## Tests

Available tests:

- `tests/test_core.py`
- `tests/test_channel.py`
- `tests/test_energy.py`
- `tests/test_mac.py`
- `tests/test_topology.py`
- `tests/test_routing.py`
- `tests/test_reliability.py`
- `tests/test_sync_localization.py`
- `tests/test_aggregation.py`
- `tests/test_security.py`
- `tests/test_edge_ai.py`
- `tests/test_federated.py`
- `tests/test_optimization.py`

Final verification result: `.venv/bin/python -m pytest -q` reported
`123 passed`.

## Experiments

Runnable experiment scripts:

- `experiments/week02_prr_curve.py`
- `experiments/week03_energy_lifetime.py`
- `experiments/week04_mac_aloha_csma.py`
- `experiments/week05_topology_connectivity.py`
- `experiments/week06_routing_compare.py`
- `experiments/week07_reliability_arq.py`
- `experiments/week08_sync_localization.py`
- `experiments/week09_aggregation_compression.py`
- `experiments/week10_security_overhead.py`
- `experiments/week11_edge_ai_detector.py`
- `experiments/week12_federated_learning.py`
- `experiments/week13_design_space_optimization.py`
- `experiments/m4_final_case_study.py`

Final M4 command:

```bash
python experiments/m4_final_case_study.py --config configs/m4_final.json
```

Run this after activating an environment with `requirements.txt` installed.

## Reports and figures

Important report and CSV artifacts:

- `reports/m4_case_study.md`
- `reports/m4_final_report.md`
- `reports/m4_final_summary.md`
- `reports/m4_final_results.csv`
- `reports/m4_final_config_dump.json`
- `reports/m4_reproducibility_checklist.md`
- `reports/pdf_requirements_matrix.md`
- `reports/repo_audit.md`
- Weekly CSV/report artifacts under `reports/`.

Important M4 figures:

- `reports/figures/m4_pareto_energy_vs_pdr.png`
- `reports/figures/m4_latency_vs_energy.png`
- `reports/figures/m4_design_alternatives_comparison.png`
- `reports/figures/m4_final_topology.png`

## Documentation

`README.md` is short and runnable. It documents environment creation,
dependency installation, tests, the final M4 command, modules, final results,
reproducibility artifacts, and limitations.

`PROMPTLOG.md` is readable and contains major AI-assisted work summaries through
Week 14 / M4, including accepted/rejected suggestions and validation.

## Problems found

- `pdftotext` and Python PDF libraries were unavailable, so PDF extraction used
  a local fallback decoder. The requirements matrix records this.
- `__pycache__/` and `.pytest_cache/` directories exist locally. They are not
  M4 blockers, but they should be omitted from a ZIP export if the submission is
  not made through Git.
- A plain system `python` did not have Matplotlib installed during verification.
  The repository virtual environment worked. The README documents environment
  creation and `.venv/bin/python` equivalents.
- No `pyproject.toml` exists. This is acceptable because `requirements.txt` is
  present and sufficient for the course scope.
