# Prompt Log

Date: 2026-05-12 22:00

## Original Prompt
Role: Expert Python developer and WSN researcher.

Task: Build the core engine (v0) of a modular discrete-event simulator named wsnsim.

Core requirements captured:
- Discrete event engine using heapq.
- API:
	- schedule(time, callback, priority, payload)
	- run(until)
- Deterministic tie-breaking for identical timestamps (priority and/or counter).
- Central SimClock using float time.
- Timestamped logger/trace module with enable/disable support.
- Reproducibility using numpy.random.default_rng with configurable seed.
- Deliverables:
	- sim.py (scheduler + clock)
	- utils/logger.py
	- At least 2 pytest tests:
		- chronological ordering
		- deterministic identical timestamp ordering
	- Hello Simulation example script.
- Style constraints: PEP 8, type hints, docstrings, class-based design, avoid globals.

## Implementation Deliverables
- Added simulator core module with class-based scheduler and simulation clock.
- Added trace logger module with timestamped records and enable/disable controls.
- Added tests for chronological execution and deterministic tie-breaking behavior.
- Added a Hello Simulation example script for a basic event loop demonstration.

## Test Commands
- .venv/bin/python -m pytest -q
- .venv/bin/python -m pytest -q tests/test_sim_core.py
- .venv/bin/python -m pytest -q tests/test_sim_core.py tests/test_scheduler.py tests/test_channel.py

## Status
....                                                                     [100%]
4 passed in 0.10s

---

Date: 2026-05-12 23:16

## Week 2 Goal
Build the radio channel module for `wsnsim`, modeling packet delivery as a function of distance, log-distance path loss, shadowing, RSSI, SNR, PRR, and optional BER/PER.

## Prompt Summary
- Add neutral core dataclasses:
	- `wsnsim/core/packet.py`
	- `wsnsim/core/link.py`
- Implement `ChannelConfig` and `LogDistanceChannel` in `wsnsim/models/channel.py`.
- Use local `numpy.random.default_rng(config.seed)` only.
- Pin one shadowing value per transmission and reuse it across all returned metrics.
- Add channel tests for monotonic path loss/RSSI/SNR, PRR bounds, reproducibility, validation, BER packet-size behavior, and shadowing consistency.
- Add `experiments/week02_prr_curve.py` and save `reports/figures/week02_prr_vs_distance.png`.
- Update README and PROMPTLOG.

## Accepted Suggestions
- Kept `Packet` outside the channel module so later MAC, routing, reliability, and energy modules can reuse it.
- Used `LinkStats` as the single structured return object for all calculated link metrics.
- Implemented pure formula helpers that do not draw random values.
- Used `calculate_link_stats(...)` as the only method that pins shadowing and optionally samples packet success.
- Generated the Week 2 plot from theoretical logistic PRR and Monte Carlo mean PRR, not one-shot success values.
- Kept `Channel = LogDistanceChannel` as a compatibility alias for package exports.

## Rejected Suggestions
- Rejected global random state and independent shadowing draws inside helper methods.
- Rejected defining packet metadata inside `wsnsim.models.channel`.
- Rejected plotting stochastic one-shot success for the Week 2 PRR curve.

## Validation Steps
- Ran `.venv/bin/python -m pytest -q tests/test_channel.py`.
- Ran `.venv/bin/python -m pytest -q`.
- Ran `.venv/bin/python experiments/week02_prr_curve.py`.
- Confirmed `reports/figures/week02_prr_vs_distance.png` was created as a 1200 x 750 PNG.

## Final Week 2 Decision
Week 2 is accepted after channel unit tests, full-suite tests, and experiment validation. The implemented channel keeps packet metadata in `wsnsim.core`, calculates one-pass link statistics with pinned shadowing, and separates theoretical PRR from stochastic packet success.

## Known Limitations
- Week 2 models a single-link radio channel only; MAC contention, interference, capture effects, retransmissions, and energy accounting remain future modules.
- The PRR-vs-distance figure reports logistic PRR and Monte Carlo mean PRR, not observed delivery traces from a full network scenario.

## Status
[100%]
Tests passed

---

Date: 2026-05-13 10:00

## Week 3 Goal
Build an energy and lifetime module for `wsnsim`, modeling node energy consumption over simulated time with radio/MCU states `TX`, `RX`, `IDLE`, and `SLEEP`.

## Prompt Summary
- Replace the placeholder `wsnsim/models/energy.py` with a clean state-based energy model.
- Add `EnergyState`, `PowerProfile`, `Battery`, `DutyCycleConfig`, `LifetimeEstimate`, and `EnergyModel`.
- Integrate energy as `energy_j = power_w * duration_s`.
- Ensure transitions integrate the previous state before switching.
- Clamp remaining battery energy at zero and expose depletion status.
- Add duty-cycle lifetime estimation in seconds, hours, and days.
- Add tests for monotonic consumed/remaining energy, depletion clamp, negative durations/timestamps, lifetime trends, and a 1 W for 10 s manual check.
- Add robustness tests for battery validation, power-profile validation, and repeated drain after depletion.
- Add `experiments/week03_energy_lifetime.py` to save CSV results and a lifetime-vs-duty-cycle plot.

## Accepted Suggestions
- Kept all power values in `PowerProfile` instead of hidden constants.
- Added explicit unit suffixes: `_w`, `_j`, and `_s`.
- Added a richer `estimate_lifetime(...)` result while keeping `estimate_lifetime_seconds(...)` for the requested scalar API.
- Documented sleep and idle as separate states with separate configured power draw.
- Documented that switching costs are not modeled in Week 3.

## Rejected Suggestions
- Rejected embedding default radio power constants in the model.
- Rejected mixing battery capacity and consumed energy without explicit joule units.
- Rejected modeling radio startup/switching transients before MAC and packet-airtime modules exist.

## Validation Steps
- Ran `.venv/bin/python -m pytest -q tests/test_energy.py`.
- Ran `.venv/bin/python -m pytest -q`.
- Ran `.venv/bin/python experiments/week03_energy_lifetime.py`.
- Confirmed `reports/week03_energy_lifetime.csv` and `reports/figures/week03_lifetime_vs_duty_cycle.png` were generated.
- After robustness-test additions, reran `.venv/bin/python -m pytest -q tests/test_energy.py`: 11 passed.
- After robustness-test additions, reran `.venv/bin/python -m pytest -q`: 32 passed.

## Status
All Tests passed

---

Date: 2026-05-13 3:30

## Milestone 1 Finalization Goal
Prepare the repository for Milestone 1 submission by addressing review follow-ups without adding Week 4 MAC requirements.

## Prompt Summary
- Refresh README title and summary so the project is presented as the Milestone 1 Week 1-3 simulator foundation.
- Replace the placeholder clone URL with the repository remote.
- Expand the README testing summary to mention core, channel, energy, and scheduler-driven integration coverage.
- Add one integration test where scheduled simulator events drive `EnergyModel` state transitions over simulated time.
- Add this new prompt-log entry for the Milestone 1 finalization pass.

## Accepted Suggestions
- Kept the scope limited to Milestone 1 deliverables: event core, channel, energy, documentation, tests, and prompt log.
- Used the existing `Scheduler` API to drive energy state transitions in the new test.
- Kept the energy assertion unit-based: TX `1.0 W * 2 s`, RX `0.5 W * 3 s`, and SLEEP `0.1 W * 2 s`, for a total of `3.7 J`.
- Used the actual Git remote `git@github.com:4lm4n4ch/Sensor-networks.git` in the README.

## Rejected Suggestions
- Rejected adding or requiring Week 4 MAC protocol behavior for this milestone.
- Rejected broad README rewrites beyond the stale title, clone command, module list, and testing summary.

## Validation Steps
- Ran `.venv/bin/python -m pytest -q tests/test_energy.py`: 12 passed.
- Ran `.venv/bin/python -m pytest -q`: 33 passed.

## Status
Milestone 1 finalization updates complete and tests passed.

---

Date: 2026-05-13

## Week 4 Goal
Build the first MAC layer module for `wsnsim`, focused on ALOHA vs simplified CSMA behavior: collision timing, carrier sensing, seeded backoff, retry limits, delay, and energy hooks.

## Prompt Summary
- Replace the placeholder `wsnsim/models/mac.py` with a scheduler-compatible MAC implementation.
- Add explicit dataclasses and enums for MAC packets, transmissions, packet status, MAC events, and results.
- Implement `CollisionDomain` with interval-overlap collision detection on the same channel.
- Implement `AlohaMAC` with send-at-will behavior and no carrier sensing.
- Implement `CSMAMAC` with instantaneous carrier sensing, deterministic slotted random backoff, contention-window growth, and retry-limit drops.
- Add optional `EnergyModel` hooks for TX, RX sensing, and IDLE transitions.
- Add deterministic pytest coverage in `tests/test_mac.py`.
- Add `experiments/week04_mac_aloha_csma.py` to compare ALOHA and CSMA under increasing traffic load and save CSV/plots.
- Update README with Week 4 architecture, simplifications, comparison table, sanity checklist, and run commands.

## Accepted Suggestions
- Kept collision detection explicit and testable using half-open intervals `[start, end)`.
- Used the existing deterministic scheduler rather than adding a second event system.
- Kept carrier sensing simple: busy means an active transmission contains the sensing time.
- Used `numpy.random.default_rng(seed)` inside CSMA for reproducible backoff.
- Documented that this is not full IEEE 802.15.4 CSMA/CA.
- Kept energy integration as hooks into Week 3 state transitions instead of expanding the energy model.

## Rejected Suggestions
- Rejected RSSI-threshold carrier sensing for Week 4 to avoid mixing physical-layer sensing with the first MAC abstraction.
- Rejected full 802.15.4 features such as ACKs, beacons, superframes, CCA timing, NB/BE state machine, hidden-terminal modeling, and capture effects.
- Rejected changing Milestone 1 scope; Week 4 MAC documentation is clearly separated from the M1 foundation note.

## Validation Steps
- Added tests for ALOHA same-time collisions.
- Added tests for non-overlapping ALOHA transmissions.
- Added tests for CSMA busy-channel backoff.
- Added tests for fixed-seed backoff reproducibility.
- Added tests that collision detection uses interval overlap, not only equal start times.
- Added tests that retry limits eventually drop a packet if the channel remains busy.

## Status
Week 4 MAC implementation, tests, experiment, README section, and prompt log entry added.

---

Date: 2026-05-14 16:40

## Week 5 Goal
Build topology and connectivity graph support for `wsnsim`, including deterministic WSN node deployments, distance-based and PRR-based neighbor graphs, sink reachability, connected components, tests, an experiment script, README documentation, and this prompt-log entry.

## Context / Files Touched
- Added `wsnsim/models/topology.py`.
- Updated `wsnsim/models/__init__.py` exports.
- Added `tests/test_topology.py`.
- Added `experiments/week05_topology_connectivity.py`.
- Updated `README.md`.
- Updated `PROMPTLOG.md`.
- Generated Week 5 report outputs under `reports/` and `reports/figures/`.

## Prompt Summary
- Implement `Node`, `TopologyConfig`, and `Topology`.
- Add random uniform and grid deployment strategies, with clustered deployment as an optional extra.
- Use `numpy.random.default_rng(seed)` and avoid global random state.
- Build undirected neighbor graphs using either communication range or channel PRR threshold.
- Provide graph queries for neighbors, connected components, average degree, sink reachability, and sink reachability ratio.
- Add tests for reproducibility, bounds, grid placement, distance sanity, graph threshold behavior, and sink connectivity.
- Add a Week 5 experiment that plots topology links and communication range vs connectivity metrics.
- Document run commands and output paths.

## Accepted Suggestions
- Treated `node_count` as total nodes, reserving node `0` as the sink when a sink position is configured.
- Kept topology graphs as plain adjacency sets to avoid making graph operations depend on `networkx`.
- Added deterministic `random_uniform`, deterministic `grid`, and seeded `clustered` deployments.
- Used Euclidean distance in meters and explicit `_m` suffixes.
- Kept PRR graph construction compatible with the Week 2 channel API.
- Disabled shadowing by default for deterministic PRR-threshold graph construction.
- Added both boolean full sink connectivity and fractional sink reachability for experiments.

## Rejected Suggestions
- Rejected adding routing behavior in Week 5; topology only builds connectivity information.
- Rejected global random state and non-seeded deployment randomness.
- Rejected making `networkx` mandatory for the topology graph API.
- Rejected mixing MAC interference/collision behavior into topology connectivity.

## Validation Steps
- Ran `.venv/bin/python -m pytest -q tests/test_topology.py`.
- Ran `.venv/bin/python -m pytest -q`.
- Ran `.venv/bin/python experiments/week05_topology_connectivity.py`.
- Confirmed `reports/week05_topology_connectivity.csv`, `reports/figures/week05_topology_graph.png`, and `reports/figures/week05_connectivity_vs_range.png` were generated.

## Known Limitations
- Graphs are undirected and symmetric; asymmetric links are not modeled yet.
- PRR-threshold graphs use one link estimate per pair and do not model temporal link variation unless shadowing is explicitly enabled.
- Connectivity is based on geometric or PRR thresholds only; no routing, interference, duty-cycle availability, retransmissions, or link capacity constraints are modeled in Week 5.
- The sink is a single configured node; multi-sink topologies are left for future extensions.

## Status
Week 5 topology implementation, tests, experiment, README section, prompt log entry, and report artifacts added.

---

Date: 2026-05-15 14:30

## Repository Review Goal
Performed a comprehensive review of the `wsnsim` repository to check its compliance with course requirements for Weeks 1–5 and Milestone 1, including code implementation, tests, documentation, and generated artifacts.

## Context
Files/modules touched:
- `README.md`
- `PROMPTLOG.md`
- `wsnsim/sim/sim.py`
- `wsnsim/models/channel.py`
- `wsnsim/models/energy.py`
- `wsnsim/models/mac.py`
- `wsnsim/models/topology.py`
- `tests/` (all test files within)
- `experiments/` (all experiment scripts within)
- `reports/figures/` (all generated figures)
- `reports/` (all generated CSV files)

Branch/commit if known:
- not recorded

## Prompt Summary
- Inspect actual code, tests, README, PROMPTLOG, experiments, and generated figures.
- Verify behavior by reading code and running tests/experiments.
- Check compliance for Weeks 1-5 and Milestone 1, against specific criteria for scheduler, channel, energy, MAC, and topology.
- Produce a structured review in a specified format.

## AI Response Summary
- Conducted an initial research phase, reviewing project structure and documentation (`README.md`, `PROMPTLOG.md`).
- Performed a detailed code implementation review of `wsnsim/sim/sim.py` and modules under `wsnsim/models/`.
- Executed the full project test suite and all experiment scripts.
- Verified the generation, content, and scientific plausibility of all required figures and CSV outputs.
- Compiled a structured review report.

## Accepted Suggestions
- The existing project implementation for Weeks 1-5 and Milestone 1 was found to be in full compliance with all stated requirements. No new design suggestions were made for this review, as the task was to evaluate existing work.

## Rejected Suggestions
- No major suggestions were rejected.

## Validation Steps
- `bash -c "source .venv/bin/activate && ./run_tests.sh"`
- `bash -c "source .venv/bin/activate && export PYTHONPATH=$PYTHONPATH:. && python experiments/hello_simulation.py"`
- `bash -c "source .venv/bin/activate && export PYTHONPATH=$PYTHONPATH:. && python experiments/week02_prr_curve.py"`
- `bash -c "source .venv/bin/activate && export PYTHONPATH=$PYTHONPATH:. && python experiments/week03_energy_lifetime.py"`
- `bash -c "source .venv/bin/activate && export PYTHONPATH=$PYTHONPATH:. && python experiments/week04_mac_aloha_csma.py"`
- `bash -c "source .venv/bin/activate && export PYTHONPATH=$PYTHONPATH:. && python experiments/week05_topology_connectivity.py"`

Include generated artifacts:
- `reports/figures/week02_prr_vs_distance.png`
- `reports/figures/week03_lifetime_vs_duty_cycle.png`
- `reports/figures/week04_mac_pdr_vs_load.png`
- `reports/figures/week04_mac_collision_delay_vs_load.png`
- `reports/figures/week05_topology_graph.png`
- `reports/figures/week05_connectivity_vs_range.png`
- `reports/week03_energy_lifetime.csv`
- `reports/week04_mac_aloha_csma.csv`
- `reports/week05_topology_connectivity.csv`

## Results
- Tests: 46 passed.
- Figures: All created and found to be scientifically plausible.
- CSV/results: All created.

## Known Limitations
- Some experiment scripts may require `export PYTHONPATH=$PYTHONPATH:.` when run outside of the virtual environment activation or editable install. A small `setup.py` or `pyproject.toml` could provide a more robust solution.
- Experiment script outputs could benefit from a concise "Simulation Summary" at the end for quicker analysis.

## Final Decision
The `wsnsim` repository successfully passed the review, demonstrating full compliance with all course requirements for Weeks 1-5 and Milestone 1. The project is well-implemented, tested, and documented.

---

Date: 2026-05-15 17:00

## Week 6 Goal
Build routing and data collection baselines for `wsnsim`, including flooding with TTL/seen-cache, BFS sink-tree routing, fair comparison metrics, tests, an experiment script, generated CSV/PNG artifacts, README documentation, and this prompt-log entry.

## Context / Files Touched
- Replaced the placeholder `wsnsim/models/routing.py`.
- Updated `wsnsim/models/__init__.py` exports.
- Added `tests/test_routing.py`.
- Added `experiments/week06_routing_compare.py`.
- Updated `README.md`.
- Updated `PROMPTLOG.md`.
- Generated Week 6 outputs under `reports/` and `reports/figures/`.

## Prompt Summary
- Implement `RoutingPacket`, `RouteDecision`, `RoutingMetrics`, and shared routing configuration.
- Implement `FloodingRouting` using all neighbors except previous sender, TTL, deterministic forwarding order, and `(packet_id, node_id)` duplicate suppression.
- Implement `SinkTreeRouting` with BFS shortest-hop parent map rooted at the sink.
- Reuse Week 5 topology neighbor graphs and document deterministic neighbor-link delivery as the default Week 6 data-plane assumption.
- Add optional channel-based link success hooks without implementing ACK/retry.
- Add tests for flooding TTL behavior, duplicate suppression, delivery, sink-tree parent maps, unreachable drops, expected hop counts, deterministic behavior, and metrics sanity.
- Add a fair comparison experiment for Flooding vs Sink-tree BFS using the same seed, topology, traffic, payload size, TTL, and link assumptions.
- Save required CSV and PNG artifacts and document run commands.

## Accepted Suggestions
- Kept Week 6 to baseline routing only; no RPL, LEACH, ACK/retry, mobility, queueing, or congestion model.
- Used the existing Week 5 adjacency sets as the default deterministic link model for fair protocol comparison.
- Added simple per-bit TX/RX energy accounting so energy per bit can be compared without requiring a full radio state trace.
- Exposed `parent_map` and `hop_distance_map` for sink-tree inspection.
- Counted flooding duplicate/control overhead separately from generated packet count so PDR remains source-packet based.
- Included experiment captions with seed, node count, topology type, communication range, payload size, TTL, and link assumption.

## Rejected Suggestions
- Rejected full RPL/6LoWPAN, LEACH clustering, ACKs, retries, and ETX parent selection for this Week 6 baseline.
- Rejected making routing depend on `networkx`; the existing plain adjacency API is sufficient.
- Rejected global random state; optional stochastic link success uses a local seeded RNG.
- Rejected probabilistic channel delivery in the default comparison to avoid giving protocols different random link traces.

## Validation Steps
- Ran `.venv/bin/python -m pytest -q tests/test_routing.py`: 8 passed.
- Ran `.venv/bin/python -m pytest -q`: 54 passed.
- Ran `.venv/bin/python experiments/week06_routing_compare.py`.
- Inspected `reports/week06_routing_compare.csv`.
- Confirmed `reports/figures/week06_routing_pdr.png`, `reports/figures/week06_routing_latency.png`, and `reports/figures/week06_routing_energy_per_bit.png` were generated.

## Generated Artifacts
- `reports/week06_routing_compare.csv`
- `reports/figures/week06_routing_pdr.png`
- `reports/figures/week06_routing_latency.png`
- `reports/figures/week06_routing_energy_per_bit.png`

## Known Limitations
- Topology is static, links are symmetric, and the default experiment uses deterministic neighbor-link delivery.
- No ACK/retry, queueing, congestion, duty-cycle availability, mobility, interference, capture effect, or MAC scheduling is modeled in routing.
- Sink-tree parent selection is BFS shortest-hop only; ETX-like selection is left for a later extension.
- Energy is a simple per-bit TX/RX accounting model, not full integration through Week 3 state transitions.

## Status
Week 6 routing implementation, tests, experiment, README section, prompt log entry, and report artifacts added. Full test suite passed.

---

Date: 2026-05-15 17:45

## Week 6 Experiment Improvement Goal
Improve the Week 6 routing comparison figures by replacing the single easy scenario bar charts with communication-range sweep plots.

## Context / Files Touched
- Updated `experiments/week06_routing_compare.py`.
- Regenerated `reports/week06_routing_compare.csv`.
- Regenerated Week 6 routing figures under `reports/figures/`.
- Updated `README.md`.
- Updated `PROMPTLOG.md`.

## Prompt Summary
- The original Week 6 figures compared Flooding and Sink-tree BFS at only `40 m`, where both protocols had PDR `1.0` and nearly identical latency.
- Modify the experiment to sweep communication range using `[15, 20, 25, 30, 35, 40, 45, 50, 60]`.
- Produce more informative figures that show how protocol behavior changes with graph density and sink reachability.

## Accepted Suggestions
- Kept seed, node count, topology type, payload size, TTL, and deterministic link assumptions fixed across the sweep.
- Rebuilt the same seeded random-uniform deployment for each communication range so range is the controlled variable.
- Wrote one CSV row per protocol per communication range.
- Added `average_degree` and `sink_reachability_ratio` to the CSV for interpretation.
- Replaced bar charts with line plots against communication range.
- Used a log-scale y-axis for energy per delivered bit so Sink-tree BFS remains visible next to Flooding.

## Rejected Suggestions
- Rejected changing routing semantics or adding ACK/retry/channel randomness for this visualization pass.
- Rejected adding extra topology or payload sweeps before first making the required range sweep clear.

## Validation Steps
- Ran `.venv/bin/python experiments/week06_routing_compare.py`.
- Inspected the updated `reports/week06_routing_compare.csv`.
- Confirmed regenerated figures:
  - `reports/figures/week06_routing_pdr.png`
  - `reports/figures/week06_routing_latency.png`
  - `reports/figures/week06_routing_energy_per_bit.png`
- Ran `.venv/bin/python -m pytest -q tests/test_routing.py`: 8 passed.
- Ran `.venv/bin/python -m pytest -q`: 54 passed.

## Generated Artifacts
- `reports/week06_routing_compare.csv`
- `reports/figures/week06_routing_pdr.png`
- `reports/figures/week06_routing_latency.png`
- `reports/figures/week06_routing_energy_per_bit.png`

## Recommended Improvements
- The energy accounting in the routing module is a simplified per-bit model.
  While acceptable for Week 6, future work could integrate it directly with
  the more detailed Week 3 `EnergyModel` for a more comprehensive view of node
  energy states during routing.
- Consider adding graphical representations of the sink-tree, such as marking
  parent links in a topology plot, to visually confirm tree structure.

## Known Limitations
- With deterministic neighbor-link delivery, Flooding and Sink-tree BFS have the same reachability-limited PDR; the main protocol contrast is overhead and energy.
- Latency remains similar because Flooding's first delivery follows a shortest-hop wave in this static graph.
- The sweep changes graph density only; it does not yet vary payload size, traffic rate, channel PRR, losses, or retry behavior.

## Status
Week 6 routing comparison upgraded to communication-range sweep figures and regenerated artifacts. Full test suite passed.
