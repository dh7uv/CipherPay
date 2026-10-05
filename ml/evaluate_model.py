from __future__ import annotations

import argparse
from pathlib import Path

import joblib
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from .synthetic_data import generate_synthetic_dataset
from .train_model import MODEL_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CipherPay's model on a reproducible synthetic holdout.")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Trained joblib model path.")
    args = parser.parse_args()

    if not args.model.is_file():
        parser.error(f"Model not found at {args.model}. Train it first with python -m ml.train_model.")

    features, labels = generate_synthetic_dataset()
    _, x_test, _, y_test = train_test_split(
        features,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )
    model = joblib.load(args.model)["model"]
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]

    print(f"Precision: {precision_score(y_test, predictions, zero_division=0):.4f}")
    print(f"Recall: {recall_score(y_test, predictions, zero_division=0):.4f}")
    print(f"F1-score: {f1_score(y_test, predictions, zero_division=0):.4f}")
    print(f"Precision-recall AUC (average precision): {average_precision_score(y_test, probabilities):.4f}")
    print("Confusion matrix (rows=true, columns=predicted; order=[legitimate, fraud]):")
    print(confusion_matrix(y_test, predictions, labels=[0, 1]))
    print("Evaluation uses synthetic data only; these metrics are not estimates of real-world fraud performance.")


if __name__ == "__main__":
    main()
