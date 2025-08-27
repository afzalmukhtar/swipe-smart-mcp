from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .database import get_db_session
from .models import Expense, PaymentMethod


@dataclass
class RewardOutcome:
    earned_rewards: float
    applied_rate: float
    applied_rule: str | None


def _is_new_month(d: date) -> bool:
    return d.day == 1


def _is_new_quarter(d: date) -> bool:
    return d.month in {1, 4, 7, 10} and d.day == 1


def _is_new_year(d: date) -> bool:
    return d.month == 1 and d.day == 1


def _parse_reward_rules(reward_rules_text: str | None) -> Dict[str, Any]:
    if not reward_rules_text:
        return {}
    try:
        return json.loads(reward_rules_text)
    except Exception:
        return {}


def _calculate_transaction_rewards(
    amount: float, category: str, rules_text: str | None
) -> RewardOutcome:
    rules = _parse_reward_rules(rules_text)
    # Basic structure:
    # {
    #   "base_rate": 0.01,
    #   "category_multipliers": {"grocery": 0.05},
    #   "soft_caps": [{"category": "grocery", "threshold": 5000, "post_rate": 0.01}],
    #   "hard_caps": [{"category": "grocery", "threshold": 10000}]
    # }
    base_rate = float(rules.get("base_rate", 0.0))
    category_multipliers = rules.get("category_multipliers", {})
    applied_rate = float(category_multipliers.get(category, base_rate))

    # For simplicity here, we do not store category-wise year-to-date. We apply caps only per-transaction by thresholding amount.
    applied_rule_label: str | None = None

    # Hard cap: if this single amount exceeds threshold, assume no rewards above threshold; here we simplify to zero rewards if over hard cap amount
    for cap in rules.get("hard_caps", []) or []:
        if cap.get("category") == category and amount >= float(cap.get("threshold", 0)):
            return RewardOutcome(earned_rewards=0.0, applied_rate=0.0, applied_rule="hard_cap")

    # Soft cap: if amount exceeds threshold, only threshold portion gets category rate; remaining gets base rate
    for cap in rules.get("soft_caps", []) or []:
        if cap.get("category") == category:
            threshold = float(cap.get("threshold", 0))
            post_rate = float(cap.get("post_rate", base_rate))
            if amount > threshold > 0:
                rewards = threshold * applied_rate + (amount - threshold) * post_rate
                return RewardOutcome(earned_rewards=rewards, applied_rate=applied_rate, applied_rule="soft_cap")

    rewards = amount * applied_rate
    return RewardOutcome(earned_rewards=rewards, applied_rate=applied_rate, applied_rule=applied_rule_label)


def _apply_period_resets(payment_method: PaymentMethod, txn_date: date) -> None:
    if _is_new_month(txn_date):
        payment_method.current_month_rewards = 0.0
        payment_method.amount_spent_this_cycle = 0.0
    if _is_new_quarter(txn_date):
        payment_method.current_quarter_rewards = 0.0
    if _is_new_year(txn_date):
        payment_method.current_year_rewards = 0.0
        payment_method.total_spent_this_year = 0.0


def add_expense(
    *,
    amount: float,
    description: str,
    category: str,
    payment_source: str,
    person: str,
    date_str: str | None = None,
) -> Dict[str, Any]:
    txn_date = (
        datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    )

    for db in get_db_session():
        session: Session = db
        pm = session.scalar(select(PaymentMethod).where(PaymentMethod.name == payment_source))
        if pm is None:
            return {"status": "error", "message": f"Payment method '{payment_source}' not found"}

        _apply_period_resets(pm, txn_date)

        outcome = _calculate_transaction_rewards(amount, category, pm.reward_rules)

        pm.amount_spent_this_cycle += amount
        pm.current_month_rewards += outcome.earned_rewards
        pm.current_quarter_rewards += outcome.earned_rewards
        pm.current_year_rewards += outcome.earned_rewards
        pm.total_spent_this_year += amount
        pm.total_lifetime_rewards += outcome.earned_rewards

        expense = Expense(
            amount=amount,
            description=description,
            category=category,
            person=person,
            date=txn_date,
            payment_method=pm,
        )
        session.add(expense)
        session.flush()

        return {
            "status": "success",
            "message": "Expense added",
            "expense_id": expense.id,
            "rewards_earned": outcome.earned_rewards,
            "applied_rate": outcome.applied_rate,
            "applied_rule": outcome.applied_rule,
        }


def get_expenses(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    payment_source: str | None = None,
    person: str | None = None,
) -> list[Dict[str, Any]]:
    start: date | None = (
        datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    )
    end: date | None = (
        datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    )

    for db in get_db_session():
        session: Session = db
        stmt = select(Expense).join(Expense.payment_method)
        filters = []
        if start:
            filters.append(Expense.date >= start)
        if end:
            filters.append(Expense.date <= end)
        if category:
            filters.append(Expense.category == category)
        if payment_source:
            filters.append(PaymentMethod.name == payment_source)
        if person:
            filters.append(Expense.person == person)
        if filters:
            stmt = stmt.where(and_(*filters))
        rows = session.scalars(stmt.order_by(Expense.date.desc(), Expense.id.desc())).all()
        return [
            {
                "id": r.id,
                "amount": r.amount,
                "description": r.description,
                "category": r.category,
                "person": r.person,
                "date": r.date.isoformat(),
                "payment_source": r.payment_method.name,
            }
            for r in rows
        ]


def edit_expense(
    *,
    expense_id: int,
    amount: float | None = None,
    description: str | None = None,
    category: str | None = None,
    payment_source: str | None = None,
    person: str | None = None,
    date_str: str | None = None,
) -> Dict[str, Any]:
    for db in get_db_session():
        session: Session = db
        expense = session.get(Expense, expense_id)
        if not expense:
            return {"status": "error", "message": f"Expense {expense_id} not found"}
        if amount is not None:
            expense.amount = amount
        if description is not None:
            expense.description = description
        if category is not None:
            expense.category = category
        if payment_source is not None:
            pm = session.scalar(select(PaymentMethod).where(PaymentMethod.name == payment_source))
            if not pm:
                return {"status": "error", "message": f"Payment method '{payment_source}' not found"}
            expense.payment_method = pm
        if person is not None:
            expense.person = person
        if date_str is not None:
            expense.date = datetime.strptime(date_str, "%Y-%m-%d").date()
        session.flush()
        return {"status": "success", "message": "Expense updated", "expense_id": expense.id}


def add_payment_method(
    *,
    name: str,
    type: str,
    credit_limit: float | None = None,
    statement_date: int | None = None,
    reward_rules: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    for db in get_db_session():
        session: Session = db
        if session.scalar(select(PaymentMethod).where(PaymentMethod.name == name)):
            return {"status": "error", "message": f"Payment method '{name}' already exists"}
        pm = PaymentMethod(
            name=name,
            type=type,
            credit_limit=credit_limit,
            statement_date=statement_date,
            reward_rules=json.dumps(reward_rules) if reward_rules is not None else None,
        )
        session.add(pm)
        session.flush()
        return {"status": "success", "message": "Payment method added", "id": pm.id}


def list_payment_methods() -> list[Dict[str, Any]]:
    for db in get_db_session():
        session: Session = db
        rows = session.scalars(select(PaymentMethod).order_by(PaymentMethod.name.asc())).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "credit_limit": r.credit_limit,
                "statement_date": r.statement_date,
                "amount_spent_this_cycle": r.amount_spent_this_cycle,
                "current_month_rewards": r.current_month_rewards,
                "current_quarter_rewards": r.current_quarter_rewards,
                "current_year_rewards": r.current_year_rewards,
                "total_spent_this_year": r.total_spent_this_year,
                "total_lifetime_rewards": r.total_lifetime_rewards,
                "reward_rules": json.loads(r.reward_rules) if r.reward_rules else None,
            }
            for r in rows
        ]


def remove_payment_method(*, name: str) -> Dict[str, Any]:
    for db in get_db_session():
        session: Session = db
        pm = session.scalar(select(PaymentMethod).where(PaymentMethod.name == name))
        if not pm:
            return {"status": "error", "message": f"Payment method '{name}' not found"}
        session.delete(pm)
        session.flush()
        return {"status": "success", "message": "Payment method removed"}


def pay_credit_card_bill(*, name: str, amount_paid: float) -> Dict[str, Any]:
    # Simplified outstanding as amount_spent_this_cycle; paying reduces it
    for db in get_db_session():
        session: Session = db
        pm = session.scalar(select(PaymentMethod).where(PaymentMethod.name == name))
        if not pm:
            return {"status": "error", "message": f"Payment method '{name}' not found"}
        pm.amount_spent_this_cycle = max(0.0, pm.amount_spent_this_cycle - amount_paid)
        session.flush()
        return {
            "status": "success",
            "message": "Payment recorded",
            "outstanding_amount": pm.amount_spent_this_cycle,
        }


def get_best_card_for_purchase(*, amount: float, category: str, merchant: str | None = None) -> list[Dict[str, Any]]:
    candidates: list[tuple[str, float, float]] = []  # (name, expected_rewards, rate)
    for db in get_db_session():
        session: Session = db
        rows = session.scalars(select(PaymentMethod)).all()
        for pm in rows:
            outcome = _calculate_transaction_rewards(amount, category, pm.reward_rules)
            candidates.append((pm.name, outcome.earned_rewards, outcome.applied_rate))
        ranked = sorted(candidates, key=lambda x: x[1], reverse=True)
        return [
            {"payment_source": name, "expected_rewards": rewards, "applied_rate": rate}
            for name, rewards, rate in ranked
        ]


def get_payment_method_summary(*, name: str | None = None) -> list[Dict[str, Any]]:
    for db in get_db_session():
        session: Session = db
        q = select(PaymentMethod)
        if name:
            q = q.where(PaymentMethod.name == name)
        rows = session.scalars(q.order_by(PaymentMethod.name.asc())).all()
        return [
            {
                "name": r.name,
                "type": r.type,
                "credit_limit": r.credit_limit,
                "statement_date": r.statement_date,
                "amount_spent_this_cycle": r.amount_spent_this_cycle,
                "current_month_rewards": r.current_month_rewards,
                "current_quarter_rewards": r.current_quarter_rewards,
                "current_year_rewards": r.current_year_rewards,
                "total_spent_this_year": r.total_spent_this_year,
                "total_lifetime_rewards": r.total_lifetime_rewards,
            }
            for r in rows
        ]


