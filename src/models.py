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

    # --- RELATIONSHIPS (With Cascade Deletes) ---
    # These settings ensure that when you delete a Card, all its
    # dependent data (Rules, History, Limits) is automatically cleaned up.

    expenses: List["Expense"] = Relationship(
        back_populates="card", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    redemption_partners: List["RedemptionPartner"] = Relationship(
        back_populates="card", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    cap_buckets: List["CapBucket"] = Relationship(
        back_populates="card", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    reward_rules: List["RewardRule"] = Relationship(
        back_populates="card", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


# --- 2. The Cap Bucket (The "Police") ---
class CapBucket(SQLModel, table=True):
    """
    Represents a limit container (e.g., 'SmartBuy Monthly Cap').
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    name: str
    max_points: float
    period: PeriodType

    # Tracking State
    current_usage: float = 0.0
    last_reset_date: date = Field(default_factory=date.today)

    # Relationships
    card: CreditCard = Relationship(back_populates="cap_buckets")

    # Note: We do NOT cascade delete here. If a bucket is deleted,
    # the rule simply loses its link (becomes Uncapped), which is safer.
    rules: List["RewardRule"] = Relationship(back_populates="cap_bucket")


# --- 3. Reward Rules (The "Logic") ---
class RewardRule(SQLModel, table=True):
    """
    Defines how points are calculated (Base + Bonus).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    category: str

    # The Math
    base_multiplier: float
    bonus_multiplier: float

    # Constraints
    min_spend: float = 0.0

    # Link to a shared Bucket (Optional)
    cap_bucket_id: Optional[int] = Field(default=None, foreign_key="capbucket.id")

    # Relationships
    card: CreditCard = Relationship(back_populates="reward_rules")
    cap_bucket: Optional[CapBucket] = Relationship(back_populates="rules")


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

    # Stores the result of our calculation
    points_earned: float = 0.0

    date: datetime = Field(default_factory=datetime.now)

    card_id: Optional[int] = Field(default=None, foreign_key="creditcard.id")
    card: Optional[CreditCard] = Relationship(back_populates="expenses")
