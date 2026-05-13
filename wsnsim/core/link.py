"""Link-level transmission statistics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkStats:
    """Computed values for a single radio transmission attempt."""

    distance_m: float
    effective_distance_m: float
    shadowing_db: float
    path_loss_db: float
    rssi_dbm: float
    snr_db: float
    snr_linear: float
    prr_logistic: float
    ber: float
    per: float
    prr_ber: float
    success: bool | None
