# CipherPay

CipherPay is a synthetic transaction-monitoring and fraud-detection project. It combines a FastAPI service, a responsive analyst dashboard, MongoDB persistence, Redis-backed activity tracking, and a rule-based fraud engine with an optional scikit-learn model.

> **Demo only.** CipherPay does not process payments. Use synthetic data, keep local secrets private, and do not rely on the demo fraud model for real payment decisions.

## Features

- Analyst and user sign-in with Argon2 password hashes and expiring JWTs.
- Role-checked APIs: users can only access their own transactions; analysts can review the transaction network, alerts, audit records, and integrity checks.
- Transaction risk scoring with explanatory rules, sliding-window user/device activity, request rate limiting, and an optional Random Forest model.
- AES-256-GCM encryption of device and location fields, with a fresh nonce and authentication tag per value.
- HMAC-SHA-256 transaction integrity verification.
- MongoDB persistence and indexes when MongoDB is reachable at startup. If it is unavailable during startup, the demo explicitly runs with in-memory storage instead; in-memory changes do not survive a restart.
- Redis-backed velocity and rate-limit tracking when Redis is reachable, with a logged in-memory fallback for local demonstrations.
- Responsive dashboard, searchable and filterable transaction history, live service status, alert review workflows, and user/analyst-specific views.

## Requirements

- Python 3.10 or newer
- MongoDB (optional for an ephemeral in-memory demo; recommended for persistence)
- Redis (optional; in-memory risk-tracking fallback is provided)

## Run locally on Windows

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Before using the app beyond a local demo, replace the placeholder signing/encryption keys in `.env`. Generate independent keys with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
python -c "import secrets; print(secrets.token_hex(32))"
```

Use these values for `SECRET_KEY`, `ENCRYPTION_KEY`, and `HMAC_SECRET_KEY`, respectively. The AES key must be base64 that decodes to exactly 32 bytes. Do not commit `.env`.

Set `MONGO_URI`, `MONGO_DB_NAME`, `REDIS_HOST`, `REDIS_PORT`, `SEED_DEMO_DATA`, and (if needed) `REDIS_PASSWORD` in `.env`. Set `FRAUD_BLACKLISTED_DEVICE_IDS` to a comma-separated list of synthetic device identifiers to flag. Start MongoDB/Redis before the API if you want their persistent/shared features. MongoDB availability is checked at app startup.

Start the API and dashboard:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/login>. With the example configuration (`SEED_DEMO_DATA=true`), the local analyst account is `demo@cipherpay.local` with password `demo123`. Demo data is opt-in and disabled by default; set `SEED_DEMO_DATA=false` and replace local secrets before deploying or exposing the service to a network.

API documentation is available at <http://127.0.0.1:8000/docs>; the health endpoint is <http://127.0.0.1:8000/api/v1/health>.

## Train and evaluate the optional fraud model

The application uses its rule-based engine when no compatible model artifact is present. To train a demonstration Random Forest using a reproducible, normalized synthetic dataset:

```powershell
python -m ml.train_model
python -m ml.evaluate_model
```

Training writes `ml/model.joblib`, which is ignored by Git. Restart the API after training to load the model. Evaluation reports precision, recall, F1, a confusion matrix, and average precision (area under the precision-recall curve). Synthetic metrics are not evidence of real-world model performance.

## Run tests

```powershell
python -m pytest -q
```

The tests cover authentication/authorization, database adapter behavior, encryption and HMAC integrity, transaction flows, rule-based risk scoring, and model-driven risk elevation.

## API overview

All API routes use the `/api/v1` prefix.

| Method | Route | Access |
| --- | --- | --- |
| `POST` | `/auth/register` | Public; creates a standard user |
| `POST` | `/auth/login` | Public |
| `GET` | `/health` | Public |
| `POST` | `/transactions/submit` | Authenticated; users submit for themselves |
| `GET` | `/transactions/` | Authenticated; user-scoped or analyst-wide, with pagination and filters |
| `GET` | `/transactions/{transaction_id}` | Authenticated; owner or analyst |
| `POST` | `/transactions/{transaction_id}/verify-integrity` | Analyst; records a verified integrity status when valid |
| `POST` | `/transactions/{transaction_id}/decision` | Analyst; approve/decline a verified High-risk (score ≥70) transaction under review |
| `GET` | `/analytics/dashboard` | Analyst |
| `GET` | `/alerts/` | Analyst |
| `PATCH` | `/alerts/{alert_id}` | Analyst; set status to `Open`, `Under Investigation`, `Resolved`, or `Dismissed` |
| `PATCH` | `/alerts/{alert_id}/resolve` | Analyst; compatibility endpoint |
| `GET` | `/security/audit-logs` | Analyst |
| `GET` | `/security/integrity-check/{transaction_id}` | Analyst; compatibility endpoint |

Send protected requests with `Authorization: Bearer <access-token>`. Alert state changes and sensitive authentication, transaction, and integrity actions are recorded in the audit log.

## Persistence and indexes

When MongoDB is available at startup, CipherPay creates indexes for unique user emails and transaction/alert/audit IDs; transaction owner/date, status/date, and risk score; alert status/date; and audit actor/timestamp. Collections are loaded into the application store on startup and mutations are persisted as they occur. If the database is unavailable, health reports that local storage is in use; restarting in that mode discards changes.

Redis uses sorted sets for per-user transaction velocity (one-hour window) and device activity (24-hour window). Login, registration, and transaction submission limits use expiring counters. Device identifiers and login emails are hashed before they are used in Redis keys. When Redis is unavailable, equivalent process-local tracking is used and is not shared between workers.

## Repository layout

```text
backend/
  main.py
  config.py
  database.py
  dependencies.py
  routes/                 API endpoints
  services/               Authentication, audit, crypto, fraud, and Redis logic
frontend/
  index.html
  login.html
  app.js
  login.js
  styles.css
ml/
  synthetic_data.py
  train_model.py
  evaluate_model.py
tests/
```
