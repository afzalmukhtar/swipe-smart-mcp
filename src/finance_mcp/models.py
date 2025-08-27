from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    credit_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    statement_date: Mapped[int | None] = mapped_column(Integer, nullable=True)

    amount_spent_this_cycle: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_month_rewards: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_quarter_rewards: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_year_rewards: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_spent_this_year: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_lifetime_rewards: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # JSON as text; tools will parse/serialize
    reward_rules: Mapped[str | None] = mapped_column(Text, nullable=True)

    expenses: Mapped[list[Expense]] = relationship(
        back_populates="payment_method", cascade="all, delete-orphan"
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    person: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[PaymentMethod] = relationship(back_populates="expenses")


