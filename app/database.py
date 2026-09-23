from datetime import datetime
import json

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = "sqlite:///./sentinel.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)

    transaction_id = Column(
        String(40),
        unique=True,
        index=True,
        nullable=False,
    )

    timestamp = Column(
        DateTime,
        index=True,
        nullable=False,
    )

    customer_id = Column(
        String(20),
        index=True,
        nullable=False,
    )

    amount = Column(Float, nullable=False)
    merchant = Column(String(100), nullable=False)
    merchant_category = Column(String(50), nullable=False)
    city = Column(String(60), nullable=False)
    country = Column(String(60), nullable=False)
    device_id = Column(String(40), nullable=False)
    ip_country = Column(String(60), nullable=False)
    card_present = Column(Boolean, nullable=False)
    failed_attempts = Column(Integer, nullable=False)

    is_fraud = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    risk_score = Column(
        Float,
        nullable=False,
    )

    risk_level = Column(
        String(20),
        nullable=False,
    )

    decision = Column(
        String(20),
        nullable=False,
    )

    reasons = Column(
        Text,
        nullable=False,
        default="",
    )

    features_json = Column(
        Text,
        nullable=False,
        default="{}",
    )

    model_probability = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    __table_args__ = (
        Index(
            "ix_tx_customer_time",
            "customer_id",
            "timestamp",
        ),
    )

    def to_dict(self):
        """
        Convert a SQLAlchemy Transaction into a JSON-safe dictionary.
        """

        # Safely decode stored feature JSON.
        try:
            features = json.loads(self.features_json or "{}")

            if not isinstance(features, dict):
                features = {}

        except (json.JSONDecodeError, TypeError):
            features = {}

        # Safely split fraud/risk reasons.
        reasons = (
            self.reasons.split("|")
            if self.reasons
            else []
        )

        # Safely serialize timestamp.
        timestamp = self.timestamp

        if isinstance(timestamp, datetime):
            timestamp_value = timestamp.isoformat()

            # Keep the API's existing UTC-style representation.
            if not timestamp_value.endswith("Z"):
                timestamp_value += "Z"
        else:
            timestamp_value = str(timestamp)

        return {
            "id": int(self.id),
            "transaction_id": str(self.transaction_id),
            "timestamp": timestamp_value,

            "customer_id": str(self.customer_id),

            "amount": round(float(self.amount), 2),

            "merchant": str(self.merchant),
            "merchant_category": str(self.merchant_category),

            "city": str(self.city),
            "country": str(self.country),

            "device_id": str(self.device_id),
            "ip_country": str(self.ip_country),

            "card_present": bool(self.card_present),
            "failed_attempts": int(self.failed_attempts),

            "is_fraud": bool(self.is_fraud),

            "risk_score": round(float(self.risk_score), 2),
            "risk_level": str(self.risk_level),
            "decision": str(self.decision),

            "reasons": reasons,
            "features": features,

            "model_probability": round(
                float(self.model_probability),
                4,
            ),
        }


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()