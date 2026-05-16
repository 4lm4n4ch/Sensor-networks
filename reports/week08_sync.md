# Week 08 - Synchronization

Week 8 adds deterministic clock-drift and RSSI-localization support in
`wsnsim.models.sync_localization`.

Main command:

```bash
python experiments/week08_sync_localization.py
```

Generated artifacts:

- `reports/week08_localization_error.csv`
- `reports/week08_localization_details.csv`
- `reports/figures/week08_clock_drift_error.png`
- `reports/figures/week08_localization_error_boxplot.png`
- `reports/figures/week08_localization_failure_rate.png`
- `reports/figures/week08_localization_scatter_clean.png`

The synchronization model covers ppm clock drift and one-shot offset
correction. The localization model uses RSSI-to-distance conversion and
least-squares 2D trilateration. The figures show clock error growth over time
and localization error/failure trends as RSSI noise increases.
