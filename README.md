# wsnsim: Wireless Sensor Network Simulator (Week 1 - v0 Core)

## Project Overview

`wsnsim` is a Python-based discrete-event simulator designed for Wireless Sensor Networks (WSN). The primary goal is to provide a flexible and deterministic platform for researching various WSN protocols, topologies, and performance metrics.

**Week 1 Implementation (wsnsim v0)** focuses on building the minimal core of the simulator. This includes the fundamental discrete-event simulation engine, a robust scheduling mechanism, time handling, basic logging/tracing, and initial unit tests to ensure correctness and reproducibility.

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
    -   `models/`: Placeholder for various WSN node and network models (e.g., radio, sensor, battery models).
    -   `scenarios/`: Placeholder for defining specific WSN simulation scenarios (e.g., node deployment, traffic patterns).
-   `tests/`: Contains unit and integration tests for the `wsnsim` codebase.
    -   `test_core.py`: Comprehensive tests for the core simulation engine (`Scheduler`, `SimClock`, `TraceLogger`) and `RNG` and basic `metrics`.
    -   `test_channel.py`: Basic tests for the placeholder channel model.
-   `experiments/`: Contains example simulations and scripts to run various experiments.
    -   `hello_simulation.py`: A basic "hello world" example demonstrating how to set up and run a simple simulation using `wsnsim` v0.
    -   `run_sweep.py`: Placeholder for running parameter sweeps or multiple simulation runs.
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

## Installation & Running

To set up and run `wsnsim`, follow these steps:

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/wsnsim.git
    cd wsnsim
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

`wsnsim` emphasizes robust testing to ensure the correctness and deterministic behavior of the simulation engine.

-   **What is tested**: Unit tests cover core components like the `Scheduler`, `SimClock`, `TraceLogger`, and `RNG` reproducibility, as well as basic metrics.
-   **Deterministic Testing Approach**: Tests for the `Scheduler` specifically verify that events are executed in the correct chronological order, and that tie-breaking rules (priority, then sequence) are strictly followed, irrespective of the order events are scheduled.
-   **Reproducibility**: The `RNG` tests explicitly confirm that simulations initialized with the same seed produce identical sequences of random numbers, ensuring that simulation results can be reproduced exactly.

To run all tests:
```bash
pytest
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
