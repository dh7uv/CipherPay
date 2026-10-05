# Fraud model

CipherPay optionally loads `ml/model.joblib` at API startup. Train it locally with:

```powershell
python -m ml.train_model
```

The training script generates a fixed-seed synthetic dataset with normalized amount, hour, user transaction frequency, and device activity features. Training and API inference use the same feature normalization helper. Its Random Forest is saved as a local artifact ignored by Git. The API checks the artifact's feature schema and falls back to explanatory rule-based scoring when no compatible model is available.

Evaluate the reproducible synthetic holdout with:

```powershell
python -m ml.evaluate_model
```

The report includes precision, recall, F1-score, the confusion matrix, and average precision (the area under the precision-recall curve). Accuracy is intentionally not the primary metric for this imbalanced synthetic dataset. The synthetic records and reported metrics are for software demonstration only; they are not representative of real payment fraud and must not be used to make live financial decisions. `joblib` artifacts use Python pickle serialization, so only load model files generated and controlled by this project.
