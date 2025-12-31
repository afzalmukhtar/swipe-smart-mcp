"""
Test script to verify tier matching logic.

Tests:
1. Prime member → gets 5% rule on Amazon
2. Non-Prime member → gets 3% rule on Amazon
3. Card without tier_status → gets universal rules only
"""

from datetime import datetime

from sqlmodel import Session, select

from src import CreditCard, Expense, create_db_and_tables, engine
from src.logic.rewards import RewardsEngine


def test_tier_matching():
    """Test that tier matching works correctly."""
    create_db_and_tables()

    with Session(engine) as session:
        # Find Amazon ICICI cards (Prime and Non-Prime)
        prime_card = session.exec(
            select(CreditCard).where(CreditCard.name.contains("Prime"))
        ).first()

        non_prime_card = session.exec(
            select(CreditCard).where(CreditCard.name.contains("Non-Prime"))
        ).first()

        # Find a card without tier_status (e.g., HDFC Regalia)
        generic_card = session.exec(
            select(CreditCard).where(CreditCard.name.contains("Regalia"))
        ).first()

        if not prime_card or not non_prime_card:
            print("❌ Run seed.py first to create test cards!")
            print("   uv run python scripts/seed.py")
            return

        print("=" * 60)
        print("TIER MATCHING TEST")
        print("=" * 60)

        # Show card tier_status
        print(f"\n📇 Prime Card: {prime_card.name}")
        print(f"   tier_status: {prime_card.tier_status}")

        print(f"\n📇 Non-Prime Card: {non_prime_card.name}")
        print(f"   tier_status: {non_prime_card.tier_status}")

        if generic_card:
            print(f"\n📇 Generic Card: {generic_card.name}")
            print(f"   tier_status: {generic_card.tier_status}")

        # Create test expense for Amazon
        print("\n" + "-" * 60)
        print("TEST: ₹1000 Amazon purchase")
        print("-" * 60)

        engine_instance = RewardsEngine(session)

        # Test 1: Prime card on Amazon
        expense_prime = Expense(
            amount=1000.0,
            merchant="Amazon India",
            category="Shopping",
            platform="Direct",
            date=datetime.now(),
            card_id=prime_card.id,
        )
        expense_prime.card = prime_card

        result_prime = engine_instance.calculate_rewards(expense_prime)
        print(f"\n✅ Prime Card Result:")
        print(f"   Total Points: {result_prime.total_points}")
        print(f"   Base: {result_prime.base_points}, Bonus: {result_prime.bonus_points}")
        for line in result_prime.breakdown:
            print(f"   → {line}")

        # Test 2: Non-Prime card on Amazon
        expense_non_prime = Expense(
            amount=1000.0,
            merchant="Amazon India",
            category="Shopping",
            platform="Direct",
            date=datetime.now(),
            card_id=non_prime_card.id,
        )
        expense_non_prime.card = non_prime_card

        result_non_prime = engine_instance.calculate_rewards(expense_non_prime)
        print(f"\n✅ Non-Prime Card Result:")
        print(f"   Total Points: {result_non_prime.total_points}")
        print(f"   Base: {result_non_prime.base_points}, Bonus: {result_non_prime.bonus_points}")
        for line in result_non_prime.breakdown:
            print(f"   → {line}")

        # Test 3: Generic card (no tier) on same merchant
        if generic_card:
            expense_generic = Expense(
                amount=1000.0,
                merchant="Amazon India",
                category="Shopping",
                platform="Direct",
                date=datetime.now(),
                card_id=generic_card.id,
            )
            expense_generic.card = generic_card

            result_generic = engine_instance.calculate_rewards(expense_generic)
            print(f"\n✅ Generic Card Result (no tier):")
            print(f"   Total Points: {result_generic.total_points}")
            print(f"   Base: {result_generic.base_points}, Bonus: {result_generic.bonus_points}")
            for line in result_generic.breakdown:
                print(f"   → {line}")

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Prime (5% expected):     {result_prime.total_points} pts on ₹1000")
        print(f"Non-Prime (3% expected): {result_non_prime.total_points} pts on ₹1000")
        if generic_card:
            print(f"Generic (base rate):     {result_generic.total_points} pts on ₹1000")

        # Verify expectations
        print("\n" + "-" * 60)
        print("VERIFICATION")
        print("-" * 60)
        
        # Prime should get 5% (base 2.0 + bonus 3.0 = 5.0) → 5000 pts on ₹1000
        # Non-Prime should get 3% (base 1.0 + bonus 2.0 = 3.0) → 3000 pts on ₹1000
        if result_prime.total_points > result_non_prime.total_points:
            print("✅ Prime gets MORE points than Non-Prime (correct!)")
        else:
            print("❌ Something's wrong - Prime should get more points")


if __name__ == "__main__":
    test_tier_matching()
