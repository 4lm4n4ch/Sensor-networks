# wsnsim: Wireless Sensor Network Simulator (Milestone 1)

## Project Overview

`wsnsim` is a Python-based discrete-event simulator designed for Wireless Sensor Networks (WSN). The primary goal is to provide a flexible and deterministic platform for researching various WSN protocols, topologies, and performance metrics.

**Milestone 1** covers the Week 1-3 simulator foundation: a deterministic discrete-event core, a basic radio channel model, a state-based energy/lifetime model, experiments, documentation, unit tests, and an AI prompt log.

A **discrete-event simulation** in `wsnsim` models a system as a sequence of events occurring at discrete points in time. The simulator maintains an event list, advancing its internal clock from one event to the next, executing associated callbacks. This approach is highly suitable for WSNs, where actions like message transmissions, sensor readings, or node state changes can be modeled as distinct events.

## Repository Structure

The `wsnsim` repository is structured to promote modularity, testability, and clear separation of concerns:

-   `wsnsim/`: The main source code directory for the simulator.
    -   `sim/`: Contains the core discrete-event simulation engine.
        -   `__init__.py`: Package initialization, exposing `Scheduler`, `SimClock`, and `ScheduledEvent` for direct import.
        -   `sim.py`: The heart of the simulator, implementing `Scheduler` (the discrete-event scheduler), `SimClock` (the simulation clock), and `ScheduledEvent` (the event data structure). This module handles event queuing, time advancement, and event execution.
    -   `utils/`: Utility modules supporting the simulator's operation.
        -   `__init__.py`: Package initialization.
        -   `config.py`: Placeholder for future configuration management.
        -   `logger.py`: Implements `TraceLogger`, a simple in-memory logger for recording simulation events for debugging and analysis.
        -   `logging.py`: Provides a standard Python `logging` setup for general application logs.
        -   `plot.py`: Placeholder for future plotting utilities.
        -   `rng.py`: Encapsulates `numpy.random.default_rng` for consistent and reproducible random number generation throughout the simulation.
    -   `metrics/`: Modules for calculating and analyzing WSN performance metrics.
        -   `__init__.py`: Package initialization.
        -   `energy.py`: Contains functions related to energy consumption metrics.
        -   `latency.py`: Placeholder for latency measurement functions.
        -   `pdr.py`: Placeholder for Packet Delivery Ratio (PDR) calculations.
    -   `models/`: WSN node and network models.
        -   `channel.py`: Week 2 log-distance radio channel model with shadowing, RSSI, SNR, PRR, BER/PER, and reproducible packet success sampling.
        -   `energy.py`: Week 3 state-based energy and lifetime model with TX/RX/IDLE/SLEEP power states.
    -   `core/`: Shared neutral dataclasses used across simulator layers.
        -   `packet.py`: `Packet` dataclass for MAC, routing, reliability, energy, and channel-independent packet metadata.
        -   `link.py`: `LinkStats` dataclass for one calculated transmission attempt.
    -   `scenarios/`: Placeholder for defining specific WSN simulation scenarios (e.g., node deployment, traffic patterns).
-   `tests/`: Contains unit and integration tests for the `wsnsim` codebase.
    -   `test_core.py`: Comprehensive tests for the core simulation engine (`Scheduler`, `SimClock`, `TraceLogger`) and `RNG` and basic `metrics`.
    -   `test_channel.py`: Channel tests for distance trends, probability bounds, reproducibility, validation, and manual PRR points.
    -   `test_energy.py`: Energy tests for unit-consistent consumption, depletion clamp, validation, lifetime trends, and scheduler integration.
-   `experiments/`: Contains example simulations and scripts to run various experiments.
    -   `hello_simulation.py`: A basic "hello world" example demonstrating how to set up and run a simple simulation using `wsnsim` v0.
    -   `run_sweep.py`: Placeholder for running parameter sweeps or multiple simulation runs.
    -   `week02_prr_curve.py`: Generates the Week 2 PRR-vs-distance curve.
    -   `week03_energy_lifetime.py`: Generates Week 3 lifetime-vs-duty-cycle data and plot.
-   `.gitignore`: Specifies intentionally untracked files to be ignored by Git.
-   `PROMPTLOG.md`: Log of interactions with the AI assistant (internal tool file).
-   `README.md`: This file, providing an overview and documentation of the project.
-   `requirements.txt`: Lists Python dependencies required by the project.

## Architecture Section

### Scheduler

The `Scheduler` class (`wsnsim.sim.sim.py`) is the central component of the discrete-event simulation engine. It manages a priority queue of `ScheduledEvent` objects, advancing the `SimClock` and executing event callbacks in chronological order.

-   **`schedule(time, callback, priority, payload)`**: Adds a new event to the event queue. `time` is the absolute simulation time, `callback` is the function to execute, `priority` influences tie-breaking, and `payload` carries event-specific data.
-   **`run(until)`**: Starts or continues the simulation, executing events until the queue is empty or the `until` time is reached.
-   **`stop()`**: Halts the simulation gracefully.

### SimClock

The `SimClock` class (`wsnsim.sim.sim.py`) provides a mutable, floating-point representation of the current simulation time. It can only advance forward, ensuring chronological integrity.

-   **`now`**: Property to retrieve the current simulation time.
-   **`advance_to(timestamp)`**: Moves the clock forward to a new timestamp. Raises `ValueError` if attempting to go backward in time.
-   **`reset(start)`**: Resets the clock to a specified starting time.

### Event Queue

The `Scheduler` uses a `heapq`-based priority queue to efficiently manage `ScheduledEvent` objects. `heapq` (Python's built-in min-heap implementation) ensures that the event with the smallest `time` value is always at the front of the queue.

### Tie-breaking Mechanism

Deterministic event ordering is crucial for reproducible simulations. `wsnsim` employs a robust tie-breaking mechanism for events with identical timestamps:

1.  **Time (`float`)**: Events are primarily ordered by their scheduled time.
2.  **Priority (`int`)**: For events with the same time, those with a lower numeric `priority` execute first. This allows users to define explicit precedence.
3.  **Sequence (`int`)**: As a final tie-breaker, an automatically incrementing `sequence` number (from `itertools.count`) is assigned to each event upon scheduling. This guarantees a stable, First-In-First-Out (FIFO) order for events with identical time and priority, making the simulation perfectly deterministic.

The `ScheduledEvent` dataclass is ordered based on these three fields.

### Logger/Trace System

The `TraceLogger` (`wsnsim.utils.logger.py`) provides a lightweight, in-memory tracing mechanism. It records significant simulation events (e.g., event scheduling, execution) with timestamps and custom details. This is invaluable for debugging, validating event flows, and understanding simulation dynamics. It can be enabled or disabled dynamically.

### Deterministic Execution

`wsnsim` is designed for absolute determinism:

-   **Event Ordering**: The `(time, priority, sequence)` tuple ensures a strict, reproducible order of event execution.
-   **Randomness**: All randomness is managed through `numpy.random.default_rng`, initialized with a specific seed, guaranteeing that sequences of random numbers are identical across simulation runs given the same seed.

### RNG Handling

Random Number Generation (RNG) is handled by the `RNG` class (`wsnsim.utils.rng.py`), which wraps `numpy.random.default_rng`. This ensures that all random operations within the simulator are:

1.  **Reproducible**: By passing a `seed` to the `Scheduler` (which then passes it to `RNG`), the entire sequence of random numbers generated during a simulation run is repeatable.
2.  **Consistent**: All modules requiring randomness should use an instance of the `RNG` class, avoiding reliance on Python's global `random` module.

## Week 2: Radio Channel Models

Week 2 adds a reproducible log-distance radio channel in `wsnsim.models.channel`. The channel is independent of MAC, routing, reliability, and energy modules. Packet metadata lives in `wsnsim.core.packet.Packet`, while one transmission attempt is reported as `wsnsim.core.link.LinkStats`.

### Channel Parameters

`ChannelConfig` uses explicit radio units:

-   `tx_power_dbm`: transmit power in dBm.
-   `d0_m`: reference distance in meters. Must be positive.
-   `path_loss_d0_db`: reference path loss at `d0_m`, in dB.
-   `path_loss_exponent`: log-distance exponent. Must be positive.
-   `shadowing_sigma_db`: standard deviation of log-normal shadowing, in dB. Must be non-negative.
-   `noise_floor_dbm`: receiver noise floor in dBm.
-   `snr_threshold_db`: logistic PRR midpoint in dB.
-   `transition_width_db`: logistic transition width in dB. Must be positive.
-   `seed`: seed for the channel-local `numpy.random.default_rng`.

### Formulas

The effective distance prevents singular behavior below the reference distance:

```text
d_eff = max(distance_m, d0_m)
```

Path loss uses a single pinned shadowing draw per transmission:

```text
PL(d) = PL(d0) + 10 * n * log10(d_eff / d0) + X_sigma
X_sigma ~ Normal(0, sigma)
```

RSSI and SNR are then computed as:

```text
RSSI_dbm = tx_power_dbm - path_loss_db
SNR_db = RSSI_dbm - noise_floor_dbm
SNR_linear = 10 ** (SNR_db / 10)
```

The default packet reception probability is logistic:

```text
PRR = 1 / (1 + exp(-(SNR_db - snr_threshold_db) / transition_width_db))
```

The optional BPSK-in-AWGN BER/PER model is also reported:

```text
BER = 0.5 * erfc(sqrt(SNR_linear))
packet_bits = packet_size_bytes * 8
PER = 1 - (1 - BER) ** packet_bits
PRR_BER = (1 - BER) ** packet_bits
```

`PRR` is a probability. Stochastic packet success is a separate one-shot realization, computed only when requested:

```text
success = channel_rng.random() < prr_value
```

### Manual Validation At Two Distances

Using the default Week 2 parameters with fixed shadowing `X_sigma = 0 dB`, packet size `64 bytes`, `tx_power_dbm = 0`, `d0_m = 1`, `PL(d0) = 40 dB`, `n = 2.7`, `noise_floor_dbm = -100`, `snr_threshold_db = 10`, and `transition_width_db = 2`:

```text
Distance 10 m:
PL = 40 + 10 * 2.7 * log10(10 / 1) + 0 = 67.0000 dB
RSSI = 0 - 67.0000 = -67.0000 dBm
SNR = -67.0000 - (-100) = 33.0000 dB
PRR_logistic = 1 / (1 + exp(-(33.0000 - 10) / 2)) = 0.999990

Distance 50 m:
PL = 40 + 10 * 2.7 * log10(50 / 1) + 0 = 85.8722 dB
RSSI = 0 - 85.8722 = -85.8722 dBm
SNR = -85.8722 - (-100) = 14.1278 dB
PRR_logistic = 1 / (1 + exp(-(14.1278 - 10) / 2)) = 0.887345
```

These two points are also checked in `tests/test_channel.py` to verify the full TX -> path loss -> RSSI -> SNR -> PRR chain against hand-computed values.

### Running Week 2 Tests

```bash
.venv/bin/python -m pytest -q tests/test_channel.py
```

To run the complete test suite:

```bash
.venv/bin/python -m pytest -q
```

### Running the PRR Experiment

```bash
.venv/bin/python experiments/week02_prr_curve.py
```

The experiment sweeps distance from 1 m to 150 m and compares `sigma = 0 dB` against `sigma = 4 dB`. For the shadowed case, the plotted value is a Monte Carlo mean PRR rather than one-shot packet success. The figure is saved to:

```text
reports/figures/week02_prr_vs_distance.png
```

Expected interpretation: as distance increases, path loss increases, RSSI and SNR decrease, and PRR falls. The shadowed curve is an average over many channel realizations, so it is smoother and represents expected delivery probability under fading rather than a single packet trace.

## Week 3: Energy and Lifetime

Week 3 adds a state-based node energy model in `wsnsim.models.energy`. It is designed for use from the discrete-event scheduler: each state transition first integrates the energy consumed in the previous state over elapsed simulated time.

### Energy Architecture

-   `EnergyState`: radio/MCU power states: `TX`, `RX`, `IDLE`, and `SLEEP`.
-   `PowerProfile`: configured power draw for each state, in watts.
-   `Battery`: capacity, initial energy, and remaining energy, in joules.
-   `EnergyModel`: current state, last update time, consumed energy, remaining energy, depletion status, and duty-cycle lifetime estimates.
-   `DutyCycleConfig`: per-cycle TX/RX/IDLE/SLEEP durations for lifetime estimation.
-   `LifetimeEstimate`: average power and lifetime in seconds, hours, and days.

### Energy Formula And Units

The model uses:

```text
energy_j = power_w * duration_s
```

State updates are integrated as:

```text
elapsed_s = time_s - last_update_time_s
consumed_j = power(current_state)_w * elapsed_s
remaining_energy_j = max(0, remaining_energy_j - consumed_j)
```

Watts and joules are kept separate in names: `_w` is power, `_j` is energy, and `_s` is time. Negative durations and backward timestamps raise `ValueError`. Remaining energy is clamped at zero, and `is_depleted` becomes true once the battery reaches zero.

### Duty-Cycle Lifetime Estimate

For a repeating cycle:

```text
energy_per_cycle_j =
    tx_w * tx_time_s
  + rx_w * rx_time_s
  + idle_w * idle_time_s
  + sleep_w * sleep_time_s

average_power_w = energy_per_cycle_j / cycle_time_s
lifetime_seconds = battery_capacity_j / average_power_w
lifetime_hours = lifetime_seconds / 3600
lifetime_days = lifetime_seconds / 86400
```

The estimator supports comparing multiple duty-cycle values. Higher active-time ratios should reduce estimated lifetime when TX/RX/IDLE power exceeds sleep power.

### Manual Validation

A directly checkable case is included in `tests/test_energy.py`:

```text
Power = 1 W
Duration = 10 s
Energy = 1 W * 10 s = 10 J
```

With a 100 J battery, remaining energy is 90 J after that consumption.

### Week 3 Sanity Checklist

-   Units: power is in watts, energy is in joules, simulated time is in seconds.
-   W vs J: energy is only produced by multiplying configured power by elapsed time.
-   Timestamp monotonicity: `update(time_s)` and `transition_to(..., time_s)` reject backward time.
-   Packet duration consistency: callers should convert packet airtime to seconds before calling `consume(...)` or scheduling TX/RX transitions.
-   Sleep and idle separation: `SLEEP` and `IDLE` have independent configured power values.
-   Switching cost: transition energy/time overhead is not modeled in Week 3; transitions only integrate the previous state up to the transition timestamp.

### Running Week 3 Tests

```bash
.venv/bin/python -m pytest -q tests/test_energy.py
```

### Running The Lifetime Experiment

```bash
.venv/bin/python experiments/week03_energy_lifetime.py
```

The experiment evaluates several active-time ratios, saves a CSV, and generates a lifetime plot:

```text
reports/week03_energy_lifetime.csv
reports/figures/week03_lifetime_vs_duty_cycle.png
```

### Week 3 Limitations

This is a first-order lifetime model. It does not yet model radio startup costs, state-switching transients, voltage conversion efficiency, battery recovery effects, temperature, leakage variation, interference-driven retransmissions, or packet-level airtime calculation. Those can be layered on later without changing the basic state-integration API.

## Installation & Running

To set up and run `wsnsim`, follow these steps:

1.  **Clone the Repository**:
    ```bash
    git clone git@github.com:4lm4n4ch/Sensor-networks.git
    cd Sensor-networks
    ```

2.  **Create a Virtual Environment** (recommended):
    ```bash
    python -m venv .venv
    ```

3.  **Activate the Virtual Environment**:
    -   On Linux/macOS:
        ```bash
        source .venv/bin/activate
        ```
    -   On Windows:
        ```bash
        .venv\Scripts\activate
        ```

4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the "Hello Simulation" Example**:
    ```bash
    python experiments/hello_simulation.py
    ```

## Testing Section

`wsnsim` emphasizes robust testing to ensure the correctness and deterministic behavior of the Milestone 1 simulator foundation.

-   **What is tested**: Unit tests cover core components like the `Scheduler`, `SimClock`, `TraceLogger`, and `RNG` reproducibility; channel behavior such as path loss/RSSI/SNR trends, PRR bounds, validation, and reproducible shadowing; and energy behavior such as `energy_j = power_w * duration_s`, depletion clamping, state transitions, lifetime trends, and scheduler-driven integration.
-   **Deterministic Testing Approach**: Tests for the `Scheduler` specifically verify that events are executed in the correct chronological order, and that tie-breaking rules (priority, then sequence) are strictly followed, irrespective of the order events are scheduled.
-   **Reproducibility**: The `RNG` tests explicitly confirm that simulations initialized with the same seed produce identical sequences of random numbers, ensuring that simulation results can be reproduced exactly.

To run all tests:
```bash
.venv/bin/python -m pytest -q
```

## Example Output

Here's an example of the output from `experiments/hello_simulation.py`, demonstrating basic event execution and trace logging:

```
Starting simulation at t=0.0...
[00.50] EXEC: Hello
[01.00] EXEC: Simulation
Simulation finished. Executed 2 events.

Trace records:
00.00 | event_scheduled | event_time=0.5, priority=0, sequence=0
00.00 | event_scheduled | event_time=1.0, priority=0, sequence=1
00.50 | event_executed  | event_time=0.5, priority=0, sequence=0
01.00 | event_executed  | event_time=1.0, priority=0, sequence=1
```
