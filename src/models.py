from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship


# --- 0. Enums for Time Periods ---
class PeriodType(str, Enum):
    DAILY = "daily"
    STATEMENT_CYCLE = "statement_cycle"


# --- 1. The Credit Card Model ---
class CreditCard(SQLModel, table=True):
    """Represents a credit card configuration."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    bank: str
    network: str = "Unknown"

    # Financial Limits
    monthly_limit: float
    current_balance: float = 0.0

    # Cycle Details
    billing_cycle_start: int  # Day of month (e.g., 15)
    payment_due_days: int = 20

    # Reward Basics
    rewards_currency: str = "Points"
    base_point_value: float = 0.25

    # Relationships
    expenses: List["Expense"] = Relationship(back_populates="card")
    redemption_partners: List["RedemptionPartner"] = Relationship(back_populates="card")
    cap_buckets: List["CapBucket"] = Relationship(back_populates="card")
    reward_rules: List["RewardRule"] = Relationship(back_populates="card")


# --- 2. The Cap Bucket (The "Police") ---
class CapBucket(SQLModel, table=True):
    """
    Represents a limit container.
    Example: "SmartBuy Cap" (Max 4000 pts per Statement Cycle)
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    name: str  # e.g. "SmartBuy Daily", "Partner Milestone"
    max_points: float  # e.g. 2000.0
    period: PeriodType  # DAILY or STATEMENT_CYCLE

    # Tracking State
    current_usage: float = 0.0
    last_reset_date: date = Field(default_factory=date.today)

    # Relationships
    card: CreditCard = Relationship(back_populates="cap_buckets")
    rules: List["RewardRule"] = Relationship(back_populates="rules")


# --- 3. Reward Rules (The "Logic") ---
class RewardRule(SQLModel, table=True):
    """
    Defines how points are calculated.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    category: str  # e.g., "SmartBuy Amazon", "Dining"

    # The Math
    base_multiplier: float
    bonus_multiplier: float

    # Constraints
    min_spend: float = 0.0

    # Link to a shared Bucket
    cap_bucket_id: Optional[int] = Field(default=None, foreign_key="capbucket.id")

    # Relationships
    card: CreditCard = Relationship(back_populates="reward_rules")
    cap_bucket: Optional[CapBucket] = Relationship(
        back_populates="rules"
    )  # Changed back_populates to "rules"


# --- 4. Redemption Partners (The "Value") ---
class RedemptionPartner(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    partner_name: str
    transfer_ratio: float
    estimated_value: float

    card: CreditCard = Relationship(back_populates="redemption_partners")


# --- 5. The Expense Model ---
class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    merchant: str
    category: str
    platform: str = "Direct"

    date: datetime = Field(default_factory=datetime.now)

    card_id: Optional[int] = Field(default=None, foreign_key="creditcard.id")
    card: Optional[CreditCard] = Relationship(back_populates="expenses")
