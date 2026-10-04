# CipherPayCryptaGuard — Project Specification & Comprehensive READMENotice to Codex / AI Developer: This document serves as the complete, definitive blueprint and prompt specification for building CryptaGuard. Implement all modules, APIs, security mechanisms, database models, and frontend interfaces exactly as specified here, ensuring a fully functional, production-grade mini-project.1. Project Overview & ObjectivesCryptaGuard is a full-stack, secure financial transaction monitoring and fraud detection web application. It simulates real-time transaction processing, risk scoring, and anomaly detection while enforcing rigorous enterprise-grade security practices (Argon2id hashing, AES-256-GCM encryption, HMAC-SHA-256 integrity verification, and audit logging).Target Audience: College mini-project for a 3-person team with a 7-day development window.Core Philosophy: Prioritize a fully working, well-integrated application with a professional interface, meaningful security features, and demonstrable NoSQL functionality without unnecessary enterprise-level complexity.Data Disclaimer: Uses strictly synthetic or appropriately anonymized data. This is a simulation system, not a real payment processor.2. Architecture & System DesignHigh-Level Architecture (Mermaid Diagram)Code snippetgraph TD
    subgraph Client [Frontend Layer]
        UI[HTML5 / CSS3 / Vanilla JS Dashboard]
    end

    subgraph API [FastAPI Backend]
        AuthRoute[Auth Routes]
        TxRoute[Transaction Routes]
        AlertRoute[Alert Routes]
        AnalyticsRoute[Analytics Routes]
        SecurityRoute[Security / Audit Routes]
    end

    subgraph Services [Business Logic & Security Services]
        FraudEngine[Fraud Engine: Rules + ML Model]
        RedisSvc[Redis Service: Velocity & Rate Limiting]
        CryptoSvc[Crypto Service: AES-256-GCM & HMAC-SHA-256]
        AuditSvc[Audit Logging Service]
    end

    subgraph Datastores [Data Persistence Layer]
        MongoDB[(MongoDB Primary DB)]
        Redis[(Redis In-Memory DB)]
    end

    UI -->|HTTPS / JSON REST API| API
    API --> AuthRoute
    API --> TxRoute
    API --> AlertRoute
    API --> AnalyticsRoute
    API --> SecurityRoute

    TxRoute --> FraudEngine
    TxRoute --> RedisSvc
    TxRoute --> CryptoSvc
    TxRoute --> AuditSvc

    FraudEngine --> RedisSvc
    CryptoSvc --> MongoDB
    FraudEngine --> MongoDB
    RedisSvc --> Redis
    AnalyticsRoute --> MongoDB
3. Technology StackFrontend: HTML5, CSS3, Vanilla JavaScript (Single Page Architecture with dynamic view toggling or multi-page setup under /frontend).Backend: Python 3.10+, FastAPI, Uvicorn.Primary Database: MongoDB (Motor async driver or PyMongo).In-Memory Cache & State: Redis (redis-py).Machine Learning: scikit-learn, joblib (Random Forest classifier / Isolation Forest anomaly detector with robust rule-based fallback).Cryptography: cryptography library (for Fernet/AES-GCM and HMAC-SHA-256), argon2-cffi for password hashing.Testing: pytest, httpx (FastAPI TestClient).API Documentation: Swagger UI (/docs) & ReDoc (/redoc).4. MongoDB Collection Design & IndexesCollections & Schemas1. users_id: ObjectId (Primary Key)email: String (Unique, Indexed)password_hash: String (Argon2id hash)role: String (user or analyst)status: String (active or suspended)created_at: ISODate2. transactionstransaction_id: String (Unique, Indexed)user_id: String (Indexed)amount: Floatcurrency: String (e.g., "USD", "EUR")merchant: Stringdevice_id: String (Encrypted or Plain as per design)location: String (Encrypted or Plain)status: String (Approved, Under Review, Declined)risk_score: Integer (0–100)risk_category: String (Low, Medium, High)risk_reasons: Array of Stringsencrypted_fields: Object / String (AES-256-GCM ciphertext container for sensitive fields)integrity_hmac: String (HMAC-SHA-256 signature)created_at: ISODate (Indexed)3. fraud_alertsalert_id: String (Unique)transaction_id: String (Indexed)severity: String (Low, Medium, High, Critical)reason: Stringstatus: String (Open, Under Investigation, Resolved, Dismissed)created_at: ISODate (Indexed)updated_at: ISODate4. audit_logslog_id: Stringactor_id: String (User ID or system)action: String (e.g., USER_LOGIN, TRANSACTION_SUBMITTED, ALERT_UPDATED, INTEGRITY_CHECK_FAILED)resource_id: String (Optional target ID)timestamp: ISODate (Indexed)outcome: String (SUCCESS or FAILURE)Required Database Indexestransactions:{ user_id: 1, created_at: -1 }{ status: 1, created_at: -1 }{ risk_score: -1 }{ transaction_id: 1 } (Unique)fraud_alerts:{ status: 1, created_at: -1 }audit_logs:{ actor_id: 1, timestamp: -1 }users:{ email: 1 } (Unique)5. Redis Data Structures & TTL StrategySliding Window Velocity Tracking:Key format: velocity:user:{user_id}Data Structure: Sorted Set (ZSET) where member = transaction_id and score = timestamp (epoch seconds).Strategy: On each transaction, remove entries older than the window (e.g., past 60 minutes) using ZREMRANGEBYSCORE, count remaining items using ZCARD, then add the new transaction using ZADD. Set a TTL of 3600 seconds on the key.Device Activity Tracking:Key format: device:activity:{device_id}Data Structure: Sorted Set or String counter with TTL (e.g., 24-hour TTL) to catch device rotation/velocity abuse.API Rate Limiting:Key format: ratelimit:{user_id}:{endpoint}Data Structure: String counter with 60-second TTL.6. Fraud Detection Methodology & Model EvaluationHybrid Approach:Rule-Based Engine: Evaluates velocity (from Redis counts), large transaction thresholds, repeated rapid attempts, and blacklisted/suspicious device flags. Adds specific explanatory risk reasons.Machine Learning Model: Scikit-learn RandomForestClassifier (or Isolation Forest for anomaly detection). Accepts normalized transaction features (amount, hour of day, frequency score, geo-distance anomaly).Fallback Mechanism: If the model file (ml/model.joblib) is missing or fails to load, the system gracefully falls back 100% to the rule-based engine and appends a notice in the risk reasons.Evaluation Metrics: Evaluated using Precision, Recall, F1-Score, Confusion Matrix, and Precision-Recall AUC (avoiding accuracy alone due to severe class imbalance in fraud datasets). Documented in ml/README.md.7. Cryptography & Security SpecificationsPassword Hashing: Argon2id via argon2-cffi. Never store plaintext or use weak hashing like MD5/SHA256.AES-256-GCM Encryption:Used for sensitive fields (e.g., precise location, internal device metadata, or simulated card info if applicable).Generate a unique 12-byte nonce per encryption operation.Store ciphertext, nonce, and tag securely in MongoDB.Keys loaded via environment variables (ENCRYPTION_KEY), never hardcoded.HMAC-SHA-256 Integrity Verification:Compute a cryptographic HMAC over a canonicalized string representation of core transaction fields (transaction_id, user_id, amount, currency, timestamp).Store integrity_hmac in MongoDB.Provide an endpoint POST /transactions/{transaction_id}/verify-integrity that recomputes the HMAC and performs a constant-time comparison (hmac.compare_digest).Explicitly demonstrate tampering detection (modifying database records directly causes verification failure).Audit Logging: Every sensitive action, auth attempt, transaction creation, and integrity check failure is immutably recorded to the audit_logs collection.8. API Endpoints SpecificationMethodEndpointDescriptionAccess ControlPOST/auth/registerRegister a new userPublicPOST/auth/loginAuthenticate and return access tokenPublicGET/healthSystem health check (Mongo & Redis status)PublicPOST/transactionsSubmit and score a transactionAuthenticated (user / analyst)GET/transactionsList transactions with pagination & filtersAuthenticated (user / analyst)GET/transactions/{id}Retrieve transaction detailsAuthenticatedPOST/transactions/{id}/verify-integrityVerify HMAC integrityAuthenticated (analyst)GET/alertsRetrieve fraud alertsAnalystPATCH/alerts/{alert_id}Update alert review statusAnalystGET/analytics/summaryDashboard aggregations & statisticsAuthenticated (analyst)9. Project Directory StructurePlaintextcryptaguard/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── transactions.py
│   │   ├── alerts.py
│   │   └── analytics.py
│   ├── services/
│   │   ├── fraud_engine.py
│   │   ├── redis_service.py
│   │   ├── crypto_service.py
│   │   ├── auth_service.py
│   │   └── audit_service.py
│   └── schemas/
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── style.css
│   └── app.js
├── ml/
│   ├── train_model.py
│   ├── evaluate_model.py
│   └── README.md
├── tests/
│   ├── test_auth.py
│   ├── test_transactions.py
│   ├── test_crypto.py
│   └── test_fraud.py
├── data/
│   └── README.md
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
10. Environment Variables (.env.example)Code snippet# Application Settings
APP_NAME=CryptaGuard
DEBUG=True
API_V1_STR=/api/v1

# Database Configuration
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=cryptaguard_db

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Security & Cryptography
SECRET_KEY=super-secret-jwt-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENCRYPTION_KEY=32-byte-base64-encoded-aes-key-here
HMAC_SECRET_KEY=super-secret-hmac-key-here
11. Setup & Installation Instructions (Windows / Linux / macOS)Clone the Repository & Navigate to Workspace:Bashcd cryptaguard
Set Up Python Virtual Environment:Bashpython -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
Configure Environment Variables:Bashcp .env.example .env
# Edit .env with your local MongoDB and Redis connection strings and generated keys.
Start MongoDB and Redis services locally (via Docker or native service manager).Run the Backend Server:Bashuvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
Access Interactive API Docs:Swagger UI: http://localhost:8000/docsFrontend Dashboard: Open frontend/index.html via a local static server or FastAPI static mount.Run Automated Tests:Bashpytest tests/ -v
End of CryptaGuard Specification. Codex: Proceed with full implementation of all modules adhering strictly to these requirements.
