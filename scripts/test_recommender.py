"""Test script for CardRecommender."""

import warnings
from sqlmodel import Session

from src.db import engine
from src.logic.recommender import recommend_all_cards, recommend_card

# Suppress SQLAlchemy autoflush warnings for cleaner output
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*autoflush.*")


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def print_subheader(title: str):
    print(f"\n{title}")
    print("-" * 50)


def print_card_result(r: dict, verbose: bool = True):
    """Print a single card recommendation."""
    print(f"\n#{r['rank']} {r['card_name']} ({r['bank']})")
    print(f"   💰 Best Value: ₹{r['cash_value']['best_value']:.2f} via {r['cash_value']['best_partner']}")
    print(f"   🎯 Points: {r['points']['total']:.1f} (base: {r['points']['base']:.1f}, bonus: {r['points']['bonus']:.1f})")
    print(f"   📊 Multiplier: {r['multipliers']['effective']}x | Rule: {r['matched_rule']}")
    if r['cap_status']['warning']:
        print(f"   ⚠️  {r['cap_status']['warning']}")
    if verbose and r['cash_value']['all_options']:
        print("   📋 All redemption paths:")
        for opt in r['cash_value']['all_options'][:4]:
            print(f"      • {opt['partner']}: ₹{opt['total_value']:.2f}")


def test_recommender():
    """Test the card recommender with sample transactions."""
    with Session(engine) as session:
        print_header("CARD RECOMMENDER TESTS")

        # Test 1: Amazon Shopping
        print_subheader("📦 Test 1: ₹5000 Amazon Shopping")
        results = recommend_all_cards(session, 5000, "Amazon", "Shopping", "Amazon")
        if not results:
            print("❌ No cards found!")
            return
        for r in results[:5]:
            print_card_result(r, verbose=False)

        # Test 2: Food Delivery
        print_subheader("🍽️  Test 2: ₹2000 Swiggy Food Delivery")
        results = recommend_all_cards(session, 2000, "Swiggy", "Food Delivery", "Swiggy")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 3: Large Travel Purchase
        print_subheader("✈️  Test 3: ₹50000 Flight Booking (MakeMyTrip)")
        results = recommend_all_cards(session, 50000, "MakeMyTrip", "Travel", "MakeMyTrip")
        for r in results[:3]:
            print_card_result(r, verbose=True)

        # Test 4: Grocery
        print_subheader("🛒 Test 4: ₹3000 BigBasket Grocery")
        results = recommend_all_cards(session, 3000, "BigBasket", "Grocery", "BigBasket")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 5: Fuel
        print_subheader("⛽ Test 5: ₹5000 Fuel Purchase")
        results = recommend_all_cards(session, 5000, "HP Petrol", "Fuel", "Direct")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 6: Entertainment / OTT
        print_subheader("🎬 Test 6: ₹1500 Netflix Subscription")
        results = recommend_all_cards(session, 1500, "Netflix", "Entertainment", "Netflix")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 7: Utility Bills
        print_subheader("💡 Test 7: ₹4000 Electricity Bill")
        results = recommend_all_cards(session, 4000, "BESCOM", "Utilities", "Direct")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 8: Dining Out
        print_subheader("🍴 Test 8: ₹3500 Restaurant Dining")
        results = recommend_all_cards(session, 3500, "Mainland China", "Dining", "Direct")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 9: Small Purchase (Edge Case)
        print_subheader("🪙 Test 9: ₹100 Small Purchase")
        results = recommend_all_cards(session, 100, "Local Store", "General", "Direct")
        for r in results[:3]:
            print_card_result(r, verbose=False)

        # Test 10: Large Luxury Purchase
        print_subheader("💎 Test 10: ₹200000 Luxury Watch")
        results = recommend_all_cards(session, 200000, "Ethos", "Luxury", "Direct")
        for r in results[:3]:
            print_card_result(r, verbose=True)

        # Summary: Best Card Function
        print_subheader("🏆 QUICK BEST CARD TESTS")
        test_cases = [
            (10000, "Flipkart", "Shopping", "Flipkart"),
            (8000, "Zomato", "Food Delivery", "Zomato"),
            (25000, "IRCTC", "Travel", "IRCTC"),
        ]
        for amount, merchant, category, platform in test_cases:
            best = recommend_card(session, amount, merchant, category, platform)
            if best:
                print(f"₹{amount} {merchant}: {best['card_name']} → ₹{best['cash_value']['best_value']:.0f}")

        print_header("ALL TESTS COMPLETE ✅")


if __name__ == "__main__":
    test_recommender()
