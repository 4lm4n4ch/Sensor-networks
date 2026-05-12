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

