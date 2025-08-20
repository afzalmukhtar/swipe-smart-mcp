"""Data models for the Financial MCP Server."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


class PaymentMethod(str, Enum):
    """Payment method enum."""

    CASH = "cash"
    CREDIT_CARD = "credit-card"
    DEBIT_CARD = "debit-card"
    UPI = "upi"
    NET_BANKING = "net-banking"
    WALLET = "wallet"


class Expense(BaseModel):
    """Expense model."""

    id: int | None = None
    amount: Decimal = Field(..., gt=0)
    description: str
    category: str
    payment_method: PaymentMethod
    credit_card: str | None = None
    payment_portal: str | None = None
    person: str
    date: date
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @validator("category", always=True)
    def auto_categorize(cls, v, values):
        """Auto-categorize based on description if category not provided."""
        if v:
            return v

        description = values.get("description", "").lower()

        # Auto-categorization rules
        if any(
            word in description
            for word in [
                "food",
                "restaurant",
                "dining",
                "meal",
                "lunch",
                "dinner",
                "breakfast",
            ]
        ):
            return "Dining"
        elif any(
            word in description
            for word in ["grocery", "supermarket", "vegetables", "fruits", "milk"]
        ):
            return "Groceries"
        elif any(word in description for word in ["gas", "fuel", "petrol", "diesel"]):
            return "Gas"
        elif any(
            word in description
            for word in ["transport", "uber", "taxi", "bus", "train", "metro"]
        ):
            return "Transportation"
        elif any(
            word in description
            for word in ["movie", "entertainment", "game", "concert"]
        ):
            return "Entertainment"
        elif any(
            word in description
            for word in ["medical", "doctor", "pharmacy", "medicine", "hospital"]
        ):
            return "Healthcare"
        elif any(
            word in description
            for word in ["shopping", "clothes", "amazon", "flipkart"]
        ):
            return "Shopping"
        elif any(
            word in description
            for word in ["bill", "electricity", "water", "internet", "phone"]
        ):
            return "Bills"
        else:
            return "Other"


class CreditCard(BaseModel):
    """Credit card model."""

    id: int | None = None
    name: str
    bank: str
    reward_categories: dict[str, float]  # category -> reward rate percentage
    annual_fee: Decimal = Field(default=Decimal("0"))
    bonus_categories: dict[str, float] = Field(
        default_factory=dict
    )  # temporary/quarterly bonuses
    is_active: bool = Field(default=True)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExpenseFilter(BaseModel):
    """Filter parameters for expense queries."""

    limit: int = Field(default=10, ge=1, le=1000)
    category: str | None = None
    payment_method: PaymentMethod | None = None
    credit_card: str | None = None
    person: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    month: str | None = None  # YYYY-MM format

    @validator("month")
    def validate_month_format(cls, v):
        """Validate month format."""
        if v:
            try:
                datetime.strptime(v, "%Y-%m")
            except ValueError:
                raise ValueError("Month must be in YYYY-MM format")
        return v


class FinancialSummary(BaseModel):
    """Financial summary model."""

    total_spending: Decimal
    transaction_count: int
    average_transaction: Decimal
    top_categories: list[tuple]  # (category, amount)
    payment_methods: list[tuple]  # (method, amount)
    credit_cards: list[tuple]  # (card, amount)
    total_rewards: Decimal | None = None
    period: str
    start_date: date
    end_date: date


class RewardCalculation(BaseModel):
    """Reward calculation result."""

    amount: Decimal
    type: str  # 'cashback', 'points', 'miles'
    rate: float  # percentage rate used
    category: str
    credit_card: str


class Configuration(BaseModel):
    """Application configuration."""

    currency: str = Field(default="USD")
    default_person: str | None = None
    frequent_categories: list[str] = Field(default_factory=list)
    frequent_portals: list[str] = Field(default_factory=list)
    auto_categorization: bool = Field(default=True)
    backup_frequency: str = Field(default="weekly")  # daily, weekly, monthly
    data_retention_months: int = Field(default=24)


class ExportFormat(str, Enum):
    """Export format enum."""

    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"


class ExportRequest(BaseModel):
    """Export request model."""

    format: ExportFormat
    output_path: str
    start_date: date | None = None
    end_date: date | None = None
    categories: list[str] | None = None
    payment_methods: list[PaymentMethod] | None = None
    credit_cards: list[str] | None = None
    include_rewards: bool = Field(default=True)


class SpendingAnalysis(BaseModel):
    """Spending analysis result."""

    analysis_type: str
    period: str
    summary: str
    insights: list[str]
    data: dict[str, Any]
    recommendations: list[str] = Field(default_factory=list)
