from __future__ import annotations

FEATURE_NAMES = ("amount", "hour", "frequency", "device_activity")


def normalize_features(
    amount: float,
    hour: int,
    frequency: int,
    device_activity: int,
) -> tuple[float, float, float, float]:
    return (
        min(amount / 15_000, 1.5),
        hour / 23,
        min(frequency / 60, 1.0),
        min(device_activity / 24, 1.0),
    )
