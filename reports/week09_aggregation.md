# Week 09 - Aggregation and Compression

Week 9 implements in-network processing for WSN traffic. The model compares raw
forwarding, tree aggregation, and delta-threshold suppression.

## Evidence

- Module: `wsnsim/models/aggregation.py`
- Tests: `tests/test_aggregation.py`
- Experiment: `experiments/week09_aggregation_compression.py`
- CSV: `reports/week09_aggregation_compression.csv`
- Figure: `reports/figures/week09_aggregation_compression_tradeoff.png`

## Metrics

- Transmitted packets and bytes.
- Communication saving ratio.
- Reconstruction error with MSE and MAE.

## Interpretation

Higher delta thresholds reduce communication but increase reconstruction error.
Tree aggregation reduces network traffic compared with raw forwarding when the
sink only needs aggregate values.
