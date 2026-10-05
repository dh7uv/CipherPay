"""Evaluate the synthetic demonstration model with fraud-appropriate metrics."""
from pathlib import Path

import joblib
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_curve, precision_score, recall_score, auc

from train_model import make_dataset

MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"


if __name__ == "__main__":
    if not MODEL_PATH.exists():
        raise SystemExit("Run python ml/train_model.py first")
    features, labels = make_dataset(800)
    model = joblib.load(MODEL_PATH)
    probabilities = model.predict_proba(features)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    print("Precision:", round(precision_score(labels, predictions), 3))
    print("Recall:", round(recall_score(labels, predictions), 3))
    print("F1:", round(f1_score(labels, predictions), 3))
    print("Confusion matrix:\n", confusion_matrix(labels, predictions))
    print("PR AUC:", round(auc(recall, precision), 3))
