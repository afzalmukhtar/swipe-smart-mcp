from logging import getLogger
from typing import Optional
from mcp.server.fastmcp import FastMCP

logger = getLogger(__name__)

mcp = FastMCP("Personal Finance Server")

# database setup
database = []


# --------------------- Wallet ---------------------
# This is the main wallet that contains your credit cards
# --------------------------------------------------
@mcp.tool()
def add_credit_card(
    name: str,
    bank: str,
    monthly_limit: float,
    billing_cycle_start: int,
    base_reward_rate: float = 1.0,
) -> str:
    """
    Registers a new credit card in the database.

    Args:
        name: The nickname of the card (e.g., "Amex Platinum", "Axis Magnus").
        bank: The issuing bank (e.g., "HDFC", "SBI").
        monthly_limit: The credit limit in account currency.
        billing_cycle_start: The day of the month the bill generates (1-31).
        base_reward_rate: The default points earned per unit spent (default: 1.0).

    Returns:
        A confirmation message including the new Card ID.
    """
    logger.info(f"Adding credit card: {name}")
    return f"Credit card '{name}' added successfully."


@mcp.tool()
def get_credit_cards() -> str:
    """
    Retrieves a list of all active credit cards.

    Returns:
        A formatted string listing all cards with their IDs, names, and limits.
        Useful for finding the 'card_id' or 'name' before adding a transaction.
    """
    logger.info("Getting credit cards")
    return "Credit cards retrieved successfully."


@mcp.tool()
def delete_credit_card(card_name: str) -> str:
    """
    Permanently removes a credit card from the system.

    Args:
        card_name: The exact name of the card to delete.

    Returns:
        Success or error message.
    """
    logger.info(f"Deleting credit card: {card_name}")
    return f"Credit card '{card_name}' deleted successfully."


# --------------------- Transactions ---------------------
# This is the main wallet that contains your credit cards
# --------------------------------------------------------
@mcp.tool()
def add_transaction(
    amount: float, merchant: str, category: str, card_name: str, date: str = None
) -> str:
    """
    Logs a new expense (transaction) to the database.

    Args:
        amount: The value of the transaction.
        merchant: The name of the place/service (e.g., "Uber", "Amazon").
        category: The expense type (e.g., "Dining", "Travel", "Utilities").
        card_name: The name of the credit card used (must match an existing card).
        date: Optional date of transaction in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
        Confirmation message with Transaction ID and calculated points (if applicable).
    """
    logger.info(
        f"Adding transaction: {amount} {merchant} {category} {card_name} {date}"
    )
    return f"Transaction added successfully."


@mcp.tool()
def get_transactions(limit: int = 5, category: Optional[str] = None) -> str:
    """
    Fetches the most recent transactions from the history.

    Args:
        limit: The number of transactions to return (default: 5).
        category: Optional filter to see expenses only for a specific category (e.g., "Food").

    Returns:
        A table-like string of transactions showing Date, Merchant, Amount, and Card.
    """
    logger.info(f"Getting transactions: {limit} {category}")
    return "Transactions retrieved successfully."


@mcp.tool()
def delete_transaction(transaction_id: int) -> str:
    """
    Deletes a specific transaction record.

    Args:
        transaction_id: The unique ID of the transaction (found via get_transactions).

    Returns:
        Success message confirming deletion.
    """
    logger.info(f"Deleting transaction: {transaction_id}")
    return "Transaction deleted successfully."


# ----------------- The Points System -----------------
#       This tracks your points earned per card
# -----------------------------------------------------


@mcp.tool()
def get_reward_balance(card_name: str) -> str:
    """
    Checks the current accumulated reward points for a specific card.

    Args:
        card_name: The name of the card to check.

    Returns:
        The total points balance.
    """
    logger.info(f"Getting reward balance: {card_name}")
    return "Reward balance retrieved successfully."


@mcp.tool()
def adjust_reward_points(card_name: str, points: int, reason: str) -> str:
    """
    Manually adjusts the point balance (adds or subtracts).
    Use this for redemptions, expiration, or bonuses.

    Args:
        card_name: The card to adjust.
        points: The number of points to add (positive) or remove (negative).
        reason: A note explaining the adjustment (e.g., "Redeemed for flight", "Signup Bonus").

    Returns:
        The new updated balance.
    """
    logger.info(f"Adjusting reward points: {card_name} {points} {reason}")
    return "Reward points adjusted successfully."


if __name__ == "__main__":
    app = FastMCP()
    app.run()
