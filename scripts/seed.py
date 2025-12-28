# scripts/seed.py
from datetime import datetime, timedelta

from sqlmodel import Session, select

# Clean imports from the 'src' package
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


def seed():
    print("🌱 Seeding Database...")

    # 1. Initialize Tables (Create file if missing)
    create_db_and_tables()

    with Session(engine) as session:
        # Check if data exists to avoid duplicates
        if session.exec(select(CreditCard)).first():
            print("⚠️  Database already has data. Skipping seed.")
            return

        print("Creating HDFC Regalia Gold Setup...")

        # --- A. Create the Credit Card ---
        card = CreditCard(
            name="HDFC Regalia Gold",
            bank="HDFC",
            network="Mastercard",
            monthly_limit=500000.0,
            billing_cycle_start=15,  # Bill generates on the 15th
            base_point_value=0.20,  # 1 Pt = 0.20 INR (Cashback floor)
        )
        session.add(card)
        session.commit()
        session.refresh(card)

        # --- B. Create Buckets (The Limits) ---

        # 1. SmartBuy Monthly (Shared Cap: 4000 pts)
        bucket_sb = CapBucket(
            name="SmartBuy Monthly",
            card_id=card.id,
            max_points=4000.0,
            period=PeriodType.STATEMENT_CYCLE,
        )

        # 2. Partner/Milestone Cap (Separate Cap: 10,000 pts)
        bucket_partner = CapBucket(
            name="Partner/Milestone",
            card_id=card.id,
            max_points=10000.0,
            period=PeriodType.STATEMENT_CYCLE,
        )

        session.add(bucket_sb)
        session.add(bucket_partner)
        session.commit()
        # Refresh to get IDs for linking
        session.refresh(bucket_sb)
        session.refresh(bucket_partner)

        # --- C. Create Reward Rules (The Multipliers) ---

        rules = [
            # Rule 1: SmartBuy Amazon (5x Total)
            # 1x Base + 4x Bonus. Bonus is limited by the SmartBuy Bucket.
            RewardRule(
                card_id=card.id,
                category="SmartBuy Amazon",
                base_multiplier=1.0,
                bonus_multiplier=4.0,
                cap_bucket_id=bucket_sb.id,
            ),
            # Rule 2: Dining (2x Total)
            # Flat 2x. Usually uncapped, so no bucket linked.
            RewardRule(
                card_id=card.id,
                category="Dining",
                base_multiplier=2.0,
                bonus_multiplier=0.0,
                cap_bucket_id=None,
            ),
            # Rule 3: Myntra Partner (5x Total)
            # Uses the separate "Partner" bucket.
            RewardRule(
                card_id=card.id,
                category="Myntra Partner",
                base_multiplier=1.0,
                bonus_multiplier=4.0,
                cap_bucket_id=bucket_partner.id,
            ),
        ]
        session.add_all(rules)

        # --- D. Create Redemption Partners ---

        partners = [
            # Accor: High Value (1:1 ratio, ~1.8 INR value)
            RedemptionPartner(
                card_id=card.id,
                partner_name="Accor Hotels",
                transfer_ratio=1.0,
                estimated_value=1.80,
            ),
            # Singapore Airlines: Good Value (1:0.5 ratio, ~1.0 INR value)
            RedemptionPartner(
                card_id=card.id,
                partner_name="Singapore Airlines",
                transfer_ratio=0.5,
                estimated_value=1.00,
            ),
        ]
        session.add_all(partners)

        # --- E. Create Sample Transactions (One per Category) ---

        today = datetime.now()
        expenses = [
            # Dining
            Expense(
                card_id=card.id,
                amount=850.0,
                merchant="Swiggy",
                category="Dining",
                platform="Swiggy",
                date=today - timedelta(days=1),
            ),
            # Groceries
            Expense(
                card_id=card.id,
                amount=2500.0,
                merchant="BigBasket",
                category="Groceries",
                platform="Direct",
                date=today - timedelta(days=2),
            ),
            # Travel - Flights
            Expense(
                card_id=card.id,
                amount=12500.0,
                merchant="MakeMyTrip",
                category="Travel - Flights",
                platform="SmartBuy",
                date=today - timedelta(days=5),
            ),
            # Travel - Hotels
            Expense(
                card_id=card.id,
                amount=8000.0,
                merchant="OYO Rooms",
                category="Travel - Hotels",
                platform="Direct",
                date=today - timedelta(days=7),
            ),
            # Travel - Railways
            Expense(
                card_id=card.id,
                amount=1200.0,
                merchant="IRCTC",
                category="Travel - Railways",
                platform="Direct",
                date=today - timedelta(days=3),
            ),
            # Travel - Cabs & Rideshare
            Expense(
                card_id=card.id,
                amount=450.0,
                merchant="Uber",
                category="Travel - Cabs & Rideshare",
                platform="Direct",
                date=today - timedelta(days=1),
            ),
            # Travel - Other
            Expense(
                card_id=card.id,
                amount=3500.0,
                merchant="Cleartrip",
                category="Travel - Other",
                platform="Cleartrip",
                date=today - timedelta(days=10),
            ),
            # Fuel
            Expense(
                card_id=card.id,
                amount=3000.0,
                merchant="HP Petrol Pump",
                category="Fuel",
                platform="Direct",
                date=today - timedelta(days=4),
            ),
            # Utilities
            Expense(
                card_id=card.id,
                amount=2800.0,
                merchant="Tata Power",
                category="Utilities",
                platform="CRED",
                date=today - timedelta(days=6),
            ),
            # Telecom & Internet
            Expense(
                card_id=card.id,
                amount=999.0,
                merchant="Jio Recharge",
                category="Telecom & Internet",
                platform="Direct",
                date=today - timedelta(days=8),
            ),
            # Shopping - Online
            Expense(
                card_id=card.id,
                amount=15000.0,
                merchant="Amazon India",
                category="Shopping - Online",
                platform="Amazon Pay",
                date=today - timedelta(days=3),
            ),
            # Shopping - Retail
            Expense(
                card_id=card.id,
                amount=7500.0,
                merchant="Croma Electronics",
                category="Shopping - Retail",
                platform="Direct",
                date=today - timedelta(days=12),
            ),
            # Entertainment
            Expense(
                card_id=card.id,
                amount=1200.0,
                merchant="BookMyShow",
                category="Entertainment",
                platform="BookMyShow",
                date=today - timedelta(days=2),
            ),
            # Healthcare
            Expense(
                card_id=card.id,
                amount=650.0,
                merchant="1mg",
                category="Healthcare",
                platform="Direct",
                date=today - timedelta(days=9),
            ),
            # Education
            Expense(
                card_id=card.id,
                amount=4999.0,
                merchant="Coursera",
                category="Education",
                platform="Direct",
                date=today - timedelta(days=15),
            ),
            # --- Excluded Categories (typically 0 rewards) ---
            # Insurance
            Expense(
                card_id=card.id,
                amount=25000.0,
                merchant="HDFC Life Insurance",
                category="Insurance",
                platform="Direct",
                date=today - timedelta(days=20),
            ),
            # Government Services
            Expense(
                card_id=card.id,
                amount=5000.0,
                merchant="Income Tax Portal",
                category="Government Services",
                platform="Direct",
                date=today - timedelta(days=25),
            ),
            # Rent
            Expense(
                card_id=card.id,
                amount=35000.0,
                merchant="CRED Rent Pay",
                category="Rent",
                platform="CRED",
                date=today - timedelta(days=1),
            ),
            # Wallet & Prepaid Loads
            Expense(
                card_id=card.id,
                amount=5000.0,
                merchant="Paytm Wallet",
                category="Wallet & Prepaid Loads",
                platform="Direct",
                date=today - timedelta(days=11),
            ),
            # EMI Payments
            Expense(
                card_id=card.id,
                amount=15000.0,
                merchant="HDFC Bank EMI",
                category="EMI Payments",
                platform="Direct",
                date=today - timedelta(days=5),
            ),
            # Jewellery
            Expense(
                card_id=card.id,
                amount=50000.0,
                merchant="Tanishq",
                category="Jewellery",
                platform="Direct",
                date=today - timedelta(days=30),
            ),
            # Other
            Expense(
                card_id=card.id,
                amount=1500.0,
                merchant="Miscellaneous Shop",
                category="Other",
                platform="Direct",
                date=today - timedelta(days=14),
            ),
        ]
        session.add_all(expenses)

        session.commit()
        print("✅ Database Seeded Successfully with HDFC Regalia Gold Data!")


if __name__ == "__main__":
    seed()
