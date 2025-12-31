"""
Card Recommender - Finds the best credit card for a transaction.

================================================================================
LLM GUIDELINES FOR CARD RECOMMENDATION
================================================================================

UNDERSTANDING THE OUTPUT:
-------------------------
Each card recommendation contains:
- `card_name`, `bank`: Card identification
- `points.total`: Raw points earned (base + bonus)
- `multipliers.effective`: Combined earn rate (e.g., 5.0x means 5 pts per ₹1)
- `matched_rule`: Which reward rule triggered (e.g., "Shopping", "Dining")
- `cash_value.best_value`: **PRIMARY METRIC** - Maximum ₹ value achievable
- `cash_value.best_partner`: How to redeem for max value
- `cash_value.all_options`: All redemption paths with their values
- `cap_status`: Whether card is hitting spend limits

DECISION LOGIC (in priority order):
-----------------------------------
1. **BEST VALUE** → Use `cash_value.best_value` (already sorted DESC)
   - The #1 ranked card gives the highest real ₹ return
   - This accounts for both points earned AND redemption efficiency
   - Example: 500 pts @ ₹2/pt = ₹1000 beats 800 pts @ ₹0.50/pt = ₹400

2. **REDEMPTION PATH** → Check `cash_value.best_partner`
   - "Direct Cashback": Simple, instant value
   - Airline/Hotel partners: Higher value but requires travel redemption
   - If user prefers cashback, look at `cash_value.base_value` instead

3. **CAP STATUS** → Check `cap_status.is_capped` and `cap_status.warning`
   - If `is_capped: True` or warning exists, mention it to user
   - Suggest alternative card if primary is near cap limit

4. **CATEGORY CONTEXT**:
   - Travel purchases: Airline partner redemptions are ideal
   - Everyday spend: Prefer consistent cashback cards
   - Large purchases: Check if hitting cap, suggest splitting

HOW TO RESPOND TO USER:
-----------------------
Structure your response with these elements:

1. **RECOMMENDATION** (Required)
   "Use [card_name] for this ₹[amount] [category] purchase"

2. **REASON** (Required)
   "You'll earn [points] points ([multiplier]x rate) worth ₹[best_value]"

3. **REDEMPTION ACTION** (Required)
   "Redeem via [best_partner] for maximum value"
   OR "Points can be used as direct cashback"

4. **ALTERNATIVE** (If relevant)
   "Alternative: [card_name] gives ₹[value] (if you prefer [reason])"

5. **WARNING** (If applicable)
   "Note: [cap_warning]" or "This card is near its monthly cap"

EXAMPLE RESPONSES:
------------------

**Simple Purchase:**
"For this ₹5,000 Amazon purchase, use your **HDFC Infinia**.
You'll earn 25,000 points (5x rate) worth **₹50,000** when redeemed via Marriott Bonvoy.
Alternative: HDFC Regalia Gold gives ₹49,000 value."

**With Cap Warning:**
"Use **Axis Ace** for this ₹4,000 utility bill — earns 8,500 points worth ₹8,500.
⚠️ Note: You've used 85% of your monthly bonus cap. Consider HDFC Infinia (₹26,400 value) for larger bills this month."

**Travel Redemption:**
"For this ₹50,000 flight booking, use **HDFC Regalia Gold**.
Earns 50,000 points worth **₹175,000** via Marriott Bonvoy transfer.
If you prefer instant value: ₹15,000 direct cashback is also available."

**When No Good Option:**
"For this ₹2,000 Swiggy order, your best option is HDFC Regalia Gold (₹7,000 value).
Note: None of your cards have specific Food Delivery bonuses — consider adding a dining-focused card."

FIELDS QUICK REFERENCE:
-----------------------
result['card_name']                    → Card name
result['points']['total']              → Total points earned
result['multipliers']['effective']     → Earn rate (e.g., 5.0x)
result['matched_rule']                 → Rule that matched (e.g., "Shopping")
result['cash_value']['best_value']     → Best ₹ value (PRIMARY SORT KEY)
result['cash_value']['best_partner']   → Best redemption method
result['cash_value']['base_value']     → Direct cashback value
result['cash_value']['all_options']    → List of all redemption paths
result['cap_status']['is_capped']      → True if cap hit
result['cap_status']['warning']        → Cap warning message if any
result['rank']                         → 1 = best, 2 = second best, etc.
================================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from src.logic.rewards import RewardsEngine
from src.models import CreditCard, Expense, RewardRule


@dataclass
class RedemptionOption:
    """Cash value calculation for a single redemption partner."""

    partner_name: str
    transfer_ratio: float  # e.g., 1:1 or 2:1
    point_value: float  # estimated INR per point after transfer
    cash_value: float  # total INR value for this redemption path


@dataclass
class CardRecommendation:
    """Result of analyzing a single card for a transaction."""

    card_id: int
    card_name: str
    bank: str

    # Points Earned
    total_points: float = 0.0
    base_points: float = 0.0
    bonus_points: float = 0.0

    # Multiplier Info
    base_multiplier: float = 0.0
    bonus_multiplier: float = 0.0
    effective_multiplier: float = 0.0  # base + bonus

    # Rule Info
    matched_rule: Optional[str] = None
    rule_breakdown: List[str] = field(default_factory=list)

    # Cash Values
    base_cash_value: float = 0.0  # points × card's base_point_value
    redemption_options: List[RedemptionOption] = field(default_factory=list)
    best_redemption_value: float = 0.0  # highest value among all options
    best_redemption_partner: Optional[str] = None

    # Cap Status
    is_capped: bool = False
    cap_headroom_pct: Optional[float] = None
    cap_warning: Optional[str] = None

    # Sorting
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM consumption."""
        return {
            "card_id": self.card_id,
            "card_name": self.card_name,
            "bank": self.bank,
            "points": {
                "total": self.total_points,
                "base": self.base_points,
                "bonus": self.bonus_points,
            },
            "multipliers": {
                "base": self.base_multiplier,
                "bonus": self.bonus_multiplier,
                "effective": self.effective_multiplier,
            },
            "matched_rule": self.matched_rule,
            "breakdown": self.rule_breakdown,
            "cash_value": {
                "base_value": self.base_cash_value,
                "best_value": self.best_redemption_value,
                "best_partner": self.best_redemption_partner,
                "all_options": [
                    {
                        "partner": opt.partner_name,
                        "ratio": opt.transfer_ratio,
                        "point_value": opt.point_value,
                        "total_value": opt.cash_value,
                    }
                    for opt in self.redemption_options
                ],
            },
            "cap_status": {
                "is_capped": self.is_capped,
                "headroom_pct": self.cap_headroom_pct,
                "warning": self.cap_warning,
            },
            "rank": self.rank,
        }


@dataclass
class RecommendationRequest:
    """Input for card comparison."""

    amount: float
    merchant: str
    category: str
    platform: str = "Direct"
    is_online: Optional[bool] = None


class CardRecommender:
    """
    Compares multiple cards to find the best one for a transaction.

    Usage:
        recommender = CardRecommender(session)
        results = recommender.recommend_for_expense(amount, merchant, category)
        # results is a list of dicts sorted by best_redemption_value DESC
    """

    def __init__(self, session: Session):
        self.session = session
        self.engine = RewardsEngine(session)

    def recommend_for_expense(
        self,
        amount: float,
        merchant: str,
        category: str,
        platform: str = "Direct",
        is_online: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: Fetch all cards, calculate rewards, return ranked results.

        Returns list of dictionaries sorted by best_redemption_value DESC.
        """
        cards = self._fetch_all_cards()

        if not cards:
            return []

        request = RecommendationRequest(
            amount=amount,
            merchant=merchant,
            category=category,
            platform=platform,
            is_online=is_online,
        )

        recommendations = []
        for card in cards:
            rec = self._analyze_card(card, request)
            recommendations.append(rec)

        recommendations.sort(key=lambda r: r.best_redemption_value, reverse=True)

        for i, rec in enumerate(recommendations):
            rec.rank = i + 1

        return [rec.to_dict() for rec in recommendations]

    def get_best_card(
        self,
        amount: float,
        merchant: str,
        category: str,
        platform: str = "Direct",
    ) -> Optional[Dict[str, Any]]:
        """Convenience method to get just the top recommendation as dict."""
        results = self.recommend_for_expense(amount, merchant, category, platform)
        return results[0] if results else None

    def _fetch_all_cards(self) -> List[CreditCard]:
        """Fetch all credit cards from the database."""
        statement = select(CreditCard)
        return list(self.session.exec(statement).all())

    def _analyze_card(
        self,
        card: CreditCard,
        request: RecommendationRequest,
    ) -> CardRecommendation:
        """
        Simulate reward calculation for a card without persisting.

        Steps:
        1. Create temporary expense
        2. Run through RewardsEngine
        3. Calculate redemption values for all partners
        4. Check cap headroom
        """
        temp_expense = self._create_temp_expense(card, request)

        reward_result = self.engine.calculate_rewards(temp_expense)

        matched_rule = self._get_matched_rule(card, temp_expense)
        base_mult = matched_rule.base_multiplier if matched_rule else 0.0
        bonus_mult = matched_rule.bonus_multiplier if matched_rule else 0.0

        redemption_options = self._calculate_redemption_values(
            card, reward_result.total_points
        )

        best_option = max(redemption_options, key=lambda x: x.cash_value) if redemption_options else None

        cap_headroom = self._calculate_cap_headroom(card, matched_rule)
        cap_warning = None
        if cap_headroom is not None and cap_headroom < 20:
            cap_warning = f"Warning: Only {cap_headroom:.0f}% cap remaining"

        rec = CardRecommendation(
            card_id=card.id or 0,
            card_name=card.name,
            bank=card.bank,
            total_points=reward_result.total_points,
            base_points=reward_result.base_points,
            bonus_points=reward_result.bonus_points,
            base_multiplier=base_mult,
            bonus_multiplier=bonus_mult,
            effective_multiplier=base_mult + bonus_mult,
            matched_rule=matched_rule.category if matched_rule else None,
            rule_breakdown=reward_result.breakdown,
            base_cash_value=reward_result.total_points * card.base_point_value,
            redemption_options=redemption_options,
            best_redemption_value=best_option.cash_value if best_option else reward_result.total_points * card.base_point_value,
            best_redemption_partner=best_option.partner_name if best_option else "Direct Cashback",
            is_capped=reward_result.is_capped,
            cap_headroom_pct=cap_headroom,
            cap_warning=cap_warning,
        )

        return rec

    def _create_temp_expense(
        self,
        card: CreditCard,
        request: RecommendationRequest,
    ) -> Expense:
        """Create a temporary (non-persisted) expense for simulation."""
        return Expense(
            amount=request.amount,
            merchant=request.merchant,
            category=request.category,
            platform=request.platform,
            is_online=request.is_online,
            card_id=card.id,
            card=card,
        )

    def _get_matched_rule(
        self,
        card: CreditCard,
        expense: Expense,
    ) -> Optional[RewardRule]:
        """Find the rule that would be applied for this expense."""
        return self.engine._find_best_rule(card, expense)

    def _calculate_redemption_values(
        self,
        card: CreditCard,
        total_points: float,
    ) -> List[RedemptionOption]:
        """Calculate cash value for each redemption partner."""
        options = []

        options.append(
            RedemptionOption(
                partner_name="Direct Cashback",
                transfer_ratio=1.0,
                point_value=card.base_point_value,
                cash_value=total_points * card.base_point_value,
            )
        )

        for partner in card.redemption_partners:
            transferred_points = total_points * partner.transfer_ratio
            cash_value = transferred_points * partner.estimated_value

            options.append(
                RedemptionOption(
                    partner_name=partner.partner_name,
                    transfer_ratio=partner.transfer_ratio,
                    point_value=partner.estimated_value,
                    cash_value=cash_value,
                )
            )

        return options

    def _calculate_cap_headroom(
        self,
        card: CreditCard,
        matched_rule: Optional[RewardRule],
    ) -> Optional[float]:
        """
        Calculate % of cap remaining for the matched rule's bucket.

        Returns None if rule has no cap, otherwise 0-100%.
        """
        if not matched_rule or not matched_rule.cap_bucket:
            return None

        bucket = matched_rule.cap_bucket

        start, end = self.engine._get_period_dates(
            bucket.period, bucket.reset_anchor_month, datetime.now()
        )
        current_usage = self.engine._get_bucket_usage(bucket.id, start, end)

        if bucket.max_points <= 0:
            return None

        used_pct = (current_usage / bucket.max_points) * 100
        return max(0.0, 100.0 - used_pct)


def recommend_card(
    session: Session,
    amount: float,
    merchant: str,
    category: str,
    platform: str = "Direct",
) -> Optional[Dict[str, Any]]:
    """
    Convenience function: Find the best card for a transaction.

    Example:
        best = recommend_card(session, 5000, "Amazon", "Shopping")
        if best:
            print(f"Use {best['card_name']} for {best['points']['total']} pts")
    """
    recommender = CardRecommender(session)
    return recommender.get_best_card(amount, merchant, category, platform)


def recommend_all_cards(
    session: Session,
    amount: float,
    merchant: str,
    category: str,
    platform: str = "Direct",
) -> List[Dict[str, Any]]:
    """
    Get ranked recommendations for all cards.

    Example:
        results = recommend_all_cards(session, 5000, "Amazon", "Shopping")
        for r in results:
            print(f"{r['rank']}. {r['card_name']}: ₹{r['cash_value']['best_value']}")
    """
    recommender = CardRecommender(session)
    return recommender.recommend_for_expense(amount, merchant, category, platform)
