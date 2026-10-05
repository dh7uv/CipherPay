from __future__ import annotations

import argparse
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from backend.services.fraud_features import FEATURE_NAMES
from .synthetic_data import generate_synthetic_dataset

MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"


def train_model(samples: int, output_path: Path) -> tuple[int, int]:
    features, labels = generate_synthetic_dataset(samples=samples)
    x_train, _, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )
    model = RandomForestClassifier(
        n_estimators=240,
        min_samples_leaf=3,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_names": list(FEATURE_NAMES)}, output_path)
    return len(y_test), int(y_test.sum())


def main() -> None:
    parser = argparse.ArgumentParser(description="Train CipherPay on reproducible synthetic fraud data.")
    parser.add_argument("--samples", type=int, default=6000, help="Number of synthetic transactions.")
    parser.add_argument("--output", type=Path, default=MODEL_PATH, help="Where to save the trained model.")
    args = parser.parse_args()

    holdout_size, fraud_count = train_model(args.samples, args.output)
    print(f"Saved model to {args.output}")
    print(f"Synthetic holdout labels: {holdout_size} rows, {fraud_count} fraud")
    print("This generated dataset is for software demonstration and is not representative of real payment fraud.")


if __name__ == "__main__":
    main()
