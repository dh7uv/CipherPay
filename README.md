# CipherPay 🔐

**A secure transaction-monitoring and fraud-detection platform built with FastAPI, MongoDB, Redis, and machine learning.**

CipherPay is an educational fintech project that demonstrates transaction risk scoring, fraud alerts, encrypted sensitive data, transaction integrity verification, and analyst workflows through a responsive dashboard.

> **Disclaimer:** CipherPay is a demonstration project using synthetic data. It does not process real payments and is not intended for production financial decisions.

## ✨ Features

- **Authentication and access control** — Password hashing, expiring JWTs, and role-based authorization for users and analysts.
- **Fraud detection** — Rule-based transaction risk scoring with explanatory risk signals and optional Random Forest model support.
- **Transaction monitoring** — Searchable transaction history, risk scores, and analyst review workflows.
- **Security and privacy** — AES-256-GCM encryption for sensitive device and location fields, plus HMAC-SHA-256 transaction integrity verification.
- **Real-time activity tracking** — Redis-backed velocity tracking and rate limiting, with a process-local fallback.
- **Persistent storage** — MongoDB collections and indexes when the database is available at startup.
- **Audit logging** — Records sensitive authentication, transaction, and integrity-related actions.
- **Interactive dashboard** — Responsive user and analyst views, alert management, filtering, and service health information.

## 🧰 Tech Stack

| Area | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Database | MongoDB |
| Activity tracking | Redis-compatible service |
| Machine learning | scikit-learn, Random Forest |
| Security | Argon2, JWT, AES-GCM, HMAC-SHA-256 |
| Testing | pytest |

## 🏗️ Architecture

```text
User / Analyst
      |
      v
Web Dashboard
(HTML, CSS, JavaScript)
      |
      v
FastAPI Backend
      |
      +------ Authentication & Authorization
      +------ Transaction Management
      +------ Fraud Risk Scoring
      +------ Encryption & Integrity Checks
      +------ Alerts & Audit Logging
      |
      +------ MongoDB: Persistent Records
      +------ Redis: Activity & Rate Limits
      +------ scikit-learn: Optional ML Model
```

## 📁 Project Structure

```text
CipherPay/
├── backend/
│   ├── routes/
│   ├── services/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   └── dependencies.py
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── app.js
│   ├── login.js
│   └── styles.css
├── ml/
│   ├── synthetic_data.py
│   ├── train_model.py
│   └── evaluate_model.py
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── run.py
└── README.md
```

## ⚙️ Getting Started

### Prerequisites

- Python 3.10 or newer
- MongoDB (optional for an in-memory demonstration)
- Redis or a compatible service (optional)

### 1. Clone the repository

```bash
git clone https://github.com/dh7uv/CipherPay.git
cd CipherPay
```

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

Replace placeholder secrets with independent, randomly generated keys before using the application beyond a local demonstration. Keep `.env` private and never commit real secrets.

### 5. Start the backend

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open the application:

- **Dashboard / login:** http://127.0.0.1:8000/login
- **API documentation:** http://127.0.0.1:8000/docs
- **Health check:** http://127.0.0.1:8000/api/v1/health

Start MongoDB and Redis before launching the API if you want to use those services. Check the health endpoint to confirm which services connected successfully.

### Demo credentials

If demo seeding is explicitly enabled in your local configuration, use the demo account configured by the project. Do not use demonstration credentials in a deployed environment.

## 🤖 Machine Learning

CipherPay supports an optional Random Forest model alongside its rule-based fraud scoring engine.

Train the model:

```bash
python -m ml.train_model
```

Evaluate it:

```bash
python -m ml.evaluate_model
```

The evaluation scripts report classification metrics such as precision, recall, F1 score, confusion matrix, and average precision. Because the project uses synthetic data, these results should not be interpreted as evidence of performance on real transactions.

## 🧪 Testing

Run the test suite from the repository root:

```bash
python -m pytest -q
```

Tests cover authentication and authorization, transaction flows, encryption and integrity checks, fraud scoring, database adapter behavior, and model-related risk scoring.

## 🔒 Security Notes

- Never commit `.env`, real credentials, signing keys, or encryption keys.
- Use synthetic data only; do not upload real payment or personal information.
- Keep the development server bound to localhost during local demonstrations.
- Configure unique secrets and disable demo data before any deployment.
- Review authentication, encryption, storage, and deployment settings before considering any production use.

## 🚀 Future Improvements

- Add automated CI testing and code-quality checks.
- Improve fraud-model evaluation with carefully designed validation datasets.
- Add more monitoring and explainability for analyst decisions.
- Expand integration and security testing.

## 👨‍💻 Author

**Dhruv Marfatia**

GitHub: [@dh7uv](https://github.com/dh7uv)

---

*CipherPay is an educational software project exploring secure transaction monitoring and fraud detection.*