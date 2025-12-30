from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import JSON, Column

# --- 0. Enums for Logic & Time ---


class PeriodType(str, Enum):
    """Defines when a limit resets."""

    DAILY = "daily"
    STATEMENT_CYCLE = "statement_cycle"  # Resets on billing date
    CALENDAR_MONTH = "calendar_month"  # Resets on 1st of month
    QUARTERLY = "quarterly"  # Jan-Mar, Apr-Jun, etc.
    ANNUAL = "annual"  # Yearly based on card anniversary


class CapType(str, Enum):
    """Defines what happens when the limit is hit."""

    HARD_CAP = "hard_cap"  # Stop earning EVERYTHING (0 points)
    HEADER = "header"
    BODY = "body"


class BucketScope(str, Enum):
    """Defines the scope of the cap."""

    GLOBAL = "global"  # Applies to total earnings on the card
    CATEGORY = "category"  # Applies to specific categories/rules


# --- 1. The Credit Card Model ---
class CreditCard(SQLModel, table=True):
    """
    Represents a credit card configuration.
    Now supports 'Metadata' to handle state (e.g., Prime Member).
    """

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

    # --- NEW: Dynamic State (The "Toggle" Switch) ---
    # Stores flags like {"is_prime": true, "is_swiggy_one": false}
    # We use SQLAlchemy's JSON column type for flexibility
    meta_data: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    # --- RELATIONSHIPS (With Cascade Deletes) ---
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
    Now supports reset frequencies and cap types.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    name: str
    max_points: float

    # --- NEW: Cap Logic ---
    period: PeriodType = Field(default=PeriodType.STATEMENT_CYCLE)
    period: PeriodType = Field(default=PeriodType.STATEMENT_CYCLE)
    cap_type: CapType = Field(default=CapType.HARD_CAP)
    bucket_scope: BucketScope = Field(default=BucketScope.CATEGORY)

    # For Annual/Quarterly caps, we might need a specific start month
    # e.g., 1 = January (Calendar Year), 4 = April (Fiscal Year)
    reset_anchor_month: int = Field(default=1)

    # Relationships
    card: CreditCard = Relationship(back_populates="cap_buckets")

    # If a bucket is deleted, the rule simply becomes "Uncapped" (safe)
    rules: List["RewardRule"] = Relationship(back_populates="cap_bucket")


# --- 3. Reward Rules (The "Logic") ---
class RewardRule(SQLModel, table=True):
    """
    Defines how points are calculated (Base + Bonus).
    Now supports Conditional Logic (Prime vs Non-Prime).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    category: str  # Merchant name or Category name

    # The Math
    base_multiplier: float  # e.g., 0.01 (1%)
    bonus_multiplier: float  # e.g., 0.04 (4%)

    # Constraints
    min_spend: float = 0.0

    # --- NEW: Conditional Logic ---
    # e.g., "is_prime == True". If None, applies to everyone.
    condition_expression: Optional[str] = Field(default=None)

    # Link to a shared Bucket (Optional - If None, it's UNLIMITED)
    cap_bucket_id: Optional[int] = Field(default=None, foreign_key="capbucket.id")

    # Relationships
    card: CreditCard = Relationship(back_populates="reward_rules")
    cap_bucket: Optional[CapBucket] = Relationship(back_populates="rules")


# --- 4. Redemption Partners (The "Value") ---
class RedemptionPartner(SQLModel, table=True):
    """Defines transfer partners (e.g., HDFC -> Singapore Airlines)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    partner_name: str
    transfer_ratio: float
    estimated_value: float

    card: CreditCard = Relationship(back_populates="redemption_partners")


# --- 5. The Expense Model ---
class Expense(SQLModel, table=True):
    """Represents a single financial transaction."""

    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    merchant: str
    category: str
    platform: str = "Direct"
    is_online: Optional[bool] = Field(default=None)  # New flag for Online/Offline

    # Stores the result of our calculation
    points_earned: float = 0.0

    # Useful to know WHICH rule triggered this reward (for debugging)
    applied_rule_id: Optional[int] = Field(default=None)

    date: datetime = Field(default_factory=datetime.now)

    card_id: Optional[int] = Field(default=None, foreign_key="creditcard.id")
    card: Optional[CreditCard] = Relationship(back_populates="expenses")

    # Debugging / User Info
    notes: Optional[str] = None
