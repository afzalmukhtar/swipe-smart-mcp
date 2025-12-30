import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- PATH FIXER ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from sqlmodel import Session, select

from src import (
    BucketScope,
    CapBucket,
    CapType,
    CreditCard,
    Expense,
    PeriodType,
    RedemptionPartner,
    RewardRule,
    create_db_and_tables,
    engine,
)

# --- CONFIGURATION ---
NUM_TRANSACTIONS = 100  # 🚀 Change this to generate more/less data!
DAYS_HISTORY = 60  # How far back to go

# --- DATASETS ---

PLATFORMS = [
    "Direct",
    "SmartBuy",
    "Amazon Pay",
    "CRED",
    "Google Pay",
    "PayTM",
    "PhonePe",
    "Swiggy App",
    "Zomato App",
    "Flipkart App",
]

MERCHANTS_BY_CATEGORY = {
    "Dining": [
        "Starbucks",
        "Truffles",
        "Dominos",
        "Swiggy Instamart",
        "Social",
        "Chili's",
        "Burger King",
    ],
    "Groceries": ["BigBasket", "Zepto", "Blinkit", "Reliance Fresh", "Nature's Basket"],
    "Travel - Flights": [
        "Indigo",
        "Air India",
        "MakeMyTrip",
        "Cleartrip",
        "EaseMyTrip",
        "Akasa Air",
    ],
    "Travel - Hotels": [
        "Marriott",
        "Taj Hotels",
        "OYO Rooms",
        "Airbnb",
        "Hyatt",
        "Booking.com",
    ],
    "Travel - Cabs & Rideshare": ["Uber", "Ola", "Rapido", "BluSmart"],
    "Fuel": ["HP Petrol Pump", "Indian Oil", "Shell", "Bharat Petroleum"],
    "Utilities": ["BESCOM", "Tata Power", "Mahanagar Gas", "Water Board"],
    "Shopping - Online": [
        "Amazon India",
        "Flipkart",
        "Myntra",
        "Tata Cliq",
        "Nykaa",
        "Ajio",
    ],
    "Shopping - Retail": [
        "Zara",
        "H&M",
        "Croma",
        "Reliance Digital",
        "IKEA",
        "Decathlon",
    ],
    "Entertainment": ["PVR Cinemas", "BookMyShow", "Netflix", "Spotify", "Wonderla"],
    "Telecom & Internet": ["Jio", "Airtel", "Vi", "ACT Fibernet"],
    "Insurance": ["HDFC Life", "LIC", "Acko", "PolicyBazaar"],
    "Rent": ["NoBroker", "CRED Rent Pay", "RedGirraffe"],
    "Wallet & Prepaid Loads": ["Paytm Wallet", "Amazon Pay Balance"],
    "Government Services": ["Income Tax", "Passport Seva", "Traffic Challan"],
}


# --- CARD DEFINITIONS ---
def get_card_definitions():
    """
    Returns a comprehensive list of credit card setups with realistic reward rules.

    Each card includes:
    - Multiple cap buckets for different reward categories
    - Varied multipliers (base + bonus) simulating real-world earn rates
    - min_spend thresholds where applicable
    - Realistic redemption partners with varying transfer ratios
    """
    return [
        # ==========================================
        # CARD 1: HDFC Regalia Gold (Premium Travel Card)
        # ==========================================
        {
            "card": CreditCard(
                name="HDFC Regalia Gold",
                bank="HDFC",
                network="Mastercard World",
                monthly_limit=500000.0,
                billing_cycle_start=15,
                rewards_currency="Reward Points",
                base_point_value=0.30,  # Good for flights via SmartBuy
            ),
            "buckets": [
                CapBucket(
                    name="SmartBuy Monthly Cap",
                    max_points=4000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
                CapBucket(
                    name="Dining Bonus Cap",
                    max_points=2000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
                CapBucket(
                    name="Global Earnings Cap",
                    max_points=50000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                    bucket_scope=BucketScope.GLOBAL,
                ),
            ],
            "rules": [
                # SmartBuy (10x points, capped)
                {
                    "category": "Travel - Flights",
                    "base": 2.0,
                    "bonus": 8.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Hotels",
                    "base": 2.0,
                    "bonus": 8.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Online",
                    "base": 2.0,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                # Dining (4x, separate cap)
                {
                    "category": "Dining",
                    "base": 2.0,
                    "bonus": 2.0,
                    "bucket_idx": 1,
                    "min_spend": 0,
                },
                # Base categories (2x)
                {
                    "category": "Groceries",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Entertainment",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Base Rule (Generic)
                {
                    "category": "Base",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions (0x or 1x)
                {
                    "category": "Fuel",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Base Rule
                {
                    "category": "Base",
                    "base": 1.0,  # Assumed base earning if not specified
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Utilities",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [
                {"name": "Singapore Airlines KrisFlyer", "ratio": 2.0, "value": 1.20},
                {"name": "Marriott Bonvoy", "ratio": 5.0, "value": 0.70},
                {"name": "InterMiles", "ratio": 1.0, "value": 0.50},
                {"name": "Accor Live Limitless", "ratio": 2.0, "value": 0.80},
            ],
        },
        # ==========================================
        # CARD 2: SBI Cashback (Online Shopping King)
        # ==========================================
        {
            "card": CreditCard(
                name="SBI Cashback",
                bank="SBI",
                network="Visa Signature",
                monthly_limit=200000.0,
                billing_cycle_start=1,
                rewards_currency="Cashback",
                base_point_value=1.00,  # 1 CB = 1 INR
            ),
            "buckets": [
                CapBucket(
                    name="Online Cashback Cap",
                    max_points=5000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                # 5% Online (capped at 5000/month)
                {
                    "category": "Shopping - Online",
                    "base": 5.0,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Flights",
                    "base": 5.0,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Entertainment",
                    "base": 5.0,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                # Specific Online Merchants (5%)
                {
                    "category": "Uber",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Swiggy",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Amazon",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Ola",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Zomato",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Blinkit",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Zepto",
                    "base": 0.05,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                # Base Rate (1%)
                {
                    "category": "Base",
                    "base": 0.01,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 1% Offline
                {
                    "category": "Shopping - Retail",
                    "base": 0.01,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Dining",
                    "base": 0.01,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Groceries",
                    "base": 0.01,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions
                {
                    "category": "Fuel",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Insurance",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [],  # Cashback card - no transfer partners
        },
        # ==========================================
        # CARD 3: Axis Ace (Bill Payments & Dining)
        # ==========================================
        {
            "card": CreditCard(
                name="Axis Ace",
                bank="Axis",
                network="Visa Signature",
                monthly_limit=150000.0,
                billing_cycle_start=10,
                rewards_currency="Cashback",
                base_point_value=1.00,
            ),
            "buckets": [
                CapBucket(
                    name="5% Category Cap",
                    max_points=500.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
                CapBucket(
                    name="Dining Cap",
                    max_points=400.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                # 5% on Utilities via GPay (capped)
                {
                    "category": "Utilities",
                    "base": 2.0,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Telecom & Internet",
                    "base": 2.0,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                # 4% Dining apps (separate cap)
                {
                    "category": "Dining",
                    "base": 2.0,
                    "bonus": 2.0,
                    "bucket_idx": 1,
                    "min_spend": 0,
                },
                # 2% Base
                {
                    "category": "Shopping - Online",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Flights",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Groceries",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 1% or Less
                {
                    "category": "Fuel",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Cabs & Rideshare",
                    "base": 1.5,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [],
        },
        # ==========================================
        # CARD 4: Amex Platinum Charge (Ultra Premium)
        # ==========================================
        {
            "card": CreditCard(
                name="Amex Platinum Charge",
                bank="American Express",
                network="Amex",
                monthly_limit=1000000.0,
                billing_cycle_start=5,
                rewards_currency="Membership Rewards",
                base_point_value=0.50,  # High value for travel redemptions
            ),
            "buckets": [],  # Amex Plat typically has no caps
            "rules": [
                # 5x on Travel
                {
                    "category": "Travel - Flights",
                    "base": 1.0,
                    "bonus": 4.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Hotels",
                    "base": 1.0,
                    "bonus": 4.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 3x on Dining & Entertainment
                {
                    "category": "Dining",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Entertainment",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 2x on Shopping
                {
                    "category": "Shopping - Online",
                    "base": 1.0,
                    "bonus": 1.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 1.0,
                    "bonus": 1.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 1x Base
                {
                    "category": "Groceries",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Utilities",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Cabs & Rideshare",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Fuel",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Insurance",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Government Services",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [
                {"name": "British Airways Avios", "ratio": 1.0, "value": 1.50},
                {"name": "Hilton Honors", "ratio": 2.0, "value": 0.50},
                {"name": "Air France KLM Flying Blue", "ratio": 1.0, "value": 1.20},
                {"name": "Delta SkyMiles", "ratio": 1.0, "value": 1.10},
                {"name": "Emirates Skywards", "ratio": 1.0, "value": 1.00},
            ],
        },
        # ==========================================
        # CARD 5: ICICI Amazon Pay (E-commerce Focused)
        # ==========================================
        # ==========================================
        # CARD 5a: ICICI Amazon Pay (Prime Member)
        # ==========================================
        {
            "card": CreditCard(
                name="ICICI Amazon Pay (Prime)",
                bank="ICICI",
                network="Visa Signature",
                monthly_limit=300000.0,
                billing_cycle_start=20,
                rewards_currency="Amazon Pay Balance",
                base_point_value=1.00,
                # NEW: Tag this card as belonging to a Prime member
                meta_data={"is_prime": True},
            ),
            "buckets": [
                CapBucket(
                    name="Amazon Prime Cap",
                    max_points=2500.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                # 5% on Amazon (Condition: is_prime == True)
                {
                    "category": "Shopping - Online",
                    "base": 2.0,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                    "condition": "is_prime == True",
                },
                # 2% on Bill Payments
                {
                    "category": "Utilities",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Telecom & Internet",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                # 1% elsewhere
                {
                    "category": "Dining",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Travel - Flights",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Groceries",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Entertainment",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                # Exclusions
                {
                    "category": "Fuel",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
            ],
            "partners": [],
        },
        # ==========================================
        # CARD 5b: ICICI Amazon Pay (Non-Prime Member)
        # ==========================================
        {
            "card": CreditCard(
                name="ICICI Amazon Pay (Non-Prime)",
                bank="ICICI",
                network="Visa Signature",
                monthly_limit=150000.0,
                billing_cycle_start=20,
                rewards_currency="Amazon Pay Balance",
                base_point_value=1.00,
                # NEW: Tag this card as belonging to a Non-Prime member
                meta_data={"is_prime": False},
            ),
            "buckets": [],  # Usually, 3% is uncapped or high cap for non-prime
            "rules": [
                # 3% on Amazon (Condition: is_prime == False)
                {
                    "category": "Shopping - Online",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": "is_prime == False",
                },
                # 2% on Bill Payments
                {
                    "category": "Utilities",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Telecom & Internet",
                    "base": 2.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                # 1% elsewhere
                {
                    "category": "Dining",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Travel - Flights",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Groceries",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Entertainment",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                # Exclusions
                {
                    "category": "Fuel",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                    "condition": None,
                },
            ],
            "partners": [],
        },
        # ==========================================
        # CARD 6: HDFC Infinia (Super Premium Points Card)
        # ==========================================
        {
            "card": CreditCard(
                name="HDFC Infinia",
                bank="HDFC",
                network="Visa Infinite",
                monthly_limit=2000000.0,
                billing_cycle_start=8,
                rewards_currency="Reward Points",
                base_point_value=0.50,  # Highest value for SmartBuy flights
            ),
            "buckets": [
                CapBucket(
                    name="SmartBuy Monthly",
                    max_points=10000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                # 10% SmartBuy (33 pts per 150 = 10% cap at 10k)
                {
                    "category": "Travel - Flights",
                    "base": 3.3,
                    "bonus": 7.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Hotels",
                    "base": 3.3,
                    "bonus": 7.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                # 5% Base on all eligible
                {
                    "category": "Dining",
                    "base": 3.3,
                    "bonus": 1.7,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Online",
                    "base": 3.3,
                    "bonus": 1.7,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 3.3,
                    "bonus": 1.7,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Groceries",
                    "base": 3.3,
                    "bonus": 1.7,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Entertainment",
                    "base": 3.3,
                    "bonus": 1.7,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Cabs & Rideshare",
                    "base": 3.3,
                    "bonus": 1.7,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Lower categories
                {
                    "category": "Utilities",
                    "base": 3.3,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Fuel",
                    "base": 3.3,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Insurance",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [
                {"name": "Singapore Airlines KrisFlyer", "ratio": 1.0, "value": 1.50},
                {"name": "Marriott Bonvoy", "ratio": 2.5, "value": 0.80},
                {"name": "InterMiles", "ratio": 0.5, "value": 1.00},
                {"name": "Club Vistara", "ratio": 1.0, "value": 1.20},
                {"name": "British Airways Avios", "ratio": 1.0, "value": 1.30},
            ],
        },
        # ==========================================
        # CARD 7: AU Small Finance Bank LIT (Customizable)
        # ==========================================
        {
            "card": CreditCard(
                name="AU LIT Credit Card",
                bank="AU Small Finance",
                network="Rupay",
                monthly_limit=100000.0,
                billing_cycle_start=12,
                rewards_currency="Cashback",
                base_point_value=1.00,
            ),
            "buckets": [
                CapBucket(
                    name="Selected Category Cap",
                    max_points=750.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                # User-selected 3 categories at 3.5% (assuming common choices)
                {
                    "category": "Dining",
                    "base": 0.5,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Groceries",
                    "base": 0.5,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Entertainment",
                    "base": 0.5,
                    "bonus": 3.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                # 0.5% on everything else
                {
                    "category": "Shopping - Online",
                    "base": 0.5,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 0.5,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Flights",
                    "base": 0.5,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Utilities",
                    "base": 0.5,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Fuel",
                    "base": 0.5,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [],
        },
        # ==========================================
        # CARD 8: IDFC First Select (Fuel Surcharge Waiver King)
        # ==========================================
        {
            "card": CreditCard(
                name="IDFC First Select",
                bank="IDFC First",
                network="Visa Signature",
                monthly_limit=250000.0,
                billing_cycle_start=3,
                rewards_currency="Reward Points",
                base_point_value=0.25,
            ),
            "buckets": [
                CapBucket(
                    name="10x Category Cap",
                    max_points=3000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
                CapBucket(
                    name="Fuel Cap",
                    max_points=1000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                # 10x on selected categories (usually travel)
                {
                    "category": "Travel - Flights",
                    "base": 1.0,
                    "bonus": 9.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Hotels",
                    "base": 1.0,
                    "bonus": 9.0,
                    "bucket_idx": 0,
                    "min_spend": 0,
                },
                {
                    "category": "Travel - Cabs & Rideshare",
                    "base": 1.0,
                    "bonus": 4.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 6x on Fuel (unlimited surcharge waiver)
                {
                    "category": "Fuel",
                    "base": 1.0,
                    "bonus": 5.0,
                    "bucket_idx": 1,
                    "min_spend": 0,
                },
                # 3x on others
                {
                    "category": "Dining",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Online",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Groceries",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Entertainment",
                    "base": 1.0,
                    "bonus": 2.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # 1x on utilities
                {
                    "category": "Utilities",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Telecom & Internet",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                # Exclusions
                {
                    "category": "Rent",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Wallet & Prepaid Loads",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Insurance",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
                {
                    "category": "Government Services",
                    "base": 0.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                    "min_spend": 0,
                },
            ],
            "partners": [
                {"name": "Club Vistara", "ratio": 3.0, "value": 0.50},
                {"name": "InterMiles", "ratio": 2.0, "value": 0.40},
            ],
        },
    ]


# --- MAIN SEED FUNCTION ---
def seed():
    print(f"🌱 Seeding Database with {NUM_TRANSACTIONS} randomized transactions...")
    create_db_and_tables()

    with Session(engine) as session:
        # Clear existing data to avoid duplicates/mess (Optional)
        # Uncomment these lines if you want a fresh start every time
        # session.exec(delete(Expense))
        # session.exec(delete(RewardRule))
        # session.exec(delete(CapBucket))
        # session.exec(delete(CreditCard))
        # session.commit()

        if session.exec(select(CreditCard)).first():
            print(
                "⚠️  Database already has cards. Skipping Card creation (will add Transactions only)."
            )
        else:
            # 1. Create Cards & Rules
            definitions = get_card_definitions()
            for defi in definitions:
                card = defi["card"]
                session.add(card)
                session.commit()
                session.refresh(card)

                # Add Buckets
                bucket_objs = []
                for b in defi["buckets"]:
                    b.card_id = card.id
                    session.add(b)
                    bucket_objs.append(b)
                session.commit()
                for b in bucket_objs:
                    session.refresh(b)

                # Add Rules
                for r in defi["rules"]:
                    bucket_id = (
                        bucket_objs[r["bucket_idx"]].id
                        if r["bucket_idx"] is not None
                        else None
                    )
                    rule = RewardRule(
                        card_id=card.id,
                        category=r["category"],
                        base_multiplier=r["base"],
                        bonus_multiplier=r["bonus"],
                        cap_bucket_id=bucket_id,
                        min_spend=r.get("min_spend", 0.0),
                        condition_expression=r.get("condition"),
                    )
                    session.add(rule)

                # Add Redemption Partners (if any)
                partners = defi.get("partners", [])
                if partners:
                    for p in partners:
                        partner = RedemptionPartner(
                            card_id=card.id,
                            partner_name=p["name"],
                            transfer_ratio=p["ratio"],
                            estimated_value=p["value"],
                        )
                        session.add(partner)
                else:
                    # Fallback for cashback cards - no partners needed
                    pass

                session.commit()
            print("✅ Cards, Rules & Limits Created.")

        # 2. Generate Random Transactions
        # Fetch all cards to assign transactions randomly
        all_cards = session.exec(select(CreditCard)).all()
        if not all_cards:
            print("❌ Error: No cards found!")
            return

        expenses = []
        today = datetime.now()

        print(f"🎲 Generating {NUM_TRANSACTIONS} expenses...")

        for _ in range(NUM_TRANSACTIONS):
            # A. Pick a random card
            card = random.choice(all_cards)

            # B. Pick a random Category & Merchant
            category = random.choice(list(MERCHANTS_BY_CATEGORY.keys()))
            merchant = random.choice(MERCHANTS_BY_CATEGORY[category])

            # C. Pick a random Platform (biased slightly towards Direct)
            if random.random() < 0.4:
                platform = "Direct"
            else:
                platform = random.choice(PLATFORMS)

            # D. Random Amount (Weighted: mostly small, sometimes big)
            if random.random() < 0.7:
                amount = random.uniform(100, 3000)  # Common spend
            elif random.random() < 0.9:
                amount = random.uniform(3000, 15000)  # Occasional spend
            else:
                amount = random.uniform(15000, 80000)  # Big ticket

            # E. Random Date (0 to DAYS_HISTORY days ago)
            days_ago = random.randint(0, DAYS_HISTORY)
            txn_date = today - timedelta(days=days_ago)
            # Add random time to the date
            txn_date = txn_date.replace(
                hour=random.randint(9, 23), minute=random.randint(0, 59)
            )

            # Create Expense
            exp = Expense(
                card_id=card.id,
                amount=round(amount, 2),
                merchant=merchant,
                category=category,
                platform=platform,
                date=txn_date,
                points_earned=0.0,  # To be calculated by the brain later!
            )
            expenses.append(exp)

        # Batch insert for speed
        session.add_all(expenses)
        session.commit()

        print(
            f"✅ Successfully seeded {NUM_TRANSACTIONS} transactions across {len(all_cards)} cards."
        )


if __name__ == "__main__":
    seed()
