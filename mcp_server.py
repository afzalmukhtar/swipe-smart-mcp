from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from finance_mcp import tools as finance_tools
from finance_mcp.database import init_db

mcp = FastMCP("Personal Finance MCP Server")


@mcp.tool
def add_expense(
    amount: float,
    description: str,
    category: str,
    payment_source: str,
    person: str,
    date: str | None = None,
) -> dict[str, Any]:
    return finance_tools.add_expense(
        amount=amount,
        description=description,
        category=category,
        payment_source=payment_source,
        person=person,
        date_str=date,
    )


@mcp.tool
def get_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    payment_source: str | None = None,
    person: str | None = None,
) -> list[dict[str, Any]]:
    return finance_tools.get_expenses(
        start_date=start_date,
        end_date=end_date,
        category=category,
        payment_source=payment_source,
        person=person,
    )


@mcp.tool
def edit_expense(
    expense_id: int,
    amount: float | None = None,
    description: str | None = None,
    category: str | None = None,
    payment_source: str | None = None,
    person: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    return finance_tools.edit_expense(
        expense_id=expense_id,
        amount=amount,
        description=description,
        category=category,
        payment_source=payment_source,
        person=person,
        date_str=date,
    )


@mcp.tool
def add_payment_method(
    name: str,
    type: str,
    credit_limit: float | None = None,
    statement_date: int | None = None,
    reward_rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return finance_tools.add_payment_method(
        name=name,
        type=type,
        credit_limit=credit_limit,
        statement_date=statement_date,
        reward_rules=reward_rules,
    )


@mcp.tool
def list_payment_methods() -> list[dict[str, Any]]:
    return finance_tools.list_payment_methods()


@mcp.tool
def remove_payment_method(name: str) -> dict[str, Any]:
    return finance_tools.remove_payment_method(name=name)


@mcp.tool
def pay_credit_card_bill(name: str, amount_paid: float) -> dict[str, Any]:
    return finance_tools.pay_credit_card_bill(name=name, amount_paid=amount_paid)


@mcp.tool
def get_best_card_for_purchase(
    amount: float, category: str, merchant: str | None = None
) -> list[dict[str, Any]]:
    return finance_tools.get_best_card_for_purchase(
        amount=amount, category=category, merchant=merchant
    )


@mcp.tool
def get_payment_method_summary(name: str | None = None) -> list[dict[str, Any]]:
    return finance_tools.get_payment_method_summary(name=name)


def main() -> None:
    init_db()
    mcp.run()  # Default transport: stdio


if __name__ == "__main__":
    main()
