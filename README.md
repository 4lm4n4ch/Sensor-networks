# wsnsim: Wireless Sensor Network Simulator

## Project Overview

`wsnsim` is a Python-based discrete-event simulator designed for Wireless Sensor Networks (WSN). The primary goal is to provide a flexible and deterministic platform for researching various WSN protocols, topologies, and performance metrics.

The current implementation covers Weeks 1-11: a deterministic discrete-event core, radio channel model, state-based energy/lifetime model, ALOHA/CSMA MAC layer, topology/connectivity graphs, routing/data-collection baselines, link-level ACK/retry reliability, clock drift, RSSI localization, data aggregation/compression, replay-protection security overhead modeling, edge AI anomaly detection, experiments, documentation, unit tests, and an AI prompt log.

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
        -   `mac.py`: Week 4 ALOHA and simplified CSMA MAC model with deterministic collision/backoff behavior.
        -   `topology.py`: Week 5 deterministic node deployments and distance/PRR-based connectivity graphs.
        -   `routing.py`: Week 6 flooding and BFS sink-tree routing baselines with PDR, latency, hop-count, duplicate, overhead, and energy-per-bit metrics.
        -   `reliability.py`: Week 7 link-level ACK/retry ARQ model with deterministic backoff, ACK timeout handling, latency, PDR, retry, and energy metrics.
        -   `sync_localization.py`: Week 8 node clock drift, simple offset synchronization, RSSI-to-distance conversion, and least-squares 2D trilateration.
        -   `aggregation.py`: Week 9 raw forwarding, tree aggregation, delta suppression, compression accounting, and reconstruction/aggregation error metrics.
        -   `security.py`: Week 10 replay protection, simulated authentication metadata, and CPU/latency/byte overhead accounting.
        -   `edge_ai.py`: Week 11 deterministic sensor-signal generation, streaming z-score/EWMA anomaly detection, edge communication saving, and FP/FN detection metrics.
    -   `core/`: Shared neutral dataclasses used across simulator layers.
        -   `packet.py`: `Packet` dataclass for MAC, routing, reliability, energy, and channel-independent packet metadata.
        -   `link.py`: `LinkStats` dataclass for one calculated transmission attempt.
    -   `scenarios/`: Placeholder for defining specific WSN simulation scenarios (e.g., node deployment, traffic patterns).
-   `tests/`: Contains unit and integration tests for the `wsnsim` codebase.
    -   `test_core.py`: Comprehensive tests for the core simulation engine (`Scheduler`, `SimClock`, `TraceLogger`) and `RNG` and basic `metrics`.
    -   `test_channel.py`: Channel tests for distance trends, probability bounds, reproducibility, validation, and manual PRR points.
    -   `test_energy.py`: Energy tests for unit-consistent consumption, depletion clamp, validation, lifetime trends, and scheduler integration.
    -   `test_aggregation.py`: Week 9 tests for aggregation functions, raw/tree communication cost, delta suppression, error metrics, compression formulas, and deterministic synthetic readings.
    -   `test_security.py`: Week 10 tests for sequence-number replay protection, overhead accounting, deterministic metadata, and abuse-case rejection.
    -   `test_edge_ai.py`: Week 11 tests for deterministic signal generation, anomaly labels, z-score detection, confusion-matrix metrics, communication saving, threshold trade-offs, and divide-by-zero robustness.
-   `experiments/`: Contains example simulations and scripts to run various experiments.
    -   `hello_simulation.py`: A basic "hello world" example demonstrating how to set up and run a simple simulation using `wsnsim` v0.
    -   `run_sweep.py`: Placeholder for running parameter sweeps or multiple simulation runs.
    -   `week02_prr_curve.py`: Generates the Week 2 PRR-vs-distance curve.
    -   `week03_energy_lifetime.py`: Generates Week 3 lifetime-vs-duty-cycle data and plot.
    -   `week04_mac_aloha_csma.py`: Generates Week 4 ALOHA-vs-CSMA CSV and plots.
    -   `week05_topology_connectivity.py`: Generates Week 5 topology and connectivity sweep outputs.
    -   `week06_routing_compare.py`: Generates Week 6 flooding-vs-sink-tree routing comparison outputs.
    -   `week07_reliability_arq.py`: Generates Week 7 retry-limit ARQ trade-off outputs.
    -   `week08_sync_localization.py`: Generates Week 8 localization error and clock drift outputs.
    -   `week09_aggregation_compression.py`: Generates Week 9 raw/tree/delta aggregation and compression trade-off outputs.
    -   `week10_security_overhead.py`: Generates Week 10 baseline-vs-secured replay attack and overhead outputs.
    -   `week11_edge_ai_detector.py`: Generates Week 11 edge anomaly detection threshold-sweep CSV, figures, and report.
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

## Week 4: MAC Protocols

Week 4 adds a testable MAC layer in `wsnsim.models.mac` for comparing ALOHA and a simplified CSMA-style protocol. This work is separate from the Milestone 1 foundation: Milestone 1 still covers the scheduler, channel, energy model, README, tests, repository, and prompt log.

### MAC Architecture

-   `MACPacket`: packet metadata used by MAC protocols.
-   `Transmission`: one packet attempt with `start_time_s`, `duration_s`, and exclusive `end_time_s`.
-   `CollisionDomain`: shared medium state. It tracks active transmissions and marks collisions when intervals overlap on the same channel.
-   `AlohaMAC`: sends immediately on request with no carrier sensing.
-   `CSMAMAC`: senses the medium, backs off when busy, increases the contention window up to `cw_max`, and drops after `max_retries`.
-   `MACResult`: per-packet status, attempts, backoffs, collision count, delivery time, and delay.

The MAC classes are scheduler-compatible: a send request is scheduled at an absolute simulation time, and transmission-end events are scheduled by the MAC. Same-time scheduler events remain deterministic because the existing scheduler orders by time, then priority, then sequence number.

### Collision Definition

Transmission intervals are half-open:

```text
[start_time_s, start_time_s + duration_s)
```

Two transmissions collide if both are on the same `channel_id` and their active intervals overlap:

```text
start_a < end_b and start_b < end_a
```

This means equal start times collide, partially overlapping intervals collide, and back-to-back packets where one ends exactly when the next starts do not collide. A collided packet is not delivered. A non-collided packet is delivered only if the optional packet-level channel hook also allows delivery; by default the hook always succeeds.

### Carrier Sensing

For Week 4, carrier sensing is intentionally simple: the channel is busy if `CollisionDomain.is_busy(time_s, channel_id)` finds an active transmission whose interval contains the sensing time. RSSI thresholds, CCA durations, hidden terminals, capture effect, and interference power summation are left for later weeks.

### CSMA Backoff

The simplified CSMA backoff uses a local deterministic `numpy.random.default_rng(seed)`:

```text
random_slots = rng.integers(0, CW + 1)
backoff_time = random_slots * slot_time_s
```

When the channel is busy, `CW` grows toward `cw_max`. If the packet still cannot access the channel after `max_retries`, it is dropped with reason `max_retries_busy`.

This is not a full IEEE 802.15.4 CSMA/CA model. It does not implement superframes, beacons, ACKs, CCA timing, radio turnaround, the NB/BE state machine, or energy-detection thresholds. It is a deliberately small model for timing, overlap collisions, reproducible backoff, and first-order energy hooks.

### Energy Hooks

If an `EnergyModel` is supplied for a node, MAC events trigger state transitions:

-   TX when a transmission starts.
-   IDLE when a transmission ends or while waiting for a future retry.
-   RX briefly during carrier sensing in CSMA.
-   SLEEP only when scheduled explicitly outside this MAC layer.

Carrier sensing is instantaneous in Week 4, so RX sensing energy is represented as a transition hook but does not yet consume a positive-duration listening interval.

### ALOHA / CSMA / TDMA Comparison

| Protocol | Collision behavior | Delay | Energy efficiency | Complexity | Synchronization | Low-power WSN suitability |
| --- | --- | --- | --- | --- | --- | --- |
| ALOHA | Collides whenever transmissions overlap; no prevention | Low when traffic is light, poor under load due retries/losses | Often wasteful under contention because collided TX energy is lost | Very low | None | Useful for sparse, simple nodes; weak at higher load |
| CSMA | Reduces collisions by sensing before TX; still simplified here | Backoff adds delay but improves delivery under contention | Better than ALOHA under moderate load; sensing/backoff costs energy | Moderate | No global schedule required | Good baseline for low-power WSN contention access |
| TDMA | Avoids collisions if schedule is correct | Predictable; may wait for assigned slot | Efficient when duty-cycled tightly, but idle listening must be managed | Higher | Requires time synchronization | Strong for planned periodic traffic; less flexible for bursty traffic |

### Week 4 Sanity Checklist

-   Collision is defined as overlapping transmission intervals, not only equal start times.
-   Random backoff uses a deterministic seed.
-   Same-time events are handled deterministically by scheduler priority and sequence.
-   Carrier sensing is clearly defined as active-interval overlap at the sensing instant.
-   Retry limits are enforced and produce packet drops.
-   Packet durations are calculated from size and bitrate or passed explicitly as seconds.
-   Energy hooks affect TX/RX/IDLE states when an `EnergyModel` is provided; positive-duration sensing energy is documented as a limitation.
-   ALOHA and CSMA experiments use the same generated traffic and seed conditions.

### Running Week 4 Tests

```bash
.venv/bin/python -m pytest -q tests/test_mac.py
```

### Running The MAC Experiment

```bash
.venv/bin/python experiments/week04_mac_aloha_csma.py
```

The experiment compares ALOHA and CSMA over three traffic loads and saves:

```text
reports/week04_mac_aloha_csma.csv
reports/figures/week04_mac_pdr_vs_load.png
reports/figures/week04_mac_collision_delay_vs_load.png
```

## Week 5: Topology and Connectivity Graphs

Week 5 adds deterministic node deployment and graph construction in `wsnsim.models.topology`. The module is intentionally routing-free: it builds connectivity information that later routing work can consume without committing to a route-selection algorithm yet.

### Topology Architecture

-   `Node`: stable node id, `(x_m, y_m)` position, and role such as `sensor` or `sink`.
-   `TopologyConfig`: total node count, deployment area dimensions in meters, RNG seed, sink placement, communication range, and optional PRR threshold.
-   `Topology`: node storage, Euclidean distance helpers, neighbor lookup, connected components, sink reachability, and average degree.

`node_count` is the total number of nodes. When `sink_position` is not `none`, node `0` is reserved as the sink and the remaining nodes are sensors. Supported sink positions are `center`, `corner`, `random`, `none`, or an explicit `(x_m, y_m)` tuple inside the area.

### Deployment Strategies

-   `Topology.random_uniform(config)`: places sensor nodes independently and uniformly in the configured rectangular area using `numpy.random.default_rng(config.seed)`.
-   `Topology.grid(config)`: places sensor nodes on a deterministic row-major grid over the configured area.
-   `Topology.clustered(config, cluster_count=..., cluster_std_m=...)`: optional clustered placement around seeded random cluster centers, clipped to the deployment area.

All stochastic placement is local to the topology generator. Same config plus same seed produces identical node positions; no global random state is used.

### Neighbor Graphs

Distance-threshold graphs connect two nodes when:

```text
distance_m <= communication_range_m
```

PRR-threshold graphs connect two nodes when the supplied channel reports:

```text
channel_prr(distance_m) >= prr_threshold
```

The PRR graph uses `LogDistanceChannel.calculate_link_stats(...)` or any compatible channel object. Shadowing is disabled by default for deterministic graph construction, but can be enabled explicitly.

The graph API supports:

-   `neighbors(node_id)`: neighbor lookup.
-   `connected_components()`: undirected graph components.
-   `all_nodes_can_reach_sink()`: full sink connectivity check.
-   `sink_reachability_ratio()`: fraction of nodes in the sink component.
-   `average_degree()`: mean node degree.

### Running Week 5 Tests

```bash
.venv/bin/python -m pytest -q tests/test_topology.py
```

To run the complete suite:

```bash
.venv/bin/python -m pytest -q
```

### Running The Topology Experiment

```bash
.venv/bin/python experiments/week05_topology_connectivity.py
```

The experiment uses seed `2026`, a `100 m x 100 m` area, `40` total nodes, and a centered sink. It saves:

```text
reports/week05_topology_connectivity.csv
reports/figures/week05_topology_graph.png
reports/figures/week05_connectivity_vs_range.png
```

The topology figure shows node positions in meters, neighbor links, and the highlighted sink. The range-sweep figure reports communication range in meters against average node degree and the fraction of nodes reachable from the sink.

## Week 6: Routing and Data Collection

Week 6 adds routing baselines in `wsnsim.models.routing` for static WSN data collection to one sink. The protocols consume the Week 5 `Topology` neighbor graph and use deterministic neighbor-link delivery by default. An optional channel-based probabilistic one-hop success mode is available, but the Week 6 experiment keeps links deterministic so Flooding and Sink-tree use identical topology, traffic, seed, payload size, and link assumptions.

### Routing Architecture

-   `RoutingPacket`: packet id, source, destination/sink, current/previous node, creation time, TTL, payload bits, and hop count.
-   `RouteDecision`: `FORWARD`, `DELIVER`, or `DROP`, with a reason and next-hop ids.
-   `RoutingMetrics`: generated/delivered/dropped packets, duplicates, total hops, total latency, total energy, control overhead, PDR, average latency, average hop count, and energy per delivered/generated bit.
-   `RoutingConfig`: hop delay, per-bit TX/RX energy, RNG seed, and optional channel-success settings.

### Flooding Routing

`FloodingRouting` forwards each packet to all neighbors except the previous sender. A per-router seen-cache keyed by `(packet_id, node_id)` suppresses duplicate copies, and TTL prevents infinite propagation on cyclic graphs. Delivery is counted once when the packet first reaches the sink; later copies at the sink are counted as duplicates. Flooding overhead is reported through duplicate count and `control_overhead_packets`.

### Sink-tree Routing

`SinkTreeRouting` builds a BFS shortest-hop tree rooted at the sink and exposes `parent_map` plus `hop_distance_map`. Each node forwards only to its parent toward the sink. Nodes outside the sink component are dropped cleanly with reason `unreachable_to_sink`. ETX/RPL, ACKs, retries, queueing, mobility, asymmetric links, and congestion are intentionally not modeled in Week 6.

### Metrics

The routing metrics include:

```text
PDR = delivered_packets / generated_packets
average_latency_s = total_latency_s / delivered_packets
average_hop_count = total_hops / delivered_packets
energy_per_delivered_bit_j = total_energy_j / delivered_payload_bits
energy_per_generated_bit_j = total_energy_j / generated_payload_bits
```

Energy accounting is a simple documented per-bit TX/RX model, not a full radio state trace through the Week 3 `EnergyModel`.

### Running Week 6 Tests

```bash
.venv/bin/python -m pytest -q tests/test_routing.py
```

To run the complete suite:

```bash
.venv/bin/python -m pytest -q
```

### Running The Routing Experiment

```bash
.venv/bin/python experiments/week06_routing_compare.py
```

The experiment uses seed `2026`, `25` total nodes, a `100 m x 100 m` random-uniform topology, centered sink, `64 B` payloads, TTL `10`, and deterministic neighbor-link delivery. It sweeps communication range over:

```text
15, 20, 25, 30, 35, 40, 45, 50, 60 m
```

For each range, the same deployment seed and traffic pattern are used for Flooding and Sink-tree BFS. The CSV includes average degree and sink reachability ratio so the routing metrics can be interpreted against graph connectivity. The figures plot metric trends against communication range:

```text
reports/week06_routing_compare.csv
reports/figures/week06_routing_pdr.png
reports/figures/week06_routing_latency.png
reports/figures/week06_routing_energy_per_bit.png
```

In this deterministic-link setup, Flooding and Sink-tree BFS have the same reachability-limited PDR and first-delivery hop latency, but Flooding shows much higher duplicate/control overhead and energy per bit. The energy figure uses a log-scale y-axis so both protocols remain visible.

## Week 7: Reliability and ARQ

Week 7 adds link-level reliability in `wsnsim.models.reliability`. The model implements ACK-based ARQ for one hop: each data transmission expects an ACK, retries after an ACK timeout, applies deterministic seeded backoff, and drops the packet after `retry_limit` retries. This is link-layer behavior, not end-to-end TCP-style reliability.

### Reliability Architecture

-   `ReliabilityConfig`: ACK enable flag, retry limit, ACK timeout, exponential backoff parameters, RNG seed, ACK size, bitrate, link delays, channel settings, and simple per-bit TX/RX energy costs.
-   `TransmissionAttempt`: one data attempt with packet id, source/destination, attempt index, send time, ACK deadline, data/ACK success flags, and success/failure state.
-   `ReliabilityMetrics`: generated, delivered, failed, total attempts, retries, ACK packets, timeouts, PDR, average attempts per packet, average latency, and total energy.
-   `LinkReliabilityARQ`: scheduler-compatible ARQ engine that schedules send, data delivery, ACK, timeout, and retry events.

### ACK/Retry Semantics

`retry_limit` is the number of retries after the first data transmission, so the maximum data attempts per packet is:

```text
max_attempts = retry_limit + 1
```

For each data attempt:

1.  Data TX energy is charged at the sender.
2.  The channel or injected deterministic decision decides whether data arrives.
3.  If data arrives and ACKs are enabled, ACK TX energy is charged at the receiver.
4.  If the ACK arrives before `ack_timeout_s`, the packet is marked delivered exactly once.
5.  If data or ACK is lost, the sender waits until timeout, backs off, and retries until the retry limit is exhausted.

ACK packets have their own size and energy cost. If an ACK is lost, the receiver may already have seen the data frame, but the sender still retries because it did not receive confirmation. Duplicate successful deliveries are not counted multiple times in the link-level metrics.

### Running Week 7 Tests

```bash
.venv/bin/python -m pytest -q tests/test_reliability.py
```

To run the complete suite:

```bash
.venv/bin/python -m pytest -q
```

### Running The Reliability Experiment

```bash
.venv/bin/python experiments/week07_reliability_arq.py
```

The experiment sweeps retry limits:

```text
0, 1, 2, 3, 5
```

It uses a single lossy link over the Week 2 log-distance channel with ACKs enabled and reports the delivery/energy/latency trade-off. Outputs are saved to:

```text
reports/week07_reliability_arq.csv
reports/figures/week07_reliability_arq_tradeoff.png
```

Expected interpretation: increasing `retry_limit` should usually raise PDR, while also increasing attempts, ACK traffic, energy use, and delivery latency for packets that require retries.

## Week 8: Time Synchronization and Localization

Week 8 adds `wsnsim.models.sync_localization`, covering a simple sensor-node clock drift model and RSSI-based 2D localization with anchor nodes. The module is NumPy-only and keeps synchronization/localization separate from routing and MAC behavior.

### Clock Drift Model

-   `ClockConfig`: node id, `drift_ppm`, and `offset_s`.
-   `NodeClock`: converts between true simulation time and raw local clock time.
-   `TimeSyncResult`: optional one-shot offset synchronization report.

The ppm conversion is:

```text
drift_factor = 1.0 + drift_ppm * 1e-6
local_time = offset_s + true_time_s * drift_factor
```

Positive drift makes the local clock run fast; negative drift makes it run slow. `NodeClock.true_time(local_time_s)` inverts the raw clock mapping. The optional `synchronize_offset(...)` method estimates and applies only an instantaneous offset correction; it does not estimate drift rate like TPSN or FTSP.

The clock-drift experiment plots error in milliseconds so sub-second drift remains readable over a one-hour window:

```text
clock_error_s = true_time_s * drift_ppm * 1e-6
```

For example, `100 ppm` produces about `0.36 s` of clock error after `1 hour` (`360 ms`).

### RSSI Localization Model

Localization uses known-position anchors and estimated ranges from RSSI:

-   `AnchorNode`: anchor id and known `(x_m, y_m)` position.
-   `UnknownNode`: true position used for simulation validation.
-   `RSSIMeasurement`: anchor id, RSSI in dBm, and inverse estimated distance.
-   `LocalizationResult`: estimated position, true position, error, success flag, and failure reason.

The log-distance model is:

```text
path_loss_db = PL(d0) + 10 * n * log10(d / d0)
rssi_dbm = tx_power_dbm - path_loss_db + noise_db
estimated_distance = d0 * 10 ** ((tx_power_dbm - PL(d0) - rssi_dbm) / (10 * n))
```

Distances are validated as positive, and RSSI inversion rejects non-finite values. Noiseless RSSI measurements invert back to the original distance for distances at or above `d0`.

### Trilateration

`trilaterate_2d(...)` implements closed-form linear least squares using `numpy.linalg.lstsq`. It supports 3 or more anchors by subtracting the first range equation from all others. The solver returns a clear `LocalizationError` for fewer than 3 anchors, non-positive ranges, rank-deficient collinear geometry, or extremely ill-conditioned anchor layouts.

### Running Week 8 Tests

```bash
.venv/bin/python -m pytest -q tests/test_sync_localization.py
```

To run the complete suite:

```bash
.venv/bin/python -m pytest -q
```

### Running The Sync/Localization Experiment

```bash
.venv/bin/python experiments/week08_sync_localization.py
```

The experiment uses four anchors at square corners `(0,0)`, `(100,0)`, `(0,100)`, and `(100,100)`, with `80` seeded random unknown nodes inside a `100 m x 100 m` area. It sweeps RSSI noise/shadowing:

```text
0, 1, 2, 4, 6, 8 dB
```

For each sigma, the summary CSV reports mean, median, P25, P75, P90, and maximum localization error over successful localizations, plus failed localization count and failure rate. A detailed per-node CSV is also written. A localization is counted as failed if trilateration fails, the estimate is NaN/infinite, or the estimated position falls outside the generous `[-100, 200] m` bounds used for this `100 m x 100 m` scenario.

Outputs are saved to:

```text
reports/week08_localization_error.csv
reports/week08_localization_details.csv
reports/figures/week08_localization_error_boxplot.png
reports/figures/week08_localization_failure_rate.png
reports/figures/week08_localization_scatter_clean.png
reports/figures/week08_clock_drift_error.png
```

Expected interpretation: localization error is near zero at `sigma = 0 dB` and the boxplot spread increases as RSSI noise/shadowing increases. Boxplot outliers are shown because RSSI range errors are skewed and can produce large position outliers. Failed or rejected localizations are excluded from the error boxplot and counted separately in the failure-rate plot. The clean scatter plot uses `sigma = 4 dB`, shows all true and estimated points, and draws error lines only for a deterministic 12-node sample so the figure remains readable. The clock figure shows error accumulation for `-50`, `0`, `+50`, and `+100 ppm` drift over one hour with the y-axis in milliseconds.

### Week 8 Limitations

The localization model assumes a known transmit power and path-loss exponent, independent RSSI noise per anchor, static anchors, and 2D geometry. It does not model NLOS bias, multipath correlation, anchor uncertainty, mobile nodes, robust outlier rejection, covariance estimates, or packet-level MAC/routing effects during ranging.

## Week 10: Security in WSN

Week 10 adds `wsnsim.models.security`, a basic security layer for M3 preparation. It models replay protection with sequence numbers, simulated nonce/authentication metadata, and explicit security overhead in bytes, CPU energy, and processing latency. It does not implement real cryptography; authentication is represented by configurable metadata and per-byte processing costs.

### Security Model

-   `SecurityConfig`: enables/disables the layer, controls replay protection, `auth_tag_bytes`, `nonce_bytes`, sequence-window placeholder, CPU generation cost, verification cost, latency cost, and RNG seed.
-   `SecurePacketMetadata`: sender id, receiver id, sequence number, nonce, auth-tag length, and optional timestamp.
-   `SecurityDecision`: accepted/rejected result with reason, overhead bytes, CPU energy, and latency overhead.
-   `SecurityMetrics`: cumulative checked, accepted, rejected, replay-rejected, byte-overhead, CPU-energy, and latency counters.
-   `SecurityLayer`: deterministic metadata generation, replay checks, and metric accounting.

Replay protection uses a strict high-water mark per `(sender_id, receiver_id)` flow. A packet is accepted only if its sequence number is greater than the last accepted sequence number for that flow. Duplicate or old sequence numbers are rejected as replay attempts. `sequence_window` is reserved for future sliding-window behavior; Week 10 keeps strict in-order checks so the abuse case is easy to audit.

The baseline mode intentionally has replay protection disabled. Therefore, `replay_rejected = 0` in baseline does not mean the baseline is safer; it means replayed packets are accepted and passed upward. The experiment CSV records both `replay_accepted` and `replay_rejected` so this distinction is explicit.

### Overhead Assumptions

Secured packets add a fixed nonce plus authentication-tag cost:

```text
security_overhead_bytes_per_packet = nonce_bytes + auth_tag_bytes
```

With the Week 10 experiment defaults, this is `4 B + 8 B = 12 B/packet`. Because that per-packet cost is fixed, an overhead-bytes-per-packet plot is flat by design. The main byte-cost figures therefore use total transmitted bytes and the security overhead ratio:

```text
security_overhead_ratio = total_security_overhead_bytes / total_transmitted_bytes
```

CPU overhead is simulated as per-byte authentication generation plus verification:

```text
processed_bytes = payload_bytes + security_overhead_bytes
cpu_energy_j = processed_bytes * (cpu_cost_per_byte_j + verify_cost_per_byte_j)
```

For replayed packets in the experiment, the attacker retransmits old bytes, so the receiver still pays verification cost while the legitimate sender does not pay a new generation cost. Latency overhead is a configurable per-byte processing delay. The CPU figure reports total CPU security overhead in joules; baseline is zero because no simulated authentication or verification work is performed.

### Threat Checklist

The Week 10 threat checklist is saved at:

```text
reports/week10_threat_checklist.md
```

It covers assets, attacker model, attack surface, threats, mitigations, and residual risks, including replay attack, DoS/jamming, sinkhole, Sybil, spoofing, eavesdropping, and packet injection.

### Abuse-Case Test

`tests/test_security.py` includes a replay abuse case where a legitimate packet is accepted, the same metadata is replayed, and the replay is rejected with a replay reason. It also checks increasing sequence acceptance, duplicate and old sequence rejection, disabled-security behavior, byte/CPU overhead formulas, metrics, deterministic behavior, and independent sender tracking.

### Running Week 10 Tests

```bash
.venv/bin/python -m pytest -q tests/test_security.py
```

### Running The Security Experiment

```bash
.venv/bin/python experiments/week10_security_overhead.py
```

The experiment compares baseline traffic without security against replay protection enabled using seed `2026`, `1000` legitimate packets, `64 B` payloads, `8 B` auth tags, `4 B` nonces, and replay attack rates:

```text
0.0, 0.05, 0.1, 0.2, 0.4
```

Outputs are saved to:

```text
reports/week10_security_overhead.csv
reports/figures/week10_replay_accept_reject_vs_attack_rate.png
reports/figures/week10_total_transmitted_bytes.png
reports/figures/week10_security_overhead_ratio.png
reports/figures/week10_security_cpu_energy.png
reports/figures/week10_security_overhead_bytes_per_packet.png
```

Expected interpretation: the grouped replay-abuse figure makes the comparison explicit. Baseline accepts replayed packets as the attack rate increases, while replay protection rejects those duplicate/old sequence numbers. Replay protection transmits more total bytes because each packet carries the fixed 12 B security metadata. The overhead-ratio figure is positive and roughly stable because payload size and security metadata size are fixed, so the ratio is less informative than the total-bytes comparison but still documents the fixed per-packet cost. CPU security overhead is reported as total joules and is positive for replay protection, increasing as more replayed packets must be verified.

### Week 10 Limitations

The model does not provide encryption, real MAC verification, key exchange, node capture handling, physical-layer jamming simulation, sinkhole/Sybil routing defenses, or out-of-order sliding-window replay handling. It is intentionally a small, deterministic security accounting layer that prepares the simulator for the M3 Security focus by making replay abuse and protection costs measurable.

## Week 11: Edge AI in WSN

Week 11 adds `wsnsim.models.edge_ai`, a deterministic edge anomaly-detection layer for sensor readings. The goal is to measure how much communication can be saved when nodes transmit only anomaly events instead of forwarding every raw sample, while explicitly tracking false positives, false negatives, and detection quality.

### Edge AI Motivation

WSN nodes are often energy- and bandwidth-constrained. If a node can run a small local detector, it can suppress routine readings and transmit only events that look anomalous. This reduces packet load, but the threshold must be chosen carefully: a lower threshold catches more anomalies and creates more false alarms, while a higher threshold saves more communication and can miss weaker events.

### Signal Generator

`SignalGeneratorConfig` controls a local `numpy.random.default_rng(seed)` signal generator:

-   `n_nodes` and `n_timesteps` define the sample grid.
-   `baseline_mean` and `baseline_std` define normal Gaussian readings with a small smooth temporal and spatial component.
-   `anomaly_probability` injects labeled anomaly events.
-   `anomaly_magnitude` adds a deterministic-size spike to anomalous samples.

Each generated `SensorSample` stores `node_id`, `timestamp_s`, `value`, and `is_anomaly`, so the detector can be evaluated against ground truth.

### Detector

The main Week 11 detector is a streaming per-node z-score detector. Each node compares the current sample against its recent rolling history:

```text
score = abs(value - mean(history)) / std(history)
predicted_anomaly = score > threshold
```

The module also includes a simple EWMA mode for future comparisons. Warm-up samples without enough history are treated as normal. If a metric denominator is empty, the module returns `0.0` instead of raising or producing NaN.

### Communication-Saving Model

Baseline mode transmits every sample:

```text
baseline_packets = n_nodes * n_timesteps
```

Edge AI mode transmits only samples classified as anomalies:

```text
transmitted_packets = predicted_anomaly_count
communication_saving_ratio = 1 - transmitted_packets / baseline_packets
```

The experiment also reports an optional first-order `energy_saved_j` estimate using a fixed packet-energy cost.

### FP/FN Trade-Off

The Week 11 threshold sweep records TP, FP, TN, FN, precision, recall, F1, false-positive rate, and false-negative rate. In the default scenario, increasing the z-score threshold raises communication saving because fewer packets are sent, lowers false positives, and increases false negatives. This makes the detector threshold a direct knob for the M3 Edge AI trade-off between network lifetime and missed-event risk.

### Running Week 11 Tests

```bash
.venv/bin/python -m pytest -q tests/test_edge_ai.py
```

### Running The Edge AI Experiment

```bash
.venv/bin/python experiments/week11_edge_ai_detector.py
```

The experiment uses seed `2026`, `25` nodes, `200` timesteps, anomaly probability `0.05`, and thresholds:

```text
1.5, 2.0, 2.5, 3.0, 3.5
```

Outputs are saved to:

```text
reports/week11_edge_ai_detector.csv
reports/week11_edge_ai_report.md
reports/figures/week11_comm_saving_vs_threshold.png
reports/figures/week11_fp_fn_vs_threshold.png
reports/figures/week11_comm_vs_detection_tradeoff.png
reports/figures/week11_signal_detection_example.png
```

### M3 Support

This module can support an M3 Edge AI focus by providing a reproducible anomaly-detection pipeline, detector-quality metrics, and communication/energy trade-off plots. It can also combine naturally with the Week 10 security focus: anomaly events can be secured with replay protection, letting M3 compare Security + AI costs against communication savings.

## Milestone 3 Summary

Milestone 3 is prepared as a **Combined Security and Edge AI** submission. The security side is covered by `wsnsim.models.security`, `tests/test_security.py`, `experiments/week10_security_overhead.py`, `reports/week10_threat_checklist.md`, `reports/week10_security_overhead.csv`, and the Week 10 figures under `reports/figures/`. The Edge AI side is covered by `wsnsim.models.edge_ai`, `tests/test_edge_ai.py`, `experiments/week11_edge_ai_detector.py`, `reports/week11_edge_ai_detector.csv`, `reports/week11_edge_ai_report.md`, and the Week 11 figures under `reports/figures/`.

The concise submission evidence report is:

```text
reports/m3_summary.md
```

Run the full M3 verification path with:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python experiments/week10_security_overhead.py
.venv/bin/python experiments/week11_edge_ai_detector.py
```

### Week 11 Limitations

The detector is intentionally lightweight. It does not train a learned model, adapt thresholds automatically, model concept drift, compress event payloads, account for CPU inference energy, or simulate adversarial examples. The synthetic anomalies are additive spikes, so future work could add gradual drifts, stuck-at faults, spatially correlated events, and integration with routing/MAC/energy state traces.

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

`wsnsim` emphasizes robust testing to ensure correctness and deterministic behavior across the simulator modules.

-   **What is tested**: Unit tests cover core components like the `Scheduler`, `SimClock`, `TraceLogger`, and `RNG` reproducibility; channel behavior such as path loss/RSSI/SNR trends, PRR bounds, validation, and reproducible shadowing; energy behavior such as `energy_j = power_w * duration_s`, depletion clamping, state transitions, lifetime trends, and scheduler-driven integration; MAC collision/backoff behavior; topology reproducibility, coordinate bounds, grid placement, distance graphs, connected components, and sink reachability; routing behavior including flooding TTL/duplicates, sink-tree parent maps, unreachable drops, deterministic behavior, and metric sanity checks; reliability behavior including data loss, ACK loss, retry limits, deterministic backoff, PDR, latency, and energy accounting; Week 8 clock/localization behavior including ppm conversion, offset handling, inverse clock conversion, RSSI-distance inversion, least-squares trilateration, ill-conditioned geometry handling, noiseless localization accuracy, and deterministic noisy measurements; Week 10 security behavior including replay rejection, independent sender sequence tracking, overhead formulas, metrics, and disabled-security baseline behavior; and Week 11 edge AI behavior including deterministic signals, ground-truth anomaly labels, z-score detection, FP/FN metrics, communication saving, threshold trade-offs, and divide-by-zero-safe metric formulas.
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
