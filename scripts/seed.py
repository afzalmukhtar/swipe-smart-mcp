import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

# --- PATH FIXER ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from sqlmodel import Session, select
from src import (
    CapBucket,
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
    """Returns a list of complex card setups."""
    return [
        {
            "card": CreditCard(
                name="HDFC Regalia Gold",
                bank="HDFC",
                network="Mastercard",
                monthly_limit=500000.0,
                billing_cycle_start=15,
                base_point_value=0.20,
            ),
            "buckets": [
                CapBucket(
                    name="SmartBuy Monthly",
                    max_points=4000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
                CapBucket(
                    name="Milestone",
                    max_points=10000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                ),
            ],
            "rules": [
                {
                    "category": "SmartBuy Amazon",
                    "base": 1.0,
                    "bonus": 4.0,
                    "bucket_idx": 0,
                },
                {"category": "Dining", "base": 2.0, "bonus": 0.0, "bucket_idx": None},
                {
                    "category": "Shopping - Online",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                },
            ],
        },
        {
            "card": CreditCard(
                name="SBI Cashback",
                bank="SBI",
                network="Visa",
                monthly_limit=200000.0,
                billing_cycle_start=1,
                base_point_value=1.00,
            ),
            "buckets": [
                CapBucket(
                    name="Cashback Monthly",
                    max_points=5000.0,
                    period=PeriodType.STATEMENT_CYCLE,
                )
            ],
            "rules": [
                {
                    "category": "Shopping - Online",
                    "base": 5.0,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                },
                {"category": "Dining", "base": 1.0, "bonus": 0.0, "bucket_idx": None},
                {
                    "category": "Travel - Flights",
                    "base": 5.0,
                    "bonus": 0.0,
                    "bucket_idx": 0,
                },
            ],
        },
        {
            "card": CreditCard(
                name="Axis Ace",
                bank="Axis",
                network="Visa",
                monthly_limit=150000.0,
                billing_cycle_start=10,
                base_point_value=1.00,
            ),
            "buckets": [
                CapBucket(
                    name="Ace Cashback",
                    max_points=500.0,
                    period=PeriodType.STATEMENT_CYCLE,
                )
            ],
            "rules": [
                {"category": "Utilities", "base": 5.0, "bonus": 0.0, "bucket_idx": 0},
                {"category": "Dining", "base": 4.0, "bonus": 0.0, "bucket_idx": None},
                {"category": "Fuel", "base": 1.0, "bonus": 0.0, "bucket_idx": None},
            ],
        },
        {
            "card": CreditCard(
                name="Amex Platinum Travel",
                bank="Amex",
                network="Amex",
                monthly_limit=800000.0,
                billing_cycle_start=5,
                base_point_value=0.40,
            ),
            "buckets": [],  # Amex usually uncapped or high caps
            "rules": [
                {
                    "category": "Travel - Flights",
                    "base": 3.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                },
                {
                    "category": "Travel - Hotels",
                    "base": 3.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                },
                {
                    "category": "Shopping - Retail",
                    "base": 1.0,
                    "bonus": 0.0,
                    "bucket_idx": None,
                },
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
                    )
                    session.add(rule)

                # Add Dummy Partner
                partner = RedemptionPartner(
                    card_id=card.id,
                    partner_name="Generic Airline",
                    transfer_ratio=1.0,
                    estimated_value=1.0,
                )
                session.add(partner)

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
