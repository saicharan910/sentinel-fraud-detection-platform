import random
from dataclasses import dataclass

CITIES = [
    ("Bengaluru","India",12.9716,77.5946),("Mumbai","India",19.0760,72.8777),
    ("Delhi","India",28.6139,77.2090),("Hyderabad","India",17.3850,78.4867),
    ("Chennai","India",13.0827,80.2707),("Pune","India",18.5204,73.8567),
    ("Singapore","Singapore",1.3521,103.8198),("Dubai","UAE",25.2048,55.2708),
    ("London","UK",51.5074,-0.1278),("New York","USA",40.7128,-74.0060),
    ("Toronto","Canada",43.6532,-79.3832),("Frankfurt","Germany",50.1109,8.6821),
]
MERCHANTS = [
    ("Flipkart","E-Commerce",0.20),("Amazon","E-Commerce",0.18),("Myntra","E-Commerce",0.16),
    ("Reliance Digital","Electronics",0.13),("Apple Store","Electronics",0.08),
    ("Uber","Transport",0.06),("IndianOil","Fuel",0.04),("Swiggy","Food",0.03),
    ("BookMyShow","Entertainment",0.03),("Marriott","Travel",0.02),
    ("CryptoX","Financial Services",0.015),("Luxury Jewels","Luxury Goods",0.005),
]

@dataclass
class Customer:
    customer_id: str
    home_city: str
    home_country: str
    home_lat: float
    home_lon: float
    avg_amount: float
    amount_std: float
    normal_categories: tuple
    device_id: str
    usual_hour_start: int
    usual_hour_end: int


def build_customers(n=100, seed=42):
    rng = random.Random(seed)
    customers=[]
    for i in range(n):
        city,country,lat,lon=rng.choice(CITIES[:6])
        avg=rng.uniform(600,6500)
        cats=tuple(rng.sample([m[1] for m in MERCHANTS], k=rng.randint(2,4)))
        customers.append(Customer(
            f"CUST{10000+i}",city,country,lat,lon,avg,avg*rng.uniform(.25,.55),cats,
            f"DEV-{100000+i}",rng.randint(7,10),rng.randint(18,23)))
    return customers
