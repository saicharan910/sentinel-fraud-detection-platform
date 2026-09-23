import math
import os
import random
from collections import defaultdict, deque
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

from .ml import FEATURES, MODEL_PATH, load_model, load_metrics


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RULE_SCORE = 45.0
MAX_ML_SCORE = 55.0

MODEL = None
METRICS = {}

HISTORY = defaultdict(lambda: deque(maxlen=30))

KNOWN_DEVICES = defaultdict(set)
KNOWN_MERCHANTS = defaultdict(set)

# Simulated clock for each customer.
# This prevents real-time websocket speed from being interpreted
# as actual transaction time.
SIMULATED_TIME = {}


# ============================================================
# CUSTOMER PROFILES
# ============================================================

class Customer:
    def __init__(
        self,
        customer_id,
        home_city,
        home_country,
        avg_amount,
        amount_std,
    ):
        self.customer_id = customer_id
        self.home_city = home_city
        self.home_country = home_country
        self.avg_amount = avg_amount
        self.amount_std = amount_std


CUSTOMERS = [
    Customer("CUST1001", "Bengaluru", "India", 1800, 700),
    Customer("CUST1002", "Hyderabad", "India", 2400, 900),
    Customer("CUST1003", "Chennai", "India", 1300, 500),
    Customer("CUST1004", "Mumbai", "India", 3200, 1200),
    Customer("CUST1005", "Delhi", "India", 2100, 800),
    Customer("CUST1006", "Pune", "India", 1700, 600),
    Customer("CUST1007", "Kolkata", "India", 1500, 550),
    Customer("CUST1008", "Tirupati", "India", 1100, 450),
    Customer("CUST1009", "Kochi", "India", 1900, 700),
    Customer("CUST1010", "Ahmedabad", "India", 2800, 1000),
]


# ============================================================
# LOCATION DATA
# ============================================================

CITY = {
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Pune": (18.5204, 73.8567),
    "Kolkata": (22.5726, 88.3639),
    "Tirupati": (13.6288, 79.4192),
    "Kochi": (9.9312, 76.2673),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Goa": (15.4909, 73.8278),
}


# ============================================================
# MERCHANT RISK
# ============================================================

MERCHANT_RISK = {
    "Amazon": 0.05,
    "Flipkart": 0.08,
    "Myntra": 0.10,
    "Swiggy": 0.08,
    "Zomato": 0.08,
    "BookMyShow": 0.12,
    "Uber": 0.10,
    "Ola": 0.10,
    "Apple Store": 0.15,
    "Samsung": 0.15,
    "Unknown Marketplace": 0.65,
    "Crypto Exchange": 0.80,
    "Gift Card Store": 0.70,
    "High Risk Gaming": 0.75,
}


MERCHANT_CATEGORY = {
    "Amazon": "E_COMMERCE",
    "Flipkart": "E_COMMERCE",
    "Myntra": "E_COMMERCE",
    "Swiggy": "FOOD",
    "Zomato": "FOOD",
    "BookMyShow": "ENTERTAINMENT",
    "Uber": "TRANSPORT",
    "Ola": "TRANSPORT",
    "Apple Store": "ELECTRONICS",
    "Samsung": "ELECTRONICS",
    "Unknown Marketplace": "E_COMMERCE",
    "Crypto Exchange": "FINANCIAL",
    "Gift Card Store": "DIGITAL_GOODS",
    "High Risk Gaming": "GAMING",
}


MERCHANTS = list(MERCHANT_RISK.keys())


# ============================================================
# UTILITIES
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two geographic coordinates.
    Returns kilometers.
    """

    radius = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return radius * 2 * math.asin(
        math.sqrt(a)
    )


def get_city_distance(city_a, city_b):
    if city_a not in CITY or city_b not in CITY:
        return 0.0

    lat1, lon1 = CITY[city_a]
    lat2, lon2 = CITY[city_b]

    return haversine(
        lat1,
        lon1,
        lat2,
        lon2,
    )


def random_device():
    return f"DEV-{random.randint(10000, 99999)}"


def random_ip_country(home_country):
    """
    Mostly returns the customer's normal country,
    occasionally creates an IP-country mismatch.
    """

    if random.random() < 0.90:
        return home_country

    countries = [
        "United States",
        "United Kingdom",
        "Singapore",
        "UAE",
        "Germany",
        "India",
    ]

    foreign = [
        country
        for country in countries
        if country != home_country
    ]

    return random.choice(foreign)


def get_initial_time(customer):
    """
    Initialize each customer's simulated clock.
    """

    if customer.customer_id not in SIMULATED_TIME:
        base = datetime.utcnow() - timedelta(
            hours=random.randint(1, 72)
        )

        SIMULATED_TIME[
            customer.customer_id
        ] = base

    return SIMULATED_TIME[
        customer.customer_id
    ]



def advance_simulated_time(customer, fraud_pattern=None):
    current = get_initial_time(customer)

    if fraud_pattern == "geo_velocity":
        minutes = random.randint(10, 30)
    elif fraud_pattern in ("account_takeover", "velocity"):
        minutes = random.randint(1, 8)
    else:
        minutes = random.randint(15, 90)

    current += timedelta(minutes=minutes)
    SIMULATED_TIME[customer.customer_id] = current

    return current

# ============================================================
# HISTORY
# ============================================================

def get_customer_history(customer_id):
    return list(HISTORY[customer_id])


def customer_baseline(customer):
    """
    Estimate the customer's normal spending level using
    recent history blended with the customer's profile.
    """

    history = get_customer_history(
        customer.customer_id
    )

    amounts = [
        float(item["amount"])
        for item in history
        if item.get("amount") is not None
    ]

    if amounts:
        recent_median = float(
            np.median(amounts)
        )

        baseline = (
            recent_median * 0.70
            + customer.avg_amount * 0.30
        )

        return max(
            baseline,
            1.0,
        )

    return max(
        float(customer.avg_amount),
        1.0,
    )


def customer_amount_std(customer):
    history = get_customer_history(
        customer.customer_id
    )

    amounts = [
        float(item["amount"])
        for item in history
        if item.get("amount") is not None
    ]

    if len(amounts) >= 2:
        std = float(
            np.std(
                amounts,
                ddof=1,
            )
        )

        return max(
            std,
            float(customer.amount_std) * 0.35,
            1.0,
        )

    return max(
        float(customer.amount_std),
        1.0,
    )


# ============================================================
# MODEL
# ============================================================

def ensure_model():
    """
    Load the trained Random Forest model.
    """

    global MODEL
    global METRICS

    MODEL = load_model()
    METRICS = load_metrics()

    if MODEL is not None:
        return

    print(
        "Fraud model not found. "
        "The engine will use rule-based scoring "
        "until a trained model is available."
    )


# ============================================================
# TRANSACTION GENERATION
# ============================================================

def choose_fraud_pattern():
    """
    Probability distribution for synthetic fraud scenarios.
    """

    roll = random.random()

    if roll < 0.08:
        return "account_takeover"

    if roll < 0.14:
        return "spend_spike"

    if roll < 0.19:
        return "geo_velocity"

    if roll < 0.24:
        return "velocity"

    return None


def generate_transaction():
    """
    Generate one synthetic transaction.

    Important:
    synthetic_fraud is ground-truth simulation metadata.
    It is NEVER used directly by the scoring engine.
    """

    customer = random.choice(
        CUSTOMERS
    )

    fraud_pattern = choose_fraud_pattern()

    timestamp = advance_simulated_time(
        customer,
        fraud_pattern,
    )

    baseline = customer_baseline(
        customer
    )

    

    
    # Continue from the customer's most recently observed city.
    # A normal purchase should not imply instantaneous travel home.
    previous_history = get_customer_history(customer.customer_id)

    normal_city = (
        previous_history[-1]["city"]
        if previous_history
        else customer.home_city
    )

    city = normal_city

    merchant = random.choice(
        MERCHANTS[:10]
    )

    device = None

    failed_attempts = 0

    card_present = True

    ip_country = customer.home_country

    # --------------------------------------------------------
    # NORMAL TRANSACTION
    # --------------------------------------------------------

    if fraud_pattern is None:

        amount = max(
            50.0,
            random.gauss(
                baseline,
                max(
                    customer.amount_std,
                    baseline * 0.25,
                ),
            ),
        )

        device_pool = list(
            KNOWN_DEVICES[
                customer.customer_id
            ]
        )

        if device_pool and random.random() < 0.95:
            device = random.choice(
                device_pool
            )
        else:
            device = random_device()

        if random.random() < 0.08:
            card_present = False

    # --------------------------------------------------------
    # SPENDING SPIKE
    # --------------------------------------------------------

    elif fraud_pattern == "spend_spike":

        multiplier = random.uniform(
            4.0,
            10.0,
        )

        amount = baseline * multiplier

        device_pool = list(
            KNOWN_DEVICES[
                customer.customer_id
            ]
        )

        device = (
            random.choice(device_pool)
            if device_pool
            else random_device()
        )

        card_present = random.choice(
            [True, False]
        )

    # --------------------------------------------------------
    # ACCOUNT TAKEOVER
    # --------------------------------------------------------

    elif fraud_pattern == "account_takeover":

        amount = baseline * random.uniform(
            1.5,
            4.5,
        )

        device = random_device()

        city = random.choice(
            [
                city_name
                for city_name in CITY
                if city_name != normal_city
            ]
        )

        ip_country = random.choice(
            [
                "United States",
                "United Kingdom",
                "Singapore",
                "UAE",
                "Germany",
            ]
        )

        failed_attempts = random.randint(
            2,
            5,
        )

        card_present = False

    # --------------------------------------------------------
    # IMPOSSIBLE TRAVEL
    # --------------------------------------------------------

    elif fraud_pattern == "geo_velocity":

        amount = baseline * random.uniform(
            1.2,
            3.0,
        )

        device_pool = list(
            KNOWN_DEVICES[
                customer.customer_id
            ]
        )

        device = (
            random.choice(device_pool)
            if device_pool
            else random_device()
        )

        # Pick a geographically distant city.
        distant_cities = [
            city_name
            for city_name in CITY
            if (
                city_name != normal_city
                and get_city_distance(
                    normal_city,
                    city_name,
                ) >= 500
            )
        ]

        city = random.choice(
            distant_cities
        )

        card_present = random.choice(
            [True, False]
        )

    # --------------------------------------------------------
    # VELOCITY / CARD TESTING
    # --------------------------------------------------------

    elif fraud_pattern == "velocity":

        amount = random.uniform(
            100,
            max(
                1000,
                baseline * 0.8,
            ),
        )

        device_pool = list(
            KNOWN_DEVICES[
                customer.customer_id
            ]
        )

        device = (
            random.choice(device_pool)
            if device_pool
            else random_device()
        )

        failed_attempts = random.randint(
            2,
            5,
        )

        card_present = False

    # --------------------------------------------------------
    # MERCHANT / DEVICE REGISTRATION
    # --------------------------------------------------------

    if device is None:
        device = random_device()

    # Add devices and merchants to known history
    # only AFTER generating the current transaction.
    new_device = (
        device
        not in KNOWN_DEVICES[
            customer.customer_id
        ]
    )

    new_merchant = (
        merchant
        not in KNOWN_MERCHANTS[
            customer.customer_id
        ]
    )

    # Occasionally use a new merchant for fraud.
    if (
        fraud_pattern in (
            "account_takeover",
            "spend_spike",
            "velocity",
        )
        and random.random() < 0.55
    ):
        merchant = random.choice(
            [
                "Unknown Marketplace",
                "Crypto Exchange",
                "Gift Card Store",
                "High Risk Gaming",
            ]
        )

        new_merchant = True

    category = MERCHANT_CATEGORY.get(
        merchant,
        "OTHER",
    )

    # --------------------------------------------------------
    # TIME-BASED SIGNAL
    # --------------------------------------------------------

    off_hours = (
        timestamp.hour < 6
        or timestamp.hour >= 23
    )

    transaction_id = (
        f"TXN-{random.randint(10000000, 99999999)}"
    )

    transaction = {
        "transaction_id": transaction_id,
        "timestamp": timestamp,
        "customer": customer,
        "amount": round(
            float(amount),
            2,
        ),
        "merchant": merchant,
        "category": category,
        "city": city,
        "country": customer.home_country,
        "device": device,
        "ip_country": ip_country,
        "card_present": card_present,
        "failed_attempts": failed_attempts,
        "synthetic_fraud": (
            fraud_pattern is not None
        ),
        "fraud_pattern": fraud_pattern,
        "new_device": new_device,
        "new_merchant": new_merchant,
        "off_hours": off_hours,
    }

    # Update known entities AFTER feature generation.
    KNOWN_DEVICES[
        customer.customer_id
    ].add(device)

    KNOWN_MERCHANTS[
        customer.customer_id
    ].add(merchant)

    return transaction


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def extract_features(transaction):
    customer = transaction["customer"]

    history = get_customer_history(
        customer.customer_id
    )

    baseline = customer_baseline(
        customer
    )

    std = customer_amount_std(
        customer
    )

    amount = float(
        transaction["amount"]
    )

    amount_ratio = (
        amount / baseline
        if baseline > 0
        else 0.0
    )

    amount_zscore = (
        (amount - baseline) / std
        if std > 0
        else 0.0
    )

    # --------------------------------------------------------
    # VELOCITY
    # --------------------------------------------------------

    current_time = transaction[
        "timestamp"
    ]

    recent_count = 0

    for item in reversed(history):

        previous_time = item.get(
            "timestamp"
        )

        if previous_time is None:
            continue

        try:
            elapsed = (
                current_time
                - previous_time
            ).total_seconds()
        except Exception:
            continue

        if elapsed <= 600:
            recent_count += 1

        else:
            break

    velocity_10m = recent_count

    # --------------------------------------------------------
    # DEVICE / MERCHANT
    # --------------------------------------------------------

    new_device = int(
        transaction["new_device"]
    )

    new_merchant = int(
        transaction["new_merchant"]
    )

    # --------------------------------------------------------
    # GEOGRAPHIC VELOCITY
    # --------------------------------------------------------

    geo_distance_km = 0.0
    geo_velocity_kmh = 0.0

    if history:

        previous = history[-1]

        previous_city = previous.get(
            "city"
        )

        previous_time = previous.get(
            "timestamp"
        )

        if (
            previous_city in CITY
            and transaction["city"] in CITY
            and previous_time is not None
        ):

            geo_distance_km = get_city_distance(
                previous_city,
                transaction["city"],
            )

            elapsed_hours = (
                current_time
                - previous_time
            ).total_seconds() / 3600.0

            if elapsed_hours > 0:

                geo_velocity_kmh = (
                    geo_distance_km
                    / elapsed_hours
                )

    # --------------------------------------------------------
    # IP MISMATCH
    # --------------------------------------------------------

    ip_mismatch = int(
        transaction["ip_country"]
        != transaction["country"]
    )

    # --------------------------------------------------------
    # OTHER SIGNALS
    # --------------------------------------------------------

    failed_attempts = int(
        transaction["failed_attempts"]
    )

    off_hours = int(
        transaction["off_hours"]
    )

    card_not_present = int(
        not transaction["card_present"]
    )

    merchant_risk = float(
        MERCHANT_RISK.get(
            transaction["merchant"],
            0.20,
        )
    )

    features = {
        "amount_ratio": float(
            amount_ratio
        ),
        "amount_zscore": float(
            amount_zscore
        ),
        "velocity_10m": float(
            velocity_10m
        ),
        "new_device": float(
            new_device
        ),
        "new_merchant": float(
            new_merchant
        ),
        "geo_distance_km": float(
            geo_distance_km
        ),
        "geo_velocity_kmh": float(
            geo_velocity_kmh
        ),
        "ip_mismatch": float(
            ip_mismatch
        ),
        "failed_attempts": float(
            failed_attempts
        ),
        "off_hours": float(
            off_hours
        ),
        "card_not_present": float(
            card_not_present
        ),
        "merchant_risk": float(
            merchant_risk
        ),
    }

    return features


# ============================================================
# RULE ENGINE
# ============================================================

def calculate_rule_score(features):
    """
    Deterministic fraud rules.
    Maximum contribution = 45 points.
    """

    score = 0.0
    reasons = []

    amount_ratio = features[
        "amount_ratio"
    ]

    zscore = features[
        "amount_zscore"
    ]

    velocity = features[
        "velocity_10m"
    ]

    new_device = features[
        "new_device"
    ]

    new_merchant = features[
        "new_merchant"
    ]

    geo_distance = features[
        "geo_distance_km"
    ]

    geo_velocity = features[
        "geo_velocity_kmh"
    ]

    ip_mismatch = features[
        "ip_mismatch"
    ]

    failed_attempts = features[
        "failed_attempts"
    ]

    off_hours = features[
        "off_hours"
    ]

    card_not_present = features[
        "card_not_present"
    ]

    merchant_risk = features[
        "merchant_risk"
    ]

    # --------------------------------------------------------
    # SPENDING ANOMALY
    # --------------------------------------------------------

    if amount_ratio >= 5:
        score += 14
        reasons.append(
            f"amount {amount_ratio:.1f}x customer baseline"
        )

    elif amount_ratio >= 3:
        score += 10
        reasons.append(
            f"amount {amount_ratio:.1f}x customer baseline"
        )

    elif amount_ratio >= 2:
        score += 5
        reasons.append(
            f"amount {amount_ratio:.1f}x customer baseline"
        )

    if zscore >= 6:
        score += 10
        reasons.append(
            f"extreme spending z-score {zscore:.1f}"
        )

    elif zscore >= 4:
        score += 7
        reasons.append(
            f"high spending z-score {zscore:.1f}"
        )

    elif zscore >= 3:
        score += 4
        reasons.append(
            f"elevated spending z-score {zscore:.1f}"
        )

    # --------------------------------------------------------
    # VELOCITY
    # --------------------------------------------------------

    if velocity >= 8:
        score += 12
        reasons.append(
            "high transaction velocity"
        )

    elif velocity >= 5:
        score += 8
        reasons.append(
            "elevated transaction velocity"
        )

    elif velocity >= 3:
        score += 2
        reasons.append(
            "multiple recent transactions"
        )

    # --------------------------------------------------------
    # DEVICE / MERCHANT
    # --------------------------------------------------------

    if new_device:
        score += 5
        reasons.append(
            "new device"
        )

    if new_merchant:
        score += 2.5
        reasons.append(
            "new merchant"
        )

    # --------------------------------------------------------
    # GEOGRAPHIC ANOMALY
    # --------------------------------------------------------

    if (
        geo_distance >= 500
        and geo_velocity >= 900
    ):
        score += 15
        reasons.append(
            f"impossible travel "
            f"({geo_velocity:.0f} km/h)"
        )

    elif geo_distance >= 500:
        score += 5
        reasons.append(
            f"large geographic change "
            f"({geo_distance:.0f} km)"
        )

    # --------------------------------------------------------
    # IDENTITY / NETWORK
    # --------------------------------------------------------

    if ip_mismatch:
        score += 7
        reasons.append(
            "IP country mismatch"
        )

    # --------------------------------------------------------
    # FAILED AUTHENTICATION
    # --------------------------------------------------------

    if failed_attempts >= 4:
        score += 10
        reasons.append(
            f"{failed_attempts} failed attempts"
        )

    elif failed_attempts >= 2:
        score += 7
        reasons.append(
            f"{failed_attempts} failed attempts"
        )

    elif failed_attempts == 1:
        score += 2
        reasons.append(
            "failed authentication attempt"
        )

    # --------------------------------------------------------
    # OFF-HOURS
    # --------------------------------------------------------

    if off_hours:
        score += 4
        reasons.append(
            "off-hours transaction"
        )

    # --------------------------------------------------------
    # CARD NOT PRESENT
    # --------------------------------------------------------

    if card_not_present:
        score += 2
        reasons.append(
            "card-not-present transaction"
        )

    # --------------------------------------------------------
    # MERCHANT RISK
    # --------------------------------------------------------

    if merchant_risk >= 0.5:
        score += 7
        reasons.append(
            "high-risk merchant"
        )

    elif merchant_risk >= 0.2:
        score += 3
        reasons.append(
            "elevated merchant risk"
        )

    # --------------------------------------------------------
    # COMBINED ACCOUNT-TAKEOVER SIGNAL
    # --------------------------------------------------------

    if (
        new_device
        and ip_mismatch
        and failed_attempts >= 2
    ):
        score += 8
        reasons.append(
            "account takeover pattern"
        )

    # --------------------------------------------------------
    # STRONG SPENDING COMBINATION
    # --------------------------------------------------------

    if (
        amount_ratio >= 3
        and zscore >= 4
    ):
        score += 6
        reasons.append(
            "severe spending anomaly"
        )

    # --------------------------------------------------------
    # GEO + IDENTITY COMBINATION
    # --------------------------------------------------------

    if (
        geo_distance >= 500
        and (
            ip_mismatch
            or new_device
        )
    ):
        score += 6
        reasons.append(
            "geographic and identity anomaly"
        )

    # --------------------------------------------------------
    # VELOCITY + DEVICE / MERCHANT
    # --------------------------------------------------------

    if (
        velocity >= 5
        and (
            new_device
            or new_merchant
        )
    ):
        score += 5
        reasons.append(
            "velocity with new identity signal"
        )

    # --------------------------------------------------------
    # CARD TESTING
    # --------------------------------------------------------

    if (
        failed_attempts >= 2
        and card_not_present
    ):
        score += 5
        reasons.append(
            "possible card testing pattern"
        )

    return min(
        score,
        MAX_RULE_SCORE,
    ), reasons


# ============================================================
# MACHINE LEARNING SCORE
# ============================================================

def calculate_ml_probability(features):
    """
    Obtain fraud probability from the trained Random Forest.

    If no model is available, return 0.
    """

    if MODEL is None:
        return 0.0

    try:

        row = pd.DataFrame(
            [
                [
                    features.get(
                        feature,
                        0.0,
                    )
                    for feature in FEATURES
                ]
            ],
            columns=FEATURES,
        )

        row = row.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        row = row.fillna(0)

        probability = MODEL.predict_proba(
            row
        )[0][1]

        return float(
            np.clip(
                probability,
                0.0,
                1.0,
            )
        )

    except Exception as error:

        print(
            "ML scoring error:",
            error,
        )

        return 0.0


# ============================================================
# FINAL SCORING
# ============================================================

def score(transaction):
    """
    Combine deterministic fraud rules and ML probability.

    synthetic_fraud is NOT used here.
    """

    features = extract_features(transaction)
    rule_score, reasons = calculate_rule_score(features)
    model_probability = calculate_ml_probability(features)
    ml_score = model_probability * MAX_ML_SCORE
    risk_score = rule_score + ml_score

    # --------------------------------------------------------
    # STRONG SIGNAL SAFEGUARD
    # --------------------------------------------------------
    strong_signal_count = 0

    if features["amount_ratio"] >= 3:
        strong_signal_count += 1
    if features["amount_zscore"] >= 4:
        strong_signal_count += 1
    if features["velocity_10m"] >= 5:
        strong_signal_count += 1
    if features["new_device"]:
        strong_signal_count += 1
    if features["ip_mismatch"]:
        strong_signal_count += 1
    if features["failed_attempts"] >= 2:
        strong_signal_count += 1
    if features["geo_distance_km"] >= 500 and features["geo_velocity_kmh"] >= 900:
        strong_signal_count += 1
    if features["failed_attempts"] >= 2 and features["card_not_present"]:
        strong_signal_count += 1

    if strong_signal_count >= 4:
        risk_score = max(risk_score, 75.0)
    elif strong_signal_count >= 3:
        risk_score = max(risk_score, 60.0)
    elif strong_signal_count >= 2:
        risk_score = max(risk_score, 40.0)

    # --------------------------------------------------------
    # FINAL FRAUD SAFEGUARDS
    # --------------------------------------------------------

    if features["failed_attempts"] >= 2 and features["card_not_present"]:
        risk_score = max(risk_score, 60.0)
        if "strong card-testing signal" not in reasons:
            reasons.append("strong card-testing signal")

    if features["new_device"] and features["ip_mismatch"]:
        risk_score = max(risk_score, 65.0)
        if "identity and device mismatch" not in reasons:
            reasons.append("identity and device mismatch")

    if (
        features["geo_distance_km"] >= 500
        and features["geo_velocity_kmh"] >= 900
        and (features["new_device"] or features["ip_mismatch"])
    ):
        risk_score = max(risk_score, 85.0)
        if "high-confidence impossible travel" not in reasons:
            reasons.append("high-confidence impossible travel")

    if features["amount_ratio"] >= 3 and features["amount_zscore"] >= 3:
        risk_score = max(risk_score, 60.0)
        if "high-confidence spending anomaly" not in reasons:
            reasons.append("high-confidence spending anomaly")

    # Moderate spending + new device + card-not-present is suspicious,
    # but does not automatically escalate to HIGH risk.
    if (
        features["amount_ratio"] >= 2
        and features["amount_zscore"] >= 2.5
        and features["new_device"]
        and features["card_not_present"]
    ):
        risk_score = max(risk_score, 40.0)
        if "combined spending and identity anomaly" not in reasons:
            reasons.append("combined spending and identity anomaly")

    # --------------------------------------------------------
    # MULTIPLE INDEPENDENT FRAUD SIGNALS
    # --------------------------------------------------------
    fraud_signal_count = sum([
        features["amount_ratio"] >= 3,
        features["amount_zscore"] >= 4,
        features["velocity_10m"] >= 5,
        features["new_device"] == 1,
        features["ip_mismatch"] == 1,
        features["failed_attempts"] >= 2,
        (
            features["geo_distance_km"] >= 500
            and features["geo_velocity_kmh"] >= 900
        ),
        (
            features["failed_attempts"] >= 2
            and features["card_not_present"] == 1
        ),
    ])

    if fraud_signal_count >= 3:
        risk_score = max(risk_score, 60.0)
        if "multiple independent fraud signals" not in reasons:
            reasons.append("multiple independent fraud signals")

    # Severe spending anomaly.
    if features["amount_ratio"] >= 5 and features["amount_zscore"] >= 6:
        risk_score = max(risk_score, 60.0)
        if "severe spending anomaly" not in reasons:
            reasons.append("severe spending anomaly")

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------
    risk_score = float(np.clip(risk_score, 0.0, 100.0))

    # --------------------------------------------------------
    # RISK LEVEL
    # --------------------------------------------------------
    if risk_score >= 85:
        risk_level = "CRITICAL"
    elif risk_score >= 60:
        risk_level = "HIGH"
    elif risk_score >= 35:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # --------------------------------------------------------
    # DECISION
    # --------------------------------------------------------
    if risk_score >= 85:
        decision = "BLOCK"
    elif risk_score >= 60:
        decision = "REVIEW"
    else:
        decision = "ALLOW"

    # --------------------------------------------------------
    # STORE HISTORY
    # --------------------------------------------------------
    HISTORY[transaction["customer"].customer_id].append(
        {
            "timestamp": transaction["timestamp"],
            "amount": transaction["amount"],
            "city": transaction["city"],
            "merchant": transaction["merchant"],
            "device": transaction["device"],
        }
    )

    return {
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "decision": decision,
        "reasons": reasons,
        "features": features,
        "model_probability": round(model_probability, 4),
    }
