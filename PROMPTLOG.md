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
