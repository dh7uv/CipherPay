# CryptaGuard

CryptaGuard is a full-stack, synthetic financial-transaction monitoring application. It demonstrates transaction risk scoring, fraud alerts, audit trails, MongoDB persistence, Redis-backed velocity controls, Argon2id password hashing, AES-256-GCM encryption, and HMAC-SHA-256 integrity checks. It is a simulation only—not a payment processor.

## Run locally

Use Python 3.10 or later. MongoDB and Redis are optional for the demo: when unavailable, the application uses its in-memory local mode while retaining the same API.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000/dashboard](http://localhost:8000/dashboard). The seeded demo analyst account is `demo@cipherpay.local` / `demo123`; replace it before any non-demo use. Interactive API documentation is available at `/docs` and `/redoc`.

## API

| Method | Endpoint | Access |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Public |
| POST | `/api/v1/auth/login` | Public |
| POST | `/api/v1/auth/guest` | Public; read-only JWT session |
| GET | `/api/v1/health` | Public |
| POST | `/api/v1/transactions` | Authenticated |
| GET | `/api/v1/transactions` | Authenticated |
| GET | `/api/v1/transactions/{id}` | Owner or analyst |
| GET | `/api/v1/transactions/{id}/details` | Analyst; decrypted inspector metadata |
| POST | `/api/v1/transactions/{id}/verify-integrity` | Analyst |
| GET | `/api/v1/alerts` | Analyst |
| PATCH | `/api/v1/alerts/{id}` | Analyst |
| GET | `/api/v1/analytics/summary` | Analyst |
| GET | `/api/v1/security/audit-logs` | Analyst |

The dashboard includes separate Overview, Transactions, Fraud Alerts, Analytics & ML, Security & Integrity, and Audit Trail views. Analysts can filter the transaction ledger, inspect protected records, run synthetic simulations, and verify HMAC signatures from the browser.

Submit bearer tokens in `Authorization: Bearer <token>`. List transactions accepts `status`, `risk_category`, `page`, and `page_size` filters.

## Security model

- Passwords are hashed with Argon2id; plaintext passwords are never persisted.
- Device and location values are AES-256-GCM encrypted with a fresh 12-byte nonce for every transaction.
- The HMAC protects a canonical transaction identity, owner, amount, currency, and timestamp payload. A database modification is detected by the verification endpoint.
- Sensitive actions produce audit records; the API does not provide audit-log mutation endpoints.
- Redis uses `velocity:user:{user_id}`, `device:activity:{device_id}`, and `ratelimit:{user_id}:{endpoint}` keys with the specified TTL windows.

Generate production secrets before deployment:

```bash
openssl rand -base64 32  # ENCRYPTION_KEY
openssl rand -hex 48     # SECRET_KEY and HMAC_SECRET_KEY
```

## Fraud model

The rule engine covers high amounts, high-risk merchants, unusual currencies, user velocity, and device activity. A Random Forest model can be trained on synthetic data:

```bash
python ml/train_model.py
python ml/evaluate_model.py
```

If `ml/model.joblib` is absent or fails to load, CryptaGuard uses its rule engine and identifies that fallback in the risk reasons.

## Verification

```bash
pytest -q
```

The test suite covers health, authenticated transaction submission, authorization boundaries, encryption nonce uniqueness, integrity verification/tamper detection, and the ML fallback.
