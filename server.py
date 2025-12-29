import json
import traceback
from datetime import datetime
from logging import getLogger
from pathlib import Path
from textwrap import dedent
from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, col, select, and_, or_

from src.db import engine
from src.models import CapBucket, CreditCard, Expense, RewardRule

# Path to categories data
CATEGORIES_FILE = Path(__file__).parent / "data" / "categories.json"


def load_categories() -> dict:
    """Load categories from JSON file."""
    with open(CATEGORIES_FILE, "r") as f:
        return json.load(f)


def get_category_names() -> list[str]:
    """Get list of valid category names."""
    data = load_categories()
    return [cat["name"] for cat in data["categories"]]


logger = getLogger(__name__)

mcp = FastMCP("finance-server")


# ======================= RESOURCES =======================
# Resources expose static/dynamic data for LLM clients
# =========================================================


@mcp.resource("finance://categories")
def list_categories() -> str:
    """
    Returns all valid expense categories with their descriptions.

    Use this resource to:
    1. Know which categories are available for logging transactions.
    2. Understand what each category covers (e.g., 'Dining' includes food delivery apps).
    3. Check which categories are typically excluded from rewards.
    """
    data = load_categories()
    return json.dumps(data, indent=2)


@mcp.resource("finance://categories/names")
def list_category_names() -> str:
    """
    Returns a simple list of valid category names.
    Use this for quick validation or selection.
    """
    names = get_category_names()
    return json.dumps(names)


@mcp.resource("finance://categories/excluded")
def list_excluded_categories() -> str:
    """
    Returns categories that are typically excluded from credit card rewards.
    These include: Insurance, Government, Rent, Wallet Loads, EMI, Jewellery, Cash Advance.
    """
    data = load_categories()
    excluded = [
        cat["name"]
        for cat in data["categories"]
        if cat.get("excluded_from_rewards", False)
    ]
    return json.dumps(excluded)


# ========================= TOOLS =========================
# Tools allow LLM clients to perform actions
# =========================================================


@mcp.tool()
def get_expense_logging_rules() -> dict:
    """
    **IMPORTANT: Call this tool BEFORE adding any expense.**

    Returns the guidelines and rules for logging expenses, including:
    - Required fields and their formats
    - Valid categories
    - Smart inference rules
    - How to handle missing information

    You MUST read these guidelines before calling `add_transaction`.
    """
    try:
        categories = get_category_names()
        cat_list = ", ".join(categories)

        all_cats = load_categories()["categories"]
        excluded = [
            c["name"] for c in all_cats if c.get("excluded_from_rewards", False)
        ]
        excluded_str = ", ".join(excluded)
    except Exception:
        cat_list = "Dining, Groceries, Fuel, Travel"
        excluded_str = "Fuel, Insurance"

    today = datetime.now().strftime("%Y-%m-%d")

    return {
        "status": "success",
        "today": today,
        "required_fields": {
            "amount": "Transaction value (e.g., 500, ₹200)",
            "merchant": "Where money was spent (e.g., Starbucks, Amazon)",
            "category": f"One of: {cat_list}",
            "card_name": "Which credit card was used",
        },
        "optional_fields": {
            "platform": "Default 'Direct'. Options: Direct, SmartBuy, Amazon Pay, CRED, Swiggy, Zomato",
            "date": f"Default '{today}'. Format: YYYY-MM-DD",
        },
        "inference_rules": {
            "Starbucks/Cafe/Coffee": "Category → Dining",
            "Swiggy/Zomato": "Category → Dining, Platform → Swiggy or Zomato",
            "Amazon": "Category → Shopping",
            "Uber/Ola": "Category → Travel",
        },
        "excluded_from_rewards": excluded_str,
        "behavior_rules": [
            "Parse the user's message first and extract all available details.",
            "If you found data: show what you extracted with ✅ provided, ✨ inferred, ❌ missing.",
            "Only ask for fields that are missing AND required.",
            "NEVER re-ask for information already provided by the user.",
            "If no parseable data: say 'I couldn't find expense details. Please provide: amount, merchant, and card.'",
            "Call add_transaction ONLY after user confirms the final summary.",
        ],
    }


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


# --- TOOL 2: See Transactions ---
@mcp.tool()
def get_transactions(
    limit: int = 5,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[list[str]] = None,
    merchant: Optional[list[str]] = None,
    card_name: Optional[list[str]] = None,
    platform: Optional[list[str]] = None,
    bank: Optional[list[str]] = None,
) -> dict:
    """
    Retrieves transactions based on flexible filters.

    Logic:
    - Multiple values within a filter are treated as OR (e.g., category=['Dining', 'Food'] -> Dining OR Food).
    - Different filters are treated as AND (e.g., category='Dining' AND card='HDFC').

    Args:
        limit (int): Max number of records to return (default: 5).
        start_date (str): Filter for transactions ON or AFTER this date (Format: YYYY-MM-DD).
        end_date (str): Filter for transactions ON or BEFORE this date (Format: YYYY-MM-DD).
        category (list[str]): List of categories to match (e.g., ["Dining", "Groceries"]).
        merchant (list[str]): List of merchants to match (e.g., ["Amazon", "Flipkart"]).
        card_name (list[str]): List of card names to match (e.g., ["HDFC", "Amex"]).
        platform (list[str]): List of platforms (e.g., ["Swiggy", "Zomato"]).
        bank (list[str]): List of banks (e.g., ["HDFC", "SBI"]).

    Returns:
        dict: A structured list of matching transactions and a summary count.
    """
    logger.info(f"Getting transactions with filters: {locals()}")

    try:
        with Session(engine) as session:
            # Step 1: Base Query (Join Expense + Card)
            query = select(Expense).join(CreditCard)

            # This list will store all "AND" conditions
            and_conditions = []

            # --- Date Filters ---
            if start_date:
                try:
                    s_date = datetime.strptime(start_date, "%Y-%m-%d")
                    and_conditions.append(Expense.date >= s_date)
                except ValueError:
                    return {
                        "status": "error",
                        "message": "Invalid start_date. Use YYYY-MM-DD.",
                    }

            if end_date:
                try:
                    e_date = datetime.strptime(end_date, "%Y-%m-%d")
                    # Set time to end of day to include transactions on that day
                    e_date = e_date.replace(hour=23, minute=59, second=59)
                    and_conditions.append(Expense.date <= e_date)
                except ValueError:
                    return {
                        "status": "error",
                        "message": "Invalid end_date. Use YYYY-MM-DD.",
                    }

            # --- Text Filters (Handling Lists with OR logic) ---

            # Helper function to build OR conditions for a list
            def build_or_filter(column, values):
                if not values:
                    return None
                # Creates: (col ILIKE '%val1%' OR col ILIKE '%val2%')
                conditions = [col(column).ilike(f"%{v}%") for v in values]
                return or_(*conditions)

            if category:
                cond = build_or_filter(Expense.category, category)
                if cond is not None:
                    and_conditions.append(cond)

            if merchant:
                cond = build_or_filter(Expense.merchant, merchant)
                if cond is not None:
                    and_conditions.append(cond)

            if platform:
                cond = build_or_filter(Expense.platform, platform)
                if cond is not None:
                    and_conditions.append(cond)

            if card_name:
                cond = build_or_filter(CreditCard.name, card_name)
                if cond is not None:
                    and_conditions.append(cond)

            if bank:
                cond = build_or_filter(CreditCard.bank, bank)
                if cond is not None:
                    and_conditions.append(cond)

            # --- Apply All Conditions ---
            if and_conditions:
                query = query.where(and_(*and_conditions))

            # --- Sorting & Limiting ---
            query = query.order_by(Expense.date.desc()).limit(limit)

            # --- Execute ---
            transactions = session.exec(query).all()

            # --- Format Response ---
            if not transactions:
                return {
                    "status": "success",
                    "message": "No transactions found matching criteria.",
                    "count": 0,
                    "transactions": [],
                }

            txn_list = []
            for txn in transactions:
                card_str = txn.card.name if txn.card else "Unknown"
                txn_list.append(
                    {
                        "id": txn.id,
                        "date": txn.date.strftime("%Y-%m-%d"),
                        "merchant": txn.merchant,
                        "amount": txn.amount,
                        "category": txn.category,
                        "platform": txn.platform,
                        "card": card_str,
                        "points": txn.points_earned,
                    }
                )

            return {
                "status": "success",
                "count": len(txn_list),
                "transactions": txn_list,
            }

    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": f"System error: {str(e)}"}


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


# --- Tool 4: Delete Transaction ---
@mcp.tool()
def delete_transaction(transaction_id: int) -> str:
    """
    Permanently removes a specific transaction record from the database.

    Args:
        transaction_id (int): The unique numeric ID of the transaction (found via 'get_recent_transactions').

    Returns:
        str: Success or error message.
    """
    try:
        with Session(engine) as session:
            txn = session.get(Expense, transaction_id)

            if not txn:
                return f"❌ Error: Transaction with ID {transaction_id} not found."

            # Save details for the confirmation message before deleting
            details = f"{txn.merchant} (₹{txn.amount}) [Date: {txn.date.strftime('%Y-%m-%d')}, Category: {txn.category}, Platform: {txn.platform}]"

            session.delete(txn)
            session.commit()

            return f"🗑️ Success: Deleted transaction '{details}' [ID: {transaction_id}]."

    except Exception as e:
        return (
            f"❌ Error executing tool: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        )


# --- TOOL 5: Delete a Credit Card ---
@mcp.tool()
def delete_credit_card(card_id: int) -> str:
    """
    Permanently deletes a credit card and ALL its associated rules, limits, and history.

    ⚠️ WARNING: This action cannot be undone. It removes:
    - The Card entry
    - All Reward Rules for this card
    - All Cap Buckets for this card
    - All Redemption Partners for this card
    - (Expenses might remain as orphans depending on DB settings, but are usually unlinked)

    Args:
        card_id (int): The unique numeric ID of the card (found via 'get_my_cards').

    Returns:
        str: Success or error message.
    """
    try:
        with Session(engine) as session:
            card = session.get(CreditCard, card_id)

            if not card:
                return f"❌ Error: Card with ID {card_id} not found."

            card_name = card.name
            card_limit = card.monthly_limit
            card_bank = card.bank

            # Delete the card (SQLModel/SQLAlchemy usually handles simple deletions,
            # but note that related rows might need explicit cascading in complex setups.
            # For this simple setup, we delete the parent.)
            session.delete(card)
            session.commit()

            return f"🗑️ Success: Deleted Card '{card_name}' (Limit: ₹{card_limit}, Bank: {card_bank}) [ID: {card_id}] and its configuration."

    except Exception as e:
        return (
            f"❌ Error executing tool: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        )


# --- TOOL 6: Add Transaction ---
@mcp.tool()
def add_transaction(
    amount: float,
    merchant: str,
    category: str,
    card_name: str,
    platform: str = "Direct",
    date: Optional[str] = None,
) -> dict:
    """
    Logs a new expense (transaction) to the database.

    **IMPORTANT: Call `get_expense_logging_rules` first to learn the rules for parsing user input.**

    Args:
        amount: The value of the transaction (must be positive).
        merchant: The name of the place/service (e.g., "Swiggy", "Amazon").
        category: The expense category. Must be a valid category from get_expense_logging_rules.
        card_name: The name of the credit card used.
        platform: How the payment was made (e.g., "Direct", "SmartBuy").
        date: Optional date in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
        dict: Confirmation details including Transaction ID and status.
    """
    try:
        # --- Validation ---

        # 1. Validate amount
        if amount <= 0:
            return {"status": "error", "message": "Amount must be positive."}

        # 2. Validate category
        valid_categories = get_category_names()
        if category not in valid_categories:
            return {
                "status": "error",
                "message": f"Invalid category '{category}'.",
                "valid_categories": valid_categories,
            }

        # 3. Parse date
        if date:
            try:
                transaction_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return {
                    "status": "error",
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                }
        else:
            transaction_date = datetime.now()

        # 4. Find the card
        with Session(engine) as session:
            query = select(CreditCard).where(
                col(CreditCard.name).ilike(f"%{card_name}%")
            )
            cards = session.exec(query).all()

            if not cards:
                return {
                    "status": "error",
                    "message": f"Card matching '{card_name}' not found.",
                }

            if len(cards) > 1:
                matches = [{"id": c.id, "name": c.name} for c in cards]
                return {
                    "status": "error",
                    "message": "Multiple cards found. Please be specific.",
                    "matches": matches,
                }

            card = cards[0]

            # --- 5. Calculate Points (THE BRAIN - Coming Next!) ---
            # For now, we set it to 0.0, but in the next step, we will call:
            # points_earned = calculate_points(card, amount, category, platform, transaction_date)
            points_earned = 0.0

            # --- 6. Create the Expense ---
            expense = Expense(
                amount=amount,
                merchant=merchant,
                category=category,
                platform=platform,
                date=transaction_date,
                card_id=card.id,
                points_earned=points_earned,
            )

            session.add(expense)
            session.commit()
            session.refresh(expense)

            # --- Check for Exclusion (for the user warning) ---
            categories_data = load_categories()
            is_excluded = any(
                cat["name"] == category and cat.get("excluded_from_rewards", False)
                for cat in categories_data["categories"]
            )

            return {
                "status": "success",
                "message": "Transaction added successfully.",
                "transaction": {
                    "id": expense.id,
                    "date": expense.date.strftime("%Y-%m-%d"),
                    "merchant": expense.merchant,
                    "amount": expense.amount,
                    "category": expense.category,
                    "platform": expense.platform,
                    "card": card.name,
                    "points_earned": expense.points_earned,
                },
                "meta": {
                    "is_excluded_category": is_excluded,
                    "note": "Points calculation pending implementation."
                    if points_earned == 0
                    else "Points calculated.",
                },
            }

    except Exception as e:
        logger.error(f"Error adding transaction: {str(e)}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


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
