# Week 10 Threat Checklist: WSN Security

## Assets

- Sensor readings and aggregated application data.
- Node identity, sequence numbers, nonces, and routing metadata.
- Sink availability and integrity of data collection.
- Node battery energy and CPU budget.
- Network topology, neighbor relationships, and localization information.
- Experiment reproducibility: seeds, traces, and generated metrics.

## Attacker Model

- External attacker can overhear, replay, inject, or jam radio packets.
- Attacker may have a commodity radio near part of the WSN but does not control
  the sink.
- Attacker can replay captured packets exactly, including metadata.
- Attacker can spoof sender identifiers unless authentication is enabled.
- Cryptographic key compromise, physical node capture, and side-channel attacks
  are out of scope for Week 10 but remain important residual risks.

## Attack Surface

- Broadcast wireless channel.
- Packet headers: sender id, receiver id, sequence number, and nonce.
- Routing control messages and neighbor discovery.
- ACK/retry behavior that can be abused to waste energy.
- Sink-facing collection path and aggregation points.
- Sensor-node CPU and battery resources.

## Threats

- Replay attack: captured valid packets are retransmitted to create stale data,
  duplicate events, or extra forwarding work.
- DoS/jamming: radio interference prevents packet delivery or forces retries.
- Sinkhole: a malicious node advertises attractive routes and attracts traffic.
- Sybil: one device claims many identities to distort topology, voting, or
  aggregation.
- Spoofing: attacker forges a sender identity and injects false readings.
- Eavesdropping: passive listener observes readings, locations, or traffic
  patterns.
- Packet injection: attacker creates arbitrary packets to pollute data,
  trigger alarms, or drain energy.

## Mitigations

- Sequence-number replay protection per sender/receiver flow.
- Nonce and authentication-tag metadata to model freshness and message
  authentication overhead.
- Drop duplicate or old sequence numbers before upper layers process them.
- Count CPU, latency, and byte overhead so security costs are visible in energy
  and performance studies.
- Use deterministic seeds in experiments so abuse-case behavior is reproducible.
- Future M3 work should add authenticated neighbor discovery, route validation,
  rate limiting, and key-management assumptions.

## Residual Risks

- Week 10 simulates authentication cost but does not implement real
  cryptography, encryption, key exchange, or key compromise behavior.
- Strict sequence checks reject out-of-order packets; a future sliding window is
  needed for lossy multi-hop traffic with reordering.
- Jamming and physical-layer DoS are listed but not yet simulated.
- Sinkhole, Sybil, spoofing, and injection require additional routing and
  identity models to evaluate fully.
- Eavesdropping is not mitigated without encryption, which is outside this
  week.
