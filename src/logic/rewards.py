import json
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from sqlmodel import Session, func, select

from src.models import (
    BucketScope,
    CreditCard,
    Expense,
    PeriodType,
    RewardRule,
)


@dataclass
class RewardResult:
    """Standardized output for the rewards engine."""

    total_points: float = 0.0
    base_points: float = 0.0
    bonus_points: float = 0.0
    breakdown: List[str] = field(default_factory=list)
    is_capped: bool = False


class RewardsEngine:
    """
    Calculates rewards through a series of gates.

    Flow: Exclusion → Global Cap → Waterfall

    Why this order?
    - Exclusions first: User sees "Excluded" not "Cap Hit" for banned categories
    - Global caps second: No point calculating if card's total limit is hit
    - Waterfall last: Find best rule, calculate points, apply category-specific caps
    """

    # Cap check priority: wider scope checked first
    # If annual limit is hit, no point checking monthly limits
    PERIOD_PRIORITY = {
        PeriodType.STATEMENT_YEAR: 1,
        PeriodType.QUARTER: 2,
        PeriodType.STATEMENT_MONTH: 3,
        PeriodType.DAILY: 4,
    }

    def __init__(self, session: Session):
        self.session = session
        self.GLOBAL_EXCLUSIONS = self._load_exclusions()

    def _load_exclusions(self) -> List[str]:
        """
        Loads excluded categories from data/categories.json.
        These categories typically earn 0 rewards unless a card has a specific override.
        """
        try:
            root_dir = Path(__file__).resolve().parent.parent.parent
            json_path = root_dir / "data" / "categories.json"

            with open(json_path, "r") as f:
                data = json.load(f)

            return [
                cat["name"]
                for cat in data.get("categories", [])
                if cat.get("excluded_from_rewards", False)
            ]
        except Exception as e:
            print(f"Error loading exclusions: {e}")
            return [
                "Rent",
                "Wallet & Prepaid Loads",
                "Insurance",
                "Government Services",
                "EMI",
                "Interest",
                "Cash Advance",
            ]

    def calculate_rewards(self, expense: Expense) -> RewardResult:
        """
        Main entry point. Orchestrates: Exclusion → Global Cap → Waterfall
        """
        if not expense.card:
            return RewardResult(breakdown=["No card linked to transaction."])

        card = expense.card
        result = RewardResult()

        # GATE 1: Exclusion Check
        is_excluded, override_rule = self._check_exclusions(card, expense)
        if is_excluded and not override_rule:
            result.breakdown.append(
                f"Category '{expense.category}' is globally excluded."
            )
            return result

        # GATE 2: Global Cap Check (Annual → Quarterly → Monthly)
        global_cap_hit, cap_msg = self._check_global_caps(card, expense)
        if global_cap_hit:
            result.breakdown.append(cap_msg)
            result.is_capped = True
            return result

        # GATE 3: Waterfall Calculation
        return self._calculate_waterfall(card, expense, override_rule)

    def _check_global_caps(
        self, card: CreditCard, expense: Expense
    ) -> Tuple[bool, str]:
        """
        Checks GLOBAL scope buckets in priority order: Annual → Quarterly → Monthly → Daily
        """
        global_buckets = [
            b for b in card.cap_buckets if b.bucket_scope == BucketScope.GLOBAL
        ]

        sorted_buckets = sorted(
            global_buckets, key=lambda b: self.PERIOD_PRIORITY.get(b.period, 99)
        )

        for bucket in sorted_buckets:
            start_date, end_date = self._get_period_dates(
                bucket.period, bucket.reset_anchor_month, expense.date
            )

            if bucket.bucket_scope == BucketScope.GLOBAL:
                current_points = self._get_global_usage(card.id, start_date, end_date)
            else:
                current_points = self._get_bucket_usage(bucket.id, start_date, end_date)

            if current_points >= bucket.max_points:
                return (
                    True,
                    f"Global Limit Hit: {bucket.name} ({current_points}/{bucket.max_points})",
                )

        return False, ""

    def _get_global_usage(
        self, card_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """Sum ALL points earned by the card in the period."""
        statement = select(func.sum(Expense.points_earned)).where(
            Expense.card_id == card_id,
            Expense.date >= start_date,
            Expense.date <= end_date,
        )
        result = self.session.exec(statement).first()
        return result if result else 0.0

    def _check_exclusions(
        self, card: CreditCard, expense: Expense
    ) -> Tuple[bool, Optional[RewardRule]]:
        """
        Checks if category is globally excluded.
        Returns: (is_excluded, override_rule)
        - If excluded AND no override → 0 points
        - If excluded BUT has override → use that rule in waterfall
        """
        if expense.category not in self.GLOBAL_EXCLUSIONS:
            return False, None

        query = select(RewardRule).where(
            RewardRule.card_id == card.id, RewardRule.category == expense.category
        )
        rule = self.session.exec(query).first()

        if rule:
            return True, rule

        return True, None

    def _calculate_waterfall(
        self,
        card: CreditCard,
        expense: Expense,
        override_rule: Optional[RewardRule] = None,
    ) -> RewardResult:
        """
        Calculates Base + Bonus points, then applies category-specific caps.
        Bonus points are often capped while base points flow through.
        """
        result = RewardResult()

        active_rule = override_rule or self._find_best_rule(card, expense)

        base_rate = 0.0
        bonus_rate = 0.0

        if active_rule:
            base_rate = active_rule.base_multiplier
            bonus_rate = active_rule.bonus_multiplier
            result.breakdown.append(
                f"Applied Rule: {active_rule.category} ({base_rate}x Base + {bonus_rate}x Bonus)"
            )
            expense.applied_rule_id = active_rule.id
        else:
            result.breakdown.append("No matching rule found. 0.0 points.")
            return result

        raw_base = expense.amount * base_rate
        raw_bonus = expense.amount * bonus_rate
        final_bonus = raw_bonus

        # Apply category-specific caps (bonus only, base flows through)
        if active_rule and active_rule.cap_bucket:
            bucket = active_rule.cap_bucket
            start, end = self._get_period_dates(
                bucket.period, bucket.reset_anchor_month, expense.date
            )
            current_usage = self._get_bucket_usage(bucket.id, start, end)

            remaining_space = max(0.0, bucket.max_points - current_usage)

            if raw_bonus > remaining_space:
                final_bonus = remaining_space
                result.is_capped = True
                result.breakdown.append(
                    f"Bonus Capped by '{bucket.name}': Earned {final_bonus:.1f} (limit hit)"
                )
            else:
                result.breakdown.append(
                    f"Bonus within '{bucket.name}': {raw_bonus:.1f} pts"
                )

        result.base_points = raw_base
        result.bonus_points = final_bonus
        result.total_points = raw_base + final_bonus

        return result

    def _find_best_rule(
        self, card: CreditCard, expense: Expense
    ) -> Optional[RewardRule]:
        """
        Finds the BEST rule (highest multiplier wins).

        Collects ALL matching rules from:
        1. Merchant match
        2. Platform match
        3. Category match
        4. Fallback (Base/All Spends)

        Then filters by tier matching and returns highest multiplier.
        """
        rules = card.reward_rules
        candidates = []

        # Merchant Match
        for r in rules:
            if r.category.lower() == expense.merchant.lower():
                candidates.append(r)

        # Platform Match
        for r in rules:
            if r.category.lower() == expense.platform.lower():
                candidates.append(r)

        # Category Match
        for r in rules:
            if r.category.lower() == expense.category.lower():
                candidates.append(r)

        # Fallback
        for r in rules:
            if r.category in ["Base", "All Spends", "General", "Any"]:
                candidates.append(r)

        # Filter by tier matching
        if candidates:
            tier_matched = [r for r in candidates if self._matches_tier(r, card)]
            if tier_matched:
                candidates = tier_matched
            else:
                candidates = [r for r in candidates if r.match_conditions is None]

        if not candidates:
            return None

        return max(candidates, key=lambda r: r.base_multiplier + r.bonus_multiplier)

    def _matches_tier(self, rule: RewardRule, card: CreditCard) -> bool:
        """
        Check if rule's match_conditions match card's tier_status.
        Universal rules (match_conditions=None) match all cards.
        """
        if rule.match_conditions is None:
            return True

        tier_status = card.tier_status or {}

        return all(
            tier_status.get(key) == value
            for key, value in rule.match_conditions.items()
        )

    def _get_bucket_usage(
        self, bucket_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """
        Sum points earned via rules linked to this bucket.
        Multiple rules can share a bucket (e.g., Dining + Food Delivery → Food Cap).
        """
        statement = select(func.sum(Expense.points_earned)).where(
            Expense.date >= start_date,
            Expense.date <= end_date,
            Expense.applied_rule_id.in_(
                select(RewardRule.id).where(RewardRule.cap_bucket_id == bucket_id)
            ),
        )

        result = self.session.exec(statement).first()
        return result if result else 0.0

    def _get_period_dates(
        self, period: PeriodType, anchor: int, ref_date: datetime
    ) -> Tuple[datetime, datetime]:
        """
        Calculates start/end of the period containing ref_date.

        - STATEMENT_MONTH: Billing cycle (anchor = billing day)
        - QUARTER: Calendar quarters (Jan-Mar, Apr-Jun, Jul-Sep, Oct-Dec)
        - STATEMENT_YEAR: Anniversary year (anchor = activation month)
        - DAILY: Single day
        """
        year = ref_date.year
        month = ref_date.month
        day = ref_date.day

        if period == PeriodType.STATEMENT_MONTH:
            billing_day = anchor
            if day >= billing_day:
                start = datetime(year, month, billing_day)
                if month == 12:
                    end = datetime(year + 1, 1, billing_day) - timedelta(seconds=1)
                else:
                    end = datetime(year, month + 1, billing_day) - timedelta(seconds=1)
            else:
                if month == 1:
                    start = datetime(year - 1, 12, billing_day)
                else:
                    start = datetime(year, month - 1, billing_day)
                end = datetime(year, month, billing_day) - timedelta(seconds=1)
            return start, end

        elif period == PeriodType.QUARTER:
            quarter = (month - 1) // 3
            quarter_start_month = quarter * 3 + 1
            quarter_end_month = quarter_start_month + 2
            start = datetime(year, quarter_start_month, 1)
            _, last_day = monthrange(year, quarter_end_month)
            end = datetime(year, quarter_end_month, last_day, 23, 59, 59)
            return start, end

        elif period == PeriodType.STATEMENT_YEAR:
            anchor_month = anchor if 1 <= anchor <= 12 else 1
            start_year = year if month >= anchor_month else year - 1
            start = datetime(start_year, anchor_month, 1)

            if anchor_month == 1:
                end_year = start_year
                end_month = 12
            else:
                end_year = start_year + 1
                end_month = anchor_month - 1

            _, last_day = monthrange(end_year, end_month)
            end = datetime(end_year, end_month, last_day, 23, 59, 59)
            return start, end

        elif period == PeriodType.DAILY:
            start = datetime(year, month, day, 0, 0, 0)
            end = datetime(year, month, day, 23, 59, 59)
            return start, end

        start = datetime(year, month, 1)
        _, last_day = monthrange(year, month)
        end = datetime(year, month, last_day, 23, 59, 59)
        return start, end


def calculate_rewards(session: Session, expense: Expense) -> RewardResult:
    engine = RewardsEngine(session)
    return engine.calculate_rewards(expense)
