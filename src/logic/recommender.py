from dataclasses import dataclass
from typing import List, Optional

from sqlmodel import Session

from src.logic.rewards import RewardsEngine
from src.models import CreditCard, Expense, RewardRule


@dataclass
class CardRecommendation:
    """Result of analyzing a single card for a transaction."""

    card_id: int
    card_name: str
    bank: str

    # Points & Value
    projected_points: float = 0.0
    effective_value: float = 0.0  # points × base_point_value

    # Rule Info
    matched_rule: Optional[str] = None
    rule_breakdown: str = ""

    # Cap Status
    is_capped: bool = False
    cap_headroom_pct: Optional[float] = None  # % remaining before cap hit
    cap_warning: Optional[str] = None

    # Sorting helper
    rank: int = 0


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
        recommendations = recommender.recommend(cards, request)
        best = recommendations[0] if recommendations else None
    """

    def __init__(self, session: Session):
        self.session = session
        self.engine = RewardsEngine(session)

    def recommend(
        self,
        cards: List[CreditCard],
        request: RecommendationRequest,
    ) -> List[CardRecommendation]:
        """
        Analyze all cards and return ranked recommendations.

        Returns cards sorted by effective_value DESC.
        """
        recommendations = []

        for card in cards:
            rec = self._analyze_card(card, request)
            recommendations.append(rec)

        # Sort by effective value (highest first)
        recommendations.sort(key=lambda r: r.effective_value, reverse=True)

        # Assign ranks
        for i, rec in enumerate(recommendations):
            rec.rank = i + 1

        return recommendations

    def get_best_card(
        self,
        cards: List[CreditCard],
        request: RecommendationRequest,
    ) -> Optional[CardRecommendation]:
        """Convenience method to get just the top recommendation."""
        recommendations = self.recommend(cards, request)
        return recommendations[0] if recommendations else None

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
        3. Calculate effective value
        4. Check cap headroom
        """
        rec = CardRecommendation(
            card_id=card.id,
            card_name=card.name,
            bank=card.bank,
        )

        # TODO: Create temp expense and simulate
        # TODO: Calculate effective value
        # TODO: Check cap headroom

        return rec

    def _create_temp_expense(
        self,
        card: CreditCard,
        request: RecommendationRequest,
    ) -> Expense:
        """Create a temporary (non-persisted) expense for simulation."""
        # TODO: Implement
        pass

    def _calculate_cap_headroom(
        self,
        card: CreditCard,
        matched_rule: Optional[RewardRule],
    ) -> Optional[float]:
        """
        Calculate % of cap remaining for the matched rule's bucket.

        Returns None if rule has no cap, otherwise 0-100%.
        """
        # TODO: Implement
        pass


def recommend_card(
    session: Session,
    cards: List[CreditCard],
    amount: float,
    merchant: str,
    category: str,
    platform: str = "Direct",
) -> Optional[CardRecommendation]:
    """
    Convenience function: Find the best card for a transaction.

    Example:
        best = recommend_card(session, user_cards, 5000, "Amazon", "Shopping")
    """
    recommender = CardRecommender(session)
    request = RecommendationRequest(
        amount=amount,
        merchant=merchant,
        category=category,
        platform=platform,
    )
    return recommender.get_best_card(cards, request)
