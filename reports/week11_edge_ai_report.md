# Week 11: Edge AI Anomaly Detection

## Question / Hypothesis

Can simple edge anomaly detection reduce WSN communication by transmitting only anomaly events while keeping missed anomalies and false alarms measurable?

## Scenario and Settings

- Seed: `2026`
- Nodes: `25`
- Timesteps: `200`
- Baseline samples: `5000`
- Baseline signal: Gaussian noise around `20.0` with std `1.0`
- Anomaly probability: `0.05`
- Anomaly magnitude: `3.0`
- Detector: rolling z-score, window size `20`

## Detector Description

Each node runs a streaming z-score detector against its own recent history. Baseline forwarding sends every reading to the sink. Edge AI mode sends only samples classified as anomalies, so detections are also the communication events.

## Metrics

The experiment reports TP, FP, TN, FN, precision, recall, F1, false-positive rate, false-negative rate, baseline packets, transmitted packets, communication saving ratio, and a simple optional packet-energy saving estimate.

Undefined precision/recall-style metrics are written as `0.0` when their denominator is empty.

## Results

- Best F1 threshold: `2.5` with F1 `0.529`, saving `0.959`, FNR `0.504`.
- Highest saving threshold: `3.5` with saving `0.985` and FNR `0.763`.

Figures:

- `reports/figures/week11_comm_saving_vs_threshold.png`
- `reports/figures/week11_fp_fn_vs_threshold.png`
- `reports/figures/week11_comm_vs_detection_tradeoff.png`
- `reports/figures/week11_signal_detection_example.png`

## Interpretation

Increasing the threshold generally raises communication saving because fewer samples are transmitted as anomaly events. The cost is lower sensitivity: false positives tend to fall, while false negatives can rise as weaker anomalies are filtered out. The threshold is therefore an explicit WSN trade-off between battery/network load and event detection quality.

## Reproducibility

```bash
.venv/bin/python experiments/week11_edge_ai_detector.py
```
