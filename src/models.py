from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


# --- 1. The Credit Card Model ---
class CreditCard(SQLModel, table=True):
    # Basic Details
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # e.g. "Amex Platinum"
    bank: str  # e.g. "HDFC", "SBI"
    network: str = "Unknown"  # e.g. "Visa", "Mastercard", "Amex"

    # Financial Limits
    monthly_limit: float
    current_balance: float = 0.0

    # Cycle Details
    billing_cycle_start: int
    payment_due_days: int = 20

    # Rewards Details
    rewards_currency: str = "Points"  # e.g. "Points", "Miles", "Cashback"

    # The 'Lazy Value' of a point: What is 1 point worth if you redeem it for
    # Vouchers (Amazon/Flipkart) or Statement Credit or Direct Purchase?
    # Example: If 1000 points = 250 INR Amazon Voucher, then base_point_value = 0.25
    base_point_value: float = 0.25

    # Relationships
    expenses: list["Expense"] = Relationship(back_populates="card")
    reward_rules: list["RewardRule"] = Relationship(back_populates="card")
    redemption_partners: list["RedemptionPartner"] = Relationship(back_populates="card")


# --- 2. Reward Rules (EARNING Side) ---
# "How many points do I GET?"
class RewardRule(SQLModel, table=True):
    # Basic Details
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    category: str  # e.g., "SmartBuy Amazon", "Dining", "Base"

    multiplier: float  # e.g., 5.0 for 5x points, or 0.03 for 3% cashback

    min_spend: float = 0.0  # e.g. "Min transaction 5000"
    monthly_cap: float = 0.0  # e.g. "Max 1000 points per month"

    # Relationships
    card: CreditCard = Relationship(back_populates="reward_rules")


# --- 3. Redemption Partners (BURNING Side) ---
# "What are these points WORTH?"
class RedemptionPartner(SQLModel, table=True):
    # Basic Details
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")

    partner_name: str  # e.g., "Marriott", "Singapore Airlines", "Amazon Voucher"
    transfer_ratio: float  # e.g., 2.0 (1 Bank Point = 2 Partner Points)
    estimated_value: float  # e.g., 0.50 (Value of 1 Partner Point in INR)
    # Explanation:
    # If Axis Edge Mile -> Marriott is 1:2
    # transfer_ratio = 2.0
    # estimated_value of 1 Marriott point = ~0.50 INR
    # Total Value = 2.0 * 0.50 = 1.00 INR per Axis point.

    # Relationships
    card: CreditCard = Relationship(back_populates="redemption_partners")


# --- 4. The Expense Model ---
class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    merchant: str  # e.g. "Amazon"

    # This matches RewardRule.category
    # (e.g. if you bought via SmartBuy, this should be "SmartBuy Amazon")
    category: str

    # Captures the 'Portal' nuance
    platform: str = "Direct"  # e.g. "SmartBuy", "Gyftr", "Cred", "Direct"

    date: datetime = Field(default_factory=datetime.now)
    card_id: Optional[int] = Field(default=None, foreign_key="creditcard.id")
    card: Optional[CreditCard] = Relationship(back_populates="expenses")
