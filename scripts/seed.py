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

        # --- E. Create Sample Transactions ---

        today = datetime.now()
        expenses = [
            # 1. Big Purchase on SmartBuy (₹20,000)
            # Earns: 20k * 5x = 4000 pts (Fills the monthly bucket!)
            Expense(
                card_id=card.id,
                amount=20000.0,
                merchant="Amazon India",
                category="SmartBuy Amazon",
                platform="SmartBuy",
                date=today - timedelta(days=2),
            ),
            # 2. Dining out (₹3,000)
            # Earns: 3k * 2x = 150 pts (Uncapped)
            Expense(
                card_id=card.id,
                amount=3000.0,
                merchant="Truffles",
                category="Dining",
                platform="Direct",
                date=today - timedelta(days=5),
            ),
        ]
        session.add_all(expenses)

        session.commit()
        print("✅ Database Seeded Successfully with HDFC Regalia Gold Data!")


if __name__ == "__main__":
    seed()
