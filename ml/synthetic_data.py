from __future__ import annotations

import numpy as np

from backend.services.fraud_features import normalize_features


def generate_synthetic_dataset(
    samples: int = 6000,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    if samples < 100:
        raise ValueError("At least 100 synthetic samples are required")

    generator = np.random.default_rng(seed)
    amount = np.exp(generator.uniform(np.log(5), np.log(15_000), samples))
    hour = generator.integers(0, 24, samples)
    frequency = generator.poisson(1.1, samples)
    device_activity = generator.poisson(1.4, samples)
    log_odds = (
        -5.5
        + amount * 0.0009
        + frequency * 0.6
        + device_activity * 0.35
        + ((hour < 5) * 0.45)
        + ((amount >= 5_000) * 0.8)
    )
    fraud_probability = 1 / (1 + np.exp(-log_odds))
    labels = generator.binomial(1, fraud_probability)
    features = np.asarray([
        normalize_features(float(row[0]), int(row[1]), int(row[2]), int(row[3]))
        for row in zip(amount, hour, frequency, device_activity)
    ])
    return features, labels
