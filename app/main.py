import asyncio
import json
import os

from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
    Query,
)

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import func

from .database import (
    init_db,
    get_session,
    Transaction,
)

from . import engine

from .engine import (
    generate_transaction,
    score,
    ensure_model,
    CUSTOMERS,
)


# ============================================================
# PATHS
# ============================================================

BASE = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================

class Manager:

    def __init__(self):
        self.connections = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)

    async def broadcast(self, payload):
        dead_connections = []

        for websocket in list(self.connections):

            try:
                await websocket.send_text(
                    json.dumps(
                        payload,
                        default=str,
                    )
                )

            except Exception:
                dead_connections.append(websocket)

        for websocket in dead_connections:
            self.connections.discard(websocket)


manager = Manager()


# ============================================================
# REAL-TIME TRANSACTION STREAM
# ============================================================

async def stream_loop():

    while True:

        try:

            # ------------------------------------------------
            # Generate transaction
            # ------------------------------------------------

            raw = generate_transaction()

            # ------------------------------------------------
            # Calculate risk
            # ------------------------------------------------

            result = score(raw)

            # ------------------------------------------------
            # Database session
            # ------------------------------------------------

            session = get_session()

            try:

                transaction = Transaction(

                    transaction_id=(
                        raw["transaction_id"]
                    ),

                    timestamp=(
                        raw["timestamp"]
                    ),

                    customer_id=(
                        raw["customer"].customer_id
                    ),

                    amount=(
                        raw["amount"]
                    ),

                    merchant=(
                        raw["merchant"]
                    ),

                    merchant_category=(
                        raw["category"]
                    ),

                    city=(
                        raw["city"]
                    ),

                    country=(
                        raw["country"]
                    ),

                    device_id=(
                        raw["device"]
                    ),

                    ip_country=(
                        raw["ip_country"]
                    ),

                    card_present=(
                        raw["card_present"]
                    ),

                    failed_attempts=(
                        raw["failed_attempts"]
                    ),

                    is_fraud=(
                        raw["synthetic_fraud"]
                    ),

                    risk_score=(
                        result["risk_score"]
                    ),

                    risk_level=(
                        result["risk_level"]
                    ),

                    decision=(
                        result["decision"]
                    ),

                    reasons="|".join(
                        result["reasons"]
                    ),

                    features_json=json.dumps(
                        result["features"]
                    ),

                    model_probability=(
                        result["model_probability"]
                    ),
                )

                session.add(transaction)

                session.commit()

                session.refresh(transaction)

                data = transaction.to_dict()

            finally:

                session.close()

            # ------------------------------------------------
            # Broadcast to connected dashboards
            # ------------------------------------------------

            await manager.broadcast(
                {
                    "type": "transaction",
                    "data": data,
                }
            )

        except Exception as error:

            print(
                f"[STREAM ERROR] {error}"
            )

            await manager.broadcast(
                {
                    "type": "error",
                    "data": {
                        "message": str(error),
                    },
                }
            )

        # ----------------------------------------------------
        # Stream interval
        # ----------------------------------------------------

        await asyncio.sleep(1.3)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # --------------------------------------------------------
    # Initialize database
    # --------------------------------------------------------

    init_db()

    # --------------------------------------------------------
    # Load/train ML model
    # --------------------------------------------------------

    ensure_model()

    # --------------------------------------------------------
    # Start real-time stream
    # --------------------------------------------------------

    stream_task = asyncio.create_task(
        stream_loop()
    )

    try:

        yield

    finally:

        stream_task.cancel()

        try:

            await stream_task

        except asyncio.CancelledError:

            pass


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Sentinel Fraud Detection Platform",

    description=(
        "Real-time fraud detection and "
        "risk monitoring platform."
    ),

    version="1.0.0",

    lifespan=lifespan,
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=os.path.join(
            BASE,
            "static",
        )
    ),
    name="static",
)


# ============================================================
# TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory=os.path.join(
        BASE,
        "templates",
    )
)


# ============================================================
# HOME
# ============================================================

@app.get("/")
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


# ============================================================
# TRANSACTIONS API
# ============================================================

@app.get(
    "/api/transactions"
)
async def transactions(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),

    risk_level: str | None = None,
):

    session = get_session()

    try:

        query = (
            session
            .query(Transaction)
            .order_by(
                Transaction.timestamp.desc()
            )
        )

        # ----------------------------------------------------
        # Optional risk-level filter
        # ----------------------------------------------------

        if risk_level:

            query = query.filter(
                Transaction.risk_level
                == risk_level.upper()
            )

        rows = (
            query
            .limit(limit)
            .all()
        )

        return {
            "transactions": [
                row.to_dict()
                for row in rows
            ]
        }

    finally:

        session.close()


# ============================================================
# STATS API
# ============================================================

@app.get(
    "/api/stats"
)
async def stats():

    session = get_session()

    try:

        # ----------------------------------------------------
        # Total transactions
        # ----------------------------------------------------

        total = (
            session
            .query(
                func.count(
                    Transaction.id
                )
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # Total transaction volume
        # ----------------------------------------------------

        volume = (
            session
            .query(
                func.sum(
                    Transaction.amount
                )
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # Average risk
        # ----------------------------------------------------

        avg_risk = (
            session
            .query(
                func.avg(
                    Transaction.risk_score
                )
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # Critical transactions
        # ----------------------------------------------------

        critical = (
            session
            .query(
                func.count(
                    Transaction.id
                )
            )
            .filter(
                Transaction.risk_level
                == "CRITICAL"
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # High-risk transactions
        # ----------------------------------------------------

        high_risk = (
            session
            .query(
                func.count(
                    Transaction.id
                )
            )
            .filter(
                Transaction.risk_level
                == "HIGH"
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # Review transactions
        # ----------------------------------------------------

        review = (
            session
            .query(
                func.count(
                    Transaction.id
                )
            )
            .filter(
                Transaction.decision
                == "REVIEW"
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # Blocked transactions
        # ----------------------------------------------------

        blocked = (
            session
            .query(
                func.count(
                    Transaction.id
                )
            )
            .filter(
                Transaction.decision
                == "BLOCK"
            )
            .scalar()
            or 0
        )

        # ----------------------------------------------------
        # Normalize numeric values
        # ----------------------------------------------------

        total = int(total)

        volume = round(
            float(volume),
            2,
        )

        avg_risk = round(
            float(avg_risk),
            2,
        )

        critical = int(critical)

        high_risk = int(high_risk)

        review = int(review)

        blocked = int(blocked)

        # ----------------------------------------------------
        # Return both old and new API field names.
        #
        # This keeps compatibility with previous frontend
        # versions while supporting the new dashboard.
        # ----------------------------------------------------

        return {

            # New dashboard names
            "total_transactions": total,

            "total_volume": volume,

            "average_risk_score": avg_risk,

            "high_risk_count": high_risk,

            "critical_risk_count": critical,

            # Existing/legacy names
            "total": total,

            "volume": volume,

            "avg_risk": avg_risk,

            "critical": critical,

            "review": review,

            "blocked": blocked,

            # ML model metrics
            "model_metrics": (
                engine.METRICS
            ),
        }

    finally:

        session.close()


# ============================================================
# MODEL INFORMATION API
# ============================================================

@app.get(
    "/api/model"
)
async def model_info():

    return {

        "features": (
            engine.FEATURES
        ),

        "metrics": (
            engine.METRICS
        ),
    }


# ============================================================
# CUSTOMERS API
# ============================================================

@app.get(
    "/api/customers"
)
async def customers():

    return {

        "customers": [

            {
                "customer_id": (
                    customer.customer_id
                ),

                "home_city": (
                    customer.home_city
                ),

                "home_country": (
                    customer.home_country
                ),

                "avg_amount": round(
                    customer.avg_amount,
                    2,
                ),
            }

            for customer in CUSTOMERS
        ]
    }


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket(
    "/ws/feed"
)
async def ws_feed(
    websocket: WebSocket,
):

    await manager.connect(
        websocket
    )

    try:

        while True:

            # Keep the connection alive.
            # The server pushes transactions through
            # manager.broadcast().

            await websocket.receive_text()

    except WebSocketDisconnect:

        await manager.disconnect(
            websocket
        )

    except Exception:

        await manager.disconnect(
            websocket
        )