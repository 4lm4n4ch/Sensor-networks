# Milestone 3 - Security and Edge AI

## Focus

Combined focus. Week 10 provides a replay-protection security module and overhead experiment, and Week 11 provides a deterministic Edge AI anomaly detector with communication-saving and FP/FN trade-off measurements.

## Implemented modules

- Security: replay protection, simulated nonce/authentication-tag overhead, CPU/latency overhead accounting, and threat checklist.
- Edge AI: deterministic synthetic signal generator, rolling z-score anomaly detector, communication-saving experiment, and detection-quality metrics.

## Security evidence

- Threat model/checklist: `reports/week10_threat_checklist.md`.
- Security module: `wsnsim/models/security.py`.
- Abuse-case test: `tests/test_security.py::test_replay_attack_is_rejected`.
- Main security experiment: `experiments/week10_security_overhead.py`.
- Main security results: `reports/week10_security_overhead.csv`.
- Main security figures:
  - `reports/figures/week10_replay_accept_reject_vs_attack_rate.png`
  - `reports/figures/week10_total_transmitted_bytes.png`
  - `reports/figures/week10_security_overhead_ratio.png`
  - `reports/figures/week10_security_cpu_energy.png`

Short interpretation: baseline/no-security mode deliberately accepts replayed packets and reports zero security overhead. Replay-protection mode accepts legitimate increasing sequence numbers and rejects duplicate or old sequence numbers. In the generated sweep, at replay attack rate `0.4`, baseline accepts `400` replay packets, while replay protection rejects `400` replay packets. The protected mode pays a fixed `12 B/packet` metadata cost plus modeled CPU and latency overhead.

## Edge AI evidence

- Detector module: `wsnsim/models/edge_ai.py`.
- Detector description/report: `reports/week11_edge_ai_report.md`.
- Main Edge AI experiment: `experiments/week11_edge_ai_detector.py`.
- Main Edge AI results: `reports/week11_edge_ai_detector.csv`.
- Main Edge AI figures:
  - `reports/figures/week11_comm_saving_vs_threshold.png`
  - `reports/figures/week11_fp_fn_vs_threshold.png`
  - `reports/figures/week11_comm_vs_detection_tradeoff.png`
  - `reports/figures/week11_signal_detection_example.png`

Short interpretation: baseline communication sends all `5000` samples. Edge AI mode sends only samples predicted as anomalies. The threshold sweep shows the intended trade-off: threshold `1.5` transmits `827` packets with saving `0.835` and false-negative rate `0.151`; threshold `3.5` transmits only `75` packets with saving `0.985` but false-negative rate `0.763`. The best generated F1 score is at threshold `2.5`.

## Reproducibility

```bash
.venv/bin/python -m pytest -q
.venv/bin/python experiments/week10_security_overhead.py
.venv/bin/python experiments/week11_edge_ai_detector.py
```

## Known limitations

- Security simulates authentication metadata and processing overhead, but does not implement real cryptography, encryption, key exchange, or node-capture handling.
- Replay protection uses a strict per-flow sequence high-water mark, so out-of-order delivery is treated as old/replayed traffic rather than accepted through a sliding window.
- DoS/jamming, sinkhole, Sybil, spoofing defenses, and packet-level route integration are documented but not fully simulated.
- Edge AI uses a lightweight analytic z-score detector rather than a trained model.
- Edge AI communication savings are packet-count based and do not yet integrate MAC contention, routing, radio loss, security wrapping, or inference CPU energy.
