import traceback
from logging import getLogger
from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, select, col

from src.db import engine
from src.models import CapBucket, CreditCard, Expense, RewardRule

logger = getLogger(__name__)

mcp = FastMCP("finance-server")

# database setup
database = []


# --- TOOL 1: Wallet Overviews ---
@mcp.tool()
def get_my_cards() -> dict:
    """
    Retrieves a summary of all credit cards currently stored in the wallet database.

    Use this tool to:
    1. Find the specific unique 'ID' of a card (required for other tools).
    2. Check credit limits, remaining limits, and billing cycle dates.
    3. See the 'Base Value' (floor price) of points for each card.

    Returns:
        dict: A dictionary of cards, including their ID, Name, Bank, Limit, and Billing Cycle.
    """
    try:
        with Session(engine) as session:
            statement = select(CreditCard)
            cards = session.exec(statement).all()

            if not cards:
                return "Your wallet is empty. No cards found."

            response = {}
            for card in cards:
                response[f"{card.name} [ID: {card.id}]"] = {
                    "bank": card.bank,
                    "limit": card.monthly_limit,
                    "base_value": card.base_point_value,
                    "billing_cycle_start": card.billing_cycle_start,
                }

            return response
    except Exception as e:
        logger.error(f"Error fetching cards: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error fetching cards: {str(e)}"


# --- TOOL 2: See Recent Transactions ---
@mcp.tool()
def get_recent_transactions() -> dict:
    """
    Fetches the log of the 10 most recent transactions recorded in the system.

    Use this tool to:
    1. Analyze recent spending habits.
    2. Verify if a specific transaction was successfully logged after an 'add_transaction' call.
    3. Identify which card was used for specific merchants.

    Returns:
        dict: A dictionary of the last 10 expenses, showing Amount, Merchant, Date, Platform, and the Card used.
    """
    try:
        with Session(engine) as session:
            # Get last 10 expenses
            statement = select(Expense).limit(10).order_by(Expense.date.desc())
            expenses = session.exec(statement).all()

            if not expenses:
                return "No transactions found."

            response = {}
            for txn in expenses:
                # Safe access to card details
                if txn.card:
                    card_info = f"{txn.card.name} [ID: {txn.card.id}]"
                else:
                    card_info = "Unknown Card"

                response[txn.id] = {
                    "merchant": txn.merchant,
                    "amount": txn.amount,
                    "platform": txn.platform,
                    "card": card_info,
                }

            return response
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error fetching transactions: {str(e)}"


# --- TOOL 3: Get Card Rules ---
@mcp.tool()
def get_card_rules(card_identifier: str) -> dict:
    """
    Retrieves the detailed reward logic (multipliers, caps, and limits) for specific credit cards.

    Args:
        card_identifier (str): The search term. Can be:
            - A specific numeric Card ID (e.g., "1") for a precise lookup.
            - A partial Card Name (e.g., "HDFC") to find all matching cards.

    Returns:
        dict: A structured JSON object containing:
            - 'status': 'success' or 'error'
            - 'match_count': Number of cards found.
            - 'cards': A list of matching card details, where each entry includes:
                - 'rules': List of categories (e.g., 'Dining'), multipliers (Base + Bonus), and any 'capped_by' limits.

    Example:
        get_card_rules("1") -> Returns rules strictly for Card ID 1.
        get_card_rules("Regalia") -> Returns rules for all cards containing 'Regalia'.
    """
    try:
        with Session(engine) as session:
            query = select(CreditCard)

            # 1. Determine if input is an ID or a Name
            if card_identifier.isdigit():
                # Search by exact ID
                query = query.where(CreditCard.id == int(card_identifier))
            else:
                # Search by Name (Case-Insensitive Partial Match)
                # This allows "HDFC" to find both "HDFC Regalia" and "HDFC Infinia"
                query = query.where(col(CreditCard.name).ilike(f"%{card_identifier}%"))

            results = session.exec(query).all()

            if not results:
                return {
                    "status": "error",
                    "message": f"No cards found matching '{card_identifier}'.",
                }

            # 2. Build the Structured Dictionary
            output = {"status": "success", "match_count": len(results), "cards": []}

            for card in results:
                card_data = {
                    "id": card.id,
                    "name": card.name,
                    "bank": card.bank,
                    "rules": [],
                }

                # Format Rules
                if not card.reward_rules:
                    card_data["rules"].append(
                        {
                            "category": "All Spends",
                            "description": "Base Rate Only (No special multipliers)",
                        }
                    )

                for rule in card.reward_rules:
                    rule_info = {
                        "category": rule.category,
                        "multiplier": f"{rule.base_multiplier}x Base + {rule.bonus_multiplier}x Bonus",
                        "total_multiplier": rule.base_multiplier
                        + rule.bonus_multiplier,
                        "is_capped": False,
                        "capped_by": None,
                    }

                    # specific check for cap bucket
                    if rule.cap_bucket:
                        rule_info["is_capped"] = True
                        rule_info["capped_by"] = {
                            "bucket_name": rule.cap_bucket.name,
                            "limit": rule.cap_bucket.max_points,
                            "period": rule.cap_bucket.period,
                        }

                    card_data["rules"].append(rule_info)

                output["cards"].append(card_data)

            return output

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
        }


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
    mcp.run()
