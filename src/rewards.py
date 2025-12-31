from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
import json
from pathlib import Path

from sqlmodel import Session, func, select

# Import Models
from src.models import (
    BucketScope,
    CapBucket,
    CapType,
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
    """The Gauntlet: Calculates rewards through a series of gates."""

    def __init__(self, session: Session):
        self.session = session
        self.GLOBAL_EXCLUSIONS = self._load_exclusions()

    def _load_exclusions(self) -> List[str]:
        """Loads excluded categories from data/categories.json."""
        try:
            # Assume data/categories.json is relative to project root
            # We are in src/rewards.py. Parent of src is root.
            root_dir = Path(__file__).resolve().parent.parent
            json_path = root_dir / "data" / "categories.json"

            with open(json_path, "r") as f:
                data = json.load(f)

            return [
                cat["name"]
                for cat in data.get("categories", [])
                if cat.get("excluded_from_rewards", False)
            ]
        except Exception as e:
            # Fallback if file missing or error
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
        Main entry point.
        Orchestrates the flow: Global Cap -> Exclusions -> Waterfall.
        """
        if not expense.card:
            return RewardResult(breakdown=["No card linked to transaction."])

        card = expense.card
        result = RewardResult()

        # --- GATE 1: Exclusion Logic ---
        # "Is this category banned by default?"
        # If this passes user sees "Excluded" instead of "Cap Hit" for banned items.
        is_excluded, override_rule = self._check_exclusions(card, expense)

        if is_excluded and not override_rule:
            result.breakdown.append(
                f"Category '{expense.category}' is globally excluded."
            )
            return result  # QUICK EXIT (0 points)

        # --- GATE 2: Global Cap Check ---
        # "Stop earning if you've hit the monthly total limit on the card"
        global_cap_hit, cap_msg = self._check_global_caps(card, expense)
        if global_cap_hit:
            result.breakdown.append(cap_msg)
            result.is_capped = True
            return result  # QUICK EXIT

        # If excluded BUT allowed (e.g. HDFC on Insurance), we continue to Waterfall
        # but ensure we ONLY use that specific rule.

        # --- GATE 3: Calculate Rewards Using Waterfall Logic ---
        return self._calculate_waterfall(card, expense, override_rule)

    # Priority order for cap checking: wider scope first
    PERIOD_PRIORITY = {
        PeriodType.STATEMENT_YEAR: 1,   # Check annual first (widest)
        PeriodType.QUARTER: 2,          # Then quarterly
        PeriodType.STATEMENT_MONTH: 3,  # Then monthly
        PeriodType.DAILY: 4,            # Then daily (narrowest)
    }

    def _check_global_caps(
        self, card: CreditCard, expense: Expense
    ) -> Tuple[bool, str]:
        """
        Checks if the card has a GLOBAL scope bucket that is full.
        Evaluates caps in priority order: Annual → Quarterly → Monthly → Daily
        Returns: (is_hit, message)
        """
        # Find global buckets for this card
        global_buckets = [
            b for b in card.cap_buckets if b.bucket_scope == BucketScope.GLOBAL
        ]

        # Sort by priority: Annual → Quarterly → Monthly → Daily
        sorted_buckets = sorted(
            global_buckets,
            key=lambda b: self.PERIOD_PRIORITY.get(b.period, 99)
        )

        for bucket in sorted_buckets:
            start_date, end_date = self._get_period_dates(
                bucket.period, bucket.reset_anchor_month, expense.date
            )

            # Query usage
            if bucket.bucket_scope == BucketScope.GLOBAL:
                current_points = self._get_global_usage(card.id, start_date, end_date)
            else:
                current_points = self._get_bucket_usage(bucket.id, start_date, end_date)

            # Check if adding this will breach
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
        Checks if category is excluded.
        Returns: (is_excluded_category, specific_override_rule_if_any)
        """
        if expense.category not in self.GLOBAL_EXCLUSIONS:
            return False, None

        # It IS an excluded category. Check if card has a rule for it.
        # Logic: If a rule exists for "Rent", it overrides the global "Rent" ban.
        query = select(RewardRule).where(
            RewardRule.card_id == card.id, RewardRule.category == expense.category
        )
        rule = self.session.exec(query).first()

        if rule:
            return True, rule  # Yes excluded, but WE HAVE A PASS

        return True, None  # Excluded and no pass

    def _calculate_waterfall(
        self,
        card: CreditCard,
        expense: Expense,
        override_rule: Optional[RewardRule] = None,
    ) -> RewardResult:
        """
        Calculates Base + Bonus, then applies Specific Caps.
        """
        result = RewardResult()

        # 1. Identify Rule
        # If we have an override (from exclusion check), use it.
        # Else, find best matching rule.
        active_rule = override_rule
        if not active_rule:
            active_rule = self._find_best_rule(card, expense)

        # 2. Calculate Raw Points
        # If no specific rule found, we need a "Default/Base" behavior.
        # Usually cards have a "Base Rate" stored on the card itself or a "All Spends" rule.
        # Let's assume Card.base_point_value is value, not rate.
        # We need a fallback "Base Rule" effectively.
        # For this design, if no rule matches, we assume generic base earning usually defined
        # as a rule with category="All Spends" or implied logic.
        # Let's assume if no rule, 0 points? Or default base?
        # Let's assume we construct a virtual rule from defaults if none found.

        base_rate = 0.0
        bonus_rate = 0.0

        if active_rule:
            base_rate = active_rule.base_multiplier
            bonus_rate = active_rule.bonus_multiplier
            result.breakdown.append(
                f"Applied Rule: {active_rule.category} ({base_rate}x Base + {bonus_rate}x Bonus)"
            )

            # Record which rule triggered logic
            expense.applied_rule_id = active_rule.id
        else:
            # Fallback to generic 1x or 0x? Let's check Card defaults.
            # Many cards have implied base rate. Let's assume 0 for safety unless a "Base" rule exists.
            # Actually, `get_card_definitions` in seed.py adds explicit rules for categories.
            # Let's try to find an "All Spends" or "Base" rule?
            # For now, if no rule matches, return 0 breakdown.
            result.breakdown.append("No matching rule found. 0.0 points.")
            return result

        raw_base = expense.amount * base_rate
        raw_bonus = expense.amount * bonus_rate

        # 3. Apply Multiplier Caps (The "Squeeze")
        # Base points are RARELY capped. Bonus points are OFTEN capped.

        final_bonus = raw_bonus

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
        Finds the most specific rule.
        Priority: Merchant > Platform > Best of (Category, Condition, Fallback).
        """
        # We can do this in Python since rules list is small per card.
        rules = card.reward_rules

        # 1. Merchant Match (Highest Priority - Explicit override)
        for r in rules:
            if r.category.lower() == expense.merchant.lower():
                return r

        # 2. Platform Match
        for r in rules:
            if r.category.lower() == expense.platform.lower():
                return r

        candidates = []

        # 3. Category Match
        for r in rules:
            if r.category.lower() == expense.category.lower():
                candidates.append(r)

        # 4. Condition Match
        for r in rules:
            if r.condition_expression:
                try:
                    # Prepare context
                    ctx = {
                        "expense": expense,
                        "card": card,
                        "is_prime": card.meta_data.get("is_prime", False)
                        if card.meta_data
                        else False,
                    }
                    if eval(r.condition_expression, ctx):
                        candidates.append(r)
                except Exception:
                    continue

        # 5. Fallback Match (Only if no specific category/condition match?)
        # Actually, sometimes Base is better than nothing, but usually Base is low.
        # But if we have "All Spends" = 1%, and "Shopping" = 0.5% (unlikely), we'd want 1%.
        for r in rules:
            if r.category in ["Base", "All Spends", "General", "Any"]:
                # If a rule has a condition, it's a Conditional Rule (handled in Step 4).
                # Fallbacks must be unconditional.
                if r.condition_expression:
                    continue
                candidates.append(r)

        if not candidates:
            return None

        # Return the rule with the highest Total Multiplier (Base + Bonus)
        # Tie-breaker: Specificity (Category > Condition > Base) - tricky to encode.
        # Let's just trust the value.
        return max(candidates, key=lambda r: r.base_multiplier + r.bonus_multiplier)

    def _get_bucket_usage(
        self, bucket_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        """Sum points earned in this bucket for the period."""
        # Join with RewardRule to filter by bucket
        # Note: We need to sum the points from expenses linked to rules that link to this bucket.
        # Logic:
        # Expenses -> linked to Rule (applied_rule_id) -> linked to Bucket (cap_bucket_id)

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
        """Calculates the start and end of the period containing ref_date."""
        year = ref_date.year
        month = ref_date.month
        day = ref_date.day

        if period == PeriodType.STATEMENT_MONTH:
            # Anchor is billing day.
            # If transaction is ON or AFTER anchor, cycle is [ThisMonth-Anchor, NextMonth-Anchor-1]
            # If before, cycle is [PrevMonth-Anchor, ThisMonth-Anchor-1]
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
            # Calendar quarters: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
            quarter = (month - 1) // 3  # 0, 1, 2, 3
            quarter_start_month = quarter * 3 + 1  # 1, 4, 7, 10
            quarter_end_month = quarter_start_month + 2  # 3, 6, 9, 12
            
            start = datetime(year, quarter_start_month, 1)
            _, last_day = monthrange(year, quarter_end_month)
            end = datetime(year, quarter_end_month, last_day, 23, 59, 59)
            return start, end

        elif period == PeriodType.STATEMENT_YEAR:
            # Anniversary year based on reset_anchor_month (card activation month)
            # e.g., anchor=3 (March): Mar 1 to Feb 28/29 of next year
            anchor_month = anchor if 1 <= anchor <= 12 else 1
            
            if month >= anchor_month:
                # We're in the current anniversary year
                start_year = year
            else:
                # We're in the previous anniversary year (before anchor month)
                start_year = year - 1
            
            start = datetime(start_year, anchor_month, 1)
            
            # End is last day of month before anchor_month in next year
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

        # Fallback (should not reach here)
        start = datetime(year, month, 1)
        _, last_day = monthrange(year, month)
        end = datetime(year, month, last_day, 23, 59, 59)
        return start, end


# --- Singleton Helper for Server ---
def calculate_rewards(session: Session, expense: Expense) -> RewardResult:
    engine = RewardsEngine(session)
    return engine.calculate_rewards(expense)
