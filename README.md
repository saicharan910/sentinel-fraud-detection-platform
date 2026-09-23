# Sentinel — Real-Time Fraud Detection & Risk Monitoring Platform

A portfolio-grade fraud decisioning system built around **behavioural feature engineering, supervised ML, explainable risk signals, real-time streaming, and an operations dashboard**.

> **Important:** the transactions and fraud labels are synthetic. The engineering architecture is real; it does not claim to use a bank's private fraud data.

## What makes this different from a simple anomaly demo

Each transaction is evaluated against a customer profile and recent behavioural history. The system creates features such as:

- spend ratio and customer-specific amount z-score
- transaction velocity in a 10-minute window
- new device / new merchant indicators
- geographic distance and implied travel speed
- IP-country mismatch
- failed authentication attempts
- off-hours behaviour
- card-present vs card-not-present
- merchant risk profile

A Random Forest classifier produces a fraud probability. A small rule layer adds explicit operational signals and the system maps the combined result to an action: **ALLOW, REVIEW, or BLOCK**. The UI shows the reasons behind elevated decisions instead of simply saying that a price increased.

## Architecture

```text
Transaction Event
      |
      v
Feature Engineering  ---> customer history / merchant profile / geo context
      |
      +----> Random Forest probability
      |
      +----> Explainable rules / risk signals
      |
      v
Risk Score (0-100)
      |
      +---- ALLOW
      +---- REVIEW
      +---- BLOCK
      |
      v
SQLite event store + WebSocket stream
      |
      v
Fraud Operations Console
```

## Run on Windows / Python 3.14

```powershell
cd sentinel_fraud_platform
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

The first startup trains a model on generated labelled behaviour and saves it under `models/fraud_model.joblib`.

## API

- `GET /api/transactions?limit=100`
- `GET /api/transactions?risk_level=CRITICAL`
- `GET /api/stats`
- `GET /api/model`
- `GET /api/customers`
- `WS /ws/feed`

## Resume positioning

**Real-Time Fraud Detection & Risk Monitoring Platform | Python, FastAPI, Scikit-learn, SQLAlchemy, WebSockets, Pandas, NumPy**

- Engineered a real-time fraud decisioning pipeline that converts transaction, behavioural, device, merchant, and geo-velocity signals into explainable 0–100 risk scores and ALLOW/REVIEW/BLOCK decisions.
- Built a labelled synthetic fraud-data pipeline and Random Forest model with customer-specific behavioural features including spend deviation, velocity, new-device/merchant detection, IP mismatch, failed attempts, and impossible-travel signals.
- Deployed a FastAPI/WebSocket operations console with persistent transaction history, live risk trends, alert queues, model metrics, and decision explanations.

## Honest limitation

This is a **synthetic portfolio system**, not a production bank fraud model. A production deployment would require institution-specific labelled data, feature-store infrastructure, model governance, threshold calibration, drift monitoring, authentication/authorization, observability, and a production database such as PostgreSQL.
