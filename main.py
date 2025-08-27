from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from src.finance_mcp import tools as finance_tools
from src.finance_mcp.database import init_db

app = FastAPI(title="Personal Finance MCP Server", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    init_db()


class AddExpenseRequest(BaseModel):
    amount: float
    description: str
    category: str
    payment_source: str
    person: str
    date: str | None = Field(default=None, alias="date")


@app.post("/tools/add_expense")
def http_add_expense(payload: AddExpenseRequest):
    return finance_tools.add_expense(
        amount=payload.amount,
        description=payload.description,
        category=payload.category,
        payment_source=payload.payment_source,
        person=payload.person,
        date_str=payload.date,
    )


class GetExpensesQuery(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    category: str | None = None
    payment_source: str | None = None
    person: str | None = None


@app.get("/tools/get_expenses")
def http_get_expenses(q: GetExpensesQuery = Depends()):
    return finance_tools.get_expenses(
        start_date=q.start_date,
        end_date=q.end_date,
        category=q.category,
        payment_source=q.payment_source,
        person=q.person,
    )


class EditExpenseRequest(BaseModel):
    expense_id: int
    amount: float | None = None
    description: str | None = None
    category: str | None = None
    payment_source: str | None = None
    person: str | None = None
    date: str | None = None


@app.post("/tools/edit_expense")
def http_edit_expense(payload: EditExpenseRequest):
    return finance_tools.edit_expense(
        expense_id=payload.expense_id,
        amount=payload.amount,
        description=payload.description,
        category=payload.category,
        payment_source=payload.payment_source,
        person=payload.person,
        date_str=payload.date,
    )


class AddPaymentMethodRequest(BaseModel):
    name: str
    type: str
    credit_limit: float | None = None
    statement_date: int | None = None
    reward_rules: dict[str, Any] | None = None


@app.post("/tools/add_payment_method")
def http_add_payment_method(payload: AddPaymentMethodRequest):
    return finance_tools.add_payment_method(
        name=payload.name,
        type=payload.type,
        credit_limit=payload.credit_limit,
        statement_date=payload.statement_date,
        reward_rules=payload.reward_rules,
    )


@app.get("/tools/list_payment_methods")
def http_list_payment_methods():
    return finance_tools.list_payment_methods()


class RemovePaymentMethodRequest(BaseModel):
    name: str


@app.post("/tools/remove_payment_method")
def http_remove_payment_method(payload: RemovePaymentMethodRequest):
    return finance_tools.remove_payment_method(name=payload.name)


class PayCreditCardBillRequest(BaseModel):
    name: str
    amount_paid: float


@app.post("/tools/pay_credit_card_bill")
def http_pay_credit_card_bill(payload: PayCreditCardBillRequest):
    return finance_tools.pay_credit_card_bill(name=payload.name, amount_paid=payload.amount_paid)


class BestCardQuery(BaseModel):
    amount: float
    category: str
    merchant: str | None = None


@app.post("/tools/get_best_card_for_purchase")
def http_get_best_card_for_purchase(payload: BestCardQuery):
    return finance_tools.get_best_card_for_purchase(
        amount=payload.amount, category=payload.category, merchant=payload.merchant
    )


class GetSummaryQuery(BaseModel):
    name: str | None = None


@app.get("/tools/get_payment_method_summary")
def http_get_payment_method_summary(q: GetSummaryQuery = Depends()):
    return finance_tools.get_payment_method_summary(name=q.name)


