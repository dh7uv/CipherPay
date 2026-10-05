# Fraud model

`train_model.py` creates a small reproducible Random Forest model using synthetic data only and writes `model.joblib` to this directory.  The live service uses it opportunistically; if it is absent or cannot load, the rule engine remains fully functional and records that fallback in the transaction risk reasons.

Evaluate the model after training with:

```bash
python ml/evaluate_model.py
```

The evaluator reports precision, recall, F1, confusion matrix, and precision-recall AUC. Accuracy is intentionally not the primary metric because fraud classes are imbalanced.
