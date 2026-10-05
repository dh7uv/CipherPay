"""Train a demonstration fraud classifier from deterministic synthetic data."""
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

ROOT = Path(__file__).resolve().parent


def make_dataset(samples: int = 2_000):
    rng = np.random.default_rng(42)
    amount = rng.lognormal(mean=6.0, sigma=1.1, size=samples)
    hour = rng.integers(0, 24, size=samples)
    velocity = rng.poisson(1.2, size=samples)
    device_events = rng.poisson(3.0, size=samples)
    fraud = ((amount > 1800) | (velocity >= 4) | (device_events >= 11) | ((hour < 5) & (amount > 900))).astype(int)
    noise = rng.random(samples) < 0.04
    fraud = np.where(noise, 1 - fraud, fraud)
    return np.column_stack((amount, hour, velocity, device_events)), fraud


if __name__ == "__main__":
    features, labels = make_dataset()
    model = RandomForestClassifier(n_estimators=150, random_state=42, class_weight="balanced")
    model.fit(features, labels)
    joblib.dump(model, ROOT / "model.joblib")
    print("Saved ml/model.joblib")
