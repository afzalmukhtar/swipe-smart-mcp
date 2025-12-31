import sys
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

# Fix path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src import (
    BucketScope,
    CapBucket,
    CreditCard,
    Expense,
    PeriodType,
    RewardRule,
    engine,
)
from src.rewards import calculate_rewards


def test_rewards():
    with Session(engine) as session:
        print("\n--- Setup: Creating Setup Test Card ---")
        # Create a fresh card to ensure no interference from seed data
        test_card = CreditCard(
            name="Test Card",
            bank="Test Bank",
            monthly_limit=100000.0,
            billing_cycle_start=1,
        )
        session.add(test_card)
        session.commit()
        session.refresh(test_card)

        # Add Rules
        # 1. Dining Rule (2x Base + 2x Bonus, Capped at 2000)
        dining_bucket = CapBucket(
            name="Dining Test Cap",
            max_points=2000.0,
            card_id=test_card.id,
            period=PeriodType.STATEMENT_MONTH,
        )
        session.add(dining_bucket)
        session.commit()

        dining_rule = RewardRule(
            category="Dining",
            base_multiplier=2.0,
            bonus_multiplier=2.0,
            card_id=test_card.id,
            cap_bucket_id=dining_bucket.id,
        )
        session.add(dining_rule)

        # 2. Fuel Rule (Override Exclusion, 1x Base, Uncapped)
        fuel_rule = RewardRule(
            category="Fuel",
            base_multiplier=1.0,
            bonus_multiplier=0.0,
            card_id=test_card.id,
        )
        session.add(fuel_rule)

        # 3. Global Cap Bucket (50k)
        global_bucket = CapBucket(
            name="Global Test Cap",
            max_points=50000.0,
            card_id=test_card.id,
            period=PeriodType.STATEMENT_MONTH,
            bucket_scope=BucketScope.GLOBAL,
        )
        session.add(global_bucket)

        session.commit()
        session.refresh(test_card)  # Load relationships

        print(f"Test Card Created: {test_card.name} [ID: {test_card.id}]")

        # 2. Test Normal Earning (Waterfall)
        print("\n--- Test 1: Normal Earning (Dining) ---")
        exp1 = Expense(
            amount=1000,
            merchant="Chili's",
            category="Dining",
            card_id=test_card.id,
            date=datetime.now(),
        )
        exp1.card = test_card
        res1 = calculate_rewards(session, exp1)
        print(f"Points: {res1.total_points} (Expected 4000.0)")
        print(f"Breakdown: {res1.breakdown}")

        # 3. Test Global Exclusion Override (Fuel)
        print("\n--- Test 2: Exclusion Override (Fuel) ---")
        exp2 = Expense(
            amount=2000,
            merchant="Shell",
            category="Fuel",
            card_id=test_card.id,
            date=datetime.now(),
        )
        exp2.card = test_card
        res2 = calculate_rewards(session, exp2)
        print(f"Points: {res2.total_points} (Expected 2000.0)")
        print(f"Breakdown: {res2.breakdown}")

        # 4. Test Hard Exclusion (Rent)
        print("\n--- Test 3: Hard Exclusion (Rent) ---")
        exp3 = Expense(
            amount=10000,
            merchant="NoBroker",
            category="Rent",
            card_id=test_card.id,
            date=datetime.now(),
        )
        exp3.card = test_card
        res3 = calculate_rewards(session, exp3)
        print(f"Points: {res3.total_points} (Expected: 0.0)")
        print(f"Breakdown: {res3.breakdown}")

        # 5. Test Global Cap Hit
        print("\n--- Test 4: Global Cap Hit ---")
        # Step A: Fill the bucket
        large_tx = Expense(
            amount=2000000,
            merchant="Apple Store",
            category="Shopping",
            card_id=test_card.id,
            date=datetime.now(),
            points_earned=60000,  # Exceeds 50k
        )
        large_tx.card = test_card
        session.add(large_tx)
        session.commit()
        # session.refresh(large_tx)

        # Step B: Try another transaction
        exp4 = Expense(
            amount=100,
            merchant="Test",
            category="Dining",
            card_id=test_card.id,
            date=datetime.now(),
        )
        exp4.card = test_card
        res4 = calculate_rewards(session, exp4)
        print(f"Points: {res4.total_points} (Expected: 0.0)")
        print(f"Breakdown: {res4.breakdown}")
        print(f"Is Capped: {res4.is_capped}")

        # 6. Test Excluded Category while Cap Hit (Priority Check)
        print("\n--- Test 5: Excluded Category while Cap Hit ---")
        # Global Cap is already hit from Test 4.
        # Now try Rent (Hard Exclusion). Should say "Excluded", NOT "Cap Hit".
        exp5 = Expense(
            amount=5000,
            merchant="NoBroker",
            category="Rent",
            card_id=test_card.id,
            date=datetime.now(),
        )
        exp5.card = test_card
        res5 = calculate_rewards(session, exp5)
        print(f"Points: {res5.total_points} (Expected: 0.0)")
        print(f"Breakdown: {res5.breakdown}")
        # Expect breakdown to contain "globally excluded" NOT "Global Limit Hit"

        # 7. Test SBI Cashback Online (Generic Condition)
        print("\n--- Test 6: SBI Cashback Online (Generic Condition) ---")
        sbi_card = session.exec(
            select(CreditCard).where(CreditCard.name == "SBI Cashback")
        ).first()
        if sbi_card:
            # A. Online Transaction (5%)
            exp6 = Expense(
                amount=1000,
                merchant="Random Site",
                category="Shopping",
                card_id=sbi_card.id,
                date=datetime.now(),
                is_online=True,
            )
            exp6.card = sbi_card
            res6 = calculate_rewards(session, exp6)
            print(f"Online Points: {res6.total_points} (Expected: 50.0 -> 5% of 1000)")
            print(f"Breakdown: {res6.breakdown}")

            # B. Offline Transaction (1%)
            print("\n--- Test 6b: SBI Cashback Offline ---")
            exp6b = Expense(
                amount=1000,
                merchant="Local Shop",
                category="Shopping",
                card_id=sbi_card.id,
                date=datetime.now(),
                is_online=False,
            )
            exp6b.card = sbi_card
            res6b = calculate_rewards(session, exp6b)
            print(
                f"Offline Points: {res6b.total_points} (Expected: 10.0 -> 1% of 1000)"
            )
            print(f"Breakdown: {res6b.breakdown}")
        else:
            print("Skipping Test 6: SBI Cashback card not found.")

        # 8. Test Base Rate Fallback (HDFC Regalia)
        print("\n--- Test 7: Base Rate Fallback (HDFC) ---")
        # Using HDFC Regalia Gold (we added Base rule to it in seed)
        hdfc_card = session.exec(
            select(CreditCard).where(CreditCard.name == "HDFC Regalia Gold")
        ).first()
        if hdfc_card:
            # A. Unknown Category (Base Rate 1%)
            exp7 = Expense(
                amount=2000,
                merchant="Mystery",
                category="Unknown",
                card_id=hdfc_card.id,
                date=datetime.now(),
            )
            exp7.card = hdfc_card
            res7 = calculate_rewards(session, exp7)
            # HDFC Base Rule was 1.0x (replaced 1.33 with 1.0)
            print(
                f"Points: {res7.total_points} (Expected: 1000.0 * 1.0 = 1000.0 with Base Rule)"
            )
            print(f"Breakdown: {res7.breakdown}")
        else:
            print("Skipping Test 7: HDFC Regalia card not found.")


if __name__ == "__main__":
    test_rewards()
