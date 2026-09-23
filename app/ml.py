import os
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split


MODEL_PATH = "models/fraud_model.joblib"

FEATURES = [
    "amount_ratio",
    "amount_zscore",
    "velocity_10m",
    "new_device",
    "new_merchant",
    "geo_distance_km",
    "geo_velocity_kmh",
    "ip_mismatch",
    "failed_attempts",
    "off_hours",
    "card_not_present",
    "merchant_risk",
]


def train_model(df):
    """
    Train the fraud detection model and persist both
    the trained model and its evaluation metrics.
    """

    required_columns = FEATURES + ["is_fraud"]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Training dataset is missing required columns: "
            + ", ".join(missing_columns)
        )

    # -----------------------------
    # Prepare features and target
    # -----------------------------

    X = df[FEATURES].copy()
    y = df["is_fraud"].astype(int)

    # Replace invalid numeric values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)

    # -----------------------------
    # Train / test split
    # -----------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        stratify=y,
        random_state=42,
    )

    # -----------------------------
    # Random Forest
    # -----------------------------

    model = RandomForestClassifier(
        n_estimators=260,
        max_depth=9,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    # -----------------------------
    # Predictions
    # -----------------------------

    fraud_probability = model.predict_proba(X_test)[:, 1]

    predictions = (
        fraud_probability >= 0.5
    ).astype(int)

    # -----------------------------
    # Metrics
    # -----------------------------

    roc_auc = roc_auc_score(
        y_test,
        fraud_probability,
    )

    pr_auc = average_precision_score(
        y_test,
        fraud_probability,
    )

    confusion = confusion_matrix(
        y_test,
        predictions,
    )

    report = classification_report(
        y_test,
        predictions,
        output_dict=True,
        zero_division=0,
    )

    # -----------------------------
    # Dataset statistics
    # -----------------------------

    training_samples = len(X_train)
    test_samples = len(X_test)

    fraud_samples = int(y.sum())
    normal_samples = int((y == 0).sum())

    # -----------------------------
    # Persist metrics
    # -----------------------------

    metrics = {
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "confusion_matrix": confusion.tolist(),
        "report": report,
        "training_samples": training_samples,
        "test_samples": test_samples,
        "fraud_samples": fraud_samples,
        "normal_samples": normal_samples,
        "features": FEATURES,
    }

    # -----------------------------
    # Save model + metrics
    # -----------------------------

    model_directory = os.path.dirname(MODEL_PATH)

    if model_directory:
        os.makedirs(
            model_directory,
            exist_ok=True,
        )

    artifact = {
        "model": model,
        "metrics": metrics,
        "features": FEATURES,
    }

    joblib.dump(
        artifact,
        MODEL_PATH,
    )

    return model, metrics


def load_model():
    """
    Load the trained model.

    Supports:
    - New artifact format containing model + metrics
    - Old format containing only the model
    """

    if not os.path.exists(MODEL_PATH):
        return None

    artifact = joblib.load(MODEL_PATH)

    # New artifact format
    if isinstance(artifact, dict):
        if "model" in artifact:
            return artifact["model"]

    # Backward compatibility
    return artifact


def load_metrics():
    """
    Load persisted model metrics.

    Returns an empty dictionary if the existing
    model file does not contain metrics.
    """

    if not os.path.exists(MODEL_PATH):
        return {}

    artifact = joblib.load(MODEL_PATH)

    if isinstance(artifact, dict):
        metrics = artifact.get("metrics")

        if isinstance(metrics, dict):
            return metrics

    return {}