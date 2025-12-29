import json
import traceback
from datetime import datetime
from logging import getLogger
from pathlib import Path
from textwrap import dedent
from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, col, select, and_

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


# ======================== PROMPTS ========================
# Prompts provide guidance templates for LLM interactions
# =========================================================


@mcp.prompt()
def log_expense() -> str:
    """
    Interactive prompt to help users log a new expense/transaction.
    Use this when the user wants to record a purchase or payment.
    """
    categories = get_category_names()
    cat_list = "\n".join([f"  - {cat}" for cat in categories])

    excluded = [
        cat["name"]
        for cat in load_categories()["categories"]
        if cat.get("excluded_from_rewards", False)
    ]
    excluded_list = ", ".join(excluded)

    return dedent(
        f"""
        # Add New Transaction

        I'll help you log a new expense. Let me gather the details.

        ---

        ## Instructions for Assistant

        Follow these steps IN ORDER to add a transaction:

        ### Step 1: Collect Required Transaction Details

        Ask the user for ALL of these details (if not already provided):

        | Field | Required | Description | Example |
        |-------|----------|-------------|---------|
        | **Amount** | ✅ Yes | Transaction value in ₹ | ₹500, 1200 |
        | **Merchant** | ✅ Yes | Store/service name | "Swiggy", "Amazon", "HP Petrol" |
        | **Platform** | ✅ Yes | HOW was payment made? | "Direct", "SmartBuy", "Amazon Pay", "CRED" |
        | **Date** | Optional | When did this happen? | YYYY-MM-DD (default: today) |

        #### Platform Options (CRITICAL for reward calculation!)

        The **platform** determines bonus multipliers. Common platforms:

        | Platform | Description | Cards that benefit |
        |----------|-------------|-------------------|
        | **Direct** | Paid directly at merchant (default) | Base rewards only |
        | **SmartBuy** | HDFC SmartBuy portal | HDFC cards (10x points) |
        | **Amazon Pay** | Amazon Pay balance/UPI | Amazon Pay ICICI (5% back) |
        | **Flipkart** | Flipkart app/website | Flipkart Axis (5% back) |
        | **CRED** | CRED app payments | Various bonus offers |
        | **PayTM** | PayTM wallet/UPI | PayTM cards |
        | **PhonePe** | PhonePe app | Various cashback |
        | **Google Pay** | GPay UPI | Bank-specific offers |
        | **Swiggy** | Swiggy app direct | Swiggy HDFC (10x on Swiggy) |
        | **Zomato** | Zomato app direct | Various dining bonuses |
        | **BookMyShow** | BMS app/website | Entertainment bonuses |
        | **MakeMyTrip** | MMT portal | Travel card bonuses |
        | **Cleartrip** | Cleartrip portal | Travel card bonuses |

        **Always ask**: "Did you pay directly, or through any app/portal like SmartBuy, CRED, Amazon Pay?"

        ### Step 2: Determine the Category

        Based on the merchant, select the appropriate category:

        {cat_list}

        **Category Mapping Guide:**
        | Merchant Type | Category |
        |---------------|----------|
        | Swiggy, Zomato, UberEats, Restaurants | Dining |
        | Amazon, Flipkart, Myntra, Meesho | Shopping - Online |
        | Malls, Retail stores, Croma, Reliance Digital | Shopping - Retail |
        | MakeMyTrip flights, Cleartrip flights, Airlines | Travel - Flights |
        | MakeMyTrip hotels, OYO, Airbnb, Booking.com | Travel - Hotels |
        | IRCTC, Metro recharge | Travel - Railways |
        | Uber, Ola, Rapido | Travel - Cabs & Rideshare |
        | Petrol pumps, HP, Indian Oil, Shell | Fuel |
        | Netflix, Hotstar, Prime Video, BookMyShow | Entertainment |
        | BigBasket, Blinkit, Zepto, DMart | Groceries |
        | 1mg, PharmEasy, Apollo Pharmacy | Healthcare |
        | Jio, Airtel, Vi, Broadband | Telecom & Internet |
        | Electricity, Water, Piped Gas | Utilities |

        **If unsure about the category, ASK the user to confirm.**

        ### Step 3: Select the Credit Card

        - Call `get_my_cards()` to see available cards in wallet
        - Ask user: "Which card did you use for this transaction?"
        - If only one card exists, confirm with user before proceeding

        ### Step 4: Confirm Before Adding

        Show a complete summary:
        ```
        📝 Transaction Summary
        ━━━━━━━━━━━━━━━━━━━━━
        Amount:   ₹[amount]
        Merchant: [merchant]
        Category: [category]
        Platform: [platform]
        Card:     [card_name]
        Date:     [date]
        ━━━━━━━━━━━━━━━━━━━━━
        ```
        Ask: "Does this look correct? Should I add this transaction?"

        ### Step 5: Add the Transaction

        Once confirmed, call `add_transaction()` tool with:
        - amount
        - merchant
        - category
        - card_name
        - platform
        - date (if provided, else omit for today)

        ---

        ## Important Notes

        **Categories typically EXCLUDED from rewards** (still track, but expect 0 points):
        {excluded_list}

        **Validation Rules:**
        - Amount must be a positive number
        - Category must be from the valid list above
        - Platform should match known platforms (or "Direct")
        - Card must exist in the wallet

        ---

        User, please tell me about the transaction you want to add. 

        What did you spend on, how much, and how did you pay?
    """
    )


# ========================= TOOLS =========================
# Tools allow LLM clients to perform actions
# =========================================================


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
    Retrieves transactions based on flexible filters. By default, returns the most recent 10 transactions.

    Args:
        limit (int): Max number of records to return (default: 10).
        start_date (str): Filter for transactions ON or AFTER this date (Format: YYYY-MM-DD).
        end_date (str): Filter for transactions ON or BEFORE this date (Format: YYYY-MM-DD).
        category (list[str]): Filter by category name (e.g., "Dining"). Case-insensitive partial match.
        merchant (list[str]): Filter by merchant name (e.g., "Amazon"). Case-insensitive partial match.
        card_name (list[str]): Filter by credit card name (e.g., "HDFC"). Case-insensitive partial match.
        platform (list[str]): Filter by platform name (e.g., "Online"). Case-insensitive partial match.
        bank (list[str]): Filter by bank name (e.g., "HDFC"). Case-insensitive partial match.

    Returns:
        dict: A structured list of matching transactions and a summary count.
    """
    logger.info(f"Getting transactions: {limit} {category}")
    # TODO: Step 1: Get every transaction
    # TODO: Step 2: Filter by date range
    # TODO: Step 3: Filter by merchant
    # TODO: Step 4: Filter by category
    # TODO: Step 5: Filter by platform
    # TODO: Step 6: Filter by card name
    # TODO: Step 7: Filter by bank
    # TODO: Step 8: Sort by Date and limit to 'limit'
    # TODO: Step 9: Return the filtered transactions
    return {
        "status": "success",
        "count": 0,
        "transactions": [],
    }


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


# --------------------- Transactions ---------------------
# Log and track expenses across your credit cards
# --------------------------------------------------------
@mcp.tool()
def add_transaction(
    amount: float,
    merchant: str,
    category: str,
    card_name: str,
    platform: str = "Direct",
    date: Optional[str] = None,
) -> str:
    """
    Logs a new expense (transaction) to the database.

    Args:
        amount: The value of the transaction (must be positive).
        merchant: The name of the place/service (e.g., "Swiggy", "Amazon", "HP Petrol").
        category: The expense category. Must be a valid category from the categories resource.
        card_name: The name of the credit card used (must match an existing card).
        platform: How the payment was made (e.g., "Direct", "SmartBuy", "CRED", "Amazon Pay").
        date: Optional date in 'YYYY-MM-DD' format. Defaults to today.

    Returns:
        Confirmation message with Transaction ID and points earned.
    """
    try:
        # --- Validation ---

        # 1. Validate amount
        if amount <= 0:
            return "❌ Error: Amount must be a positive number."

        # 2. Validate category
        valid_categories = get_category_names()
        if category not in valid_categories:
            return f"❌ Error: Invalid category '{category}'.\n\nValid categories: {', '.join(valid_categories)}"

        # 3. Parse date
        if date:
            try:
                transaction_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return (
                    "❌ Error: Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-25)."
                )
        else:
            transaction_date = datetime.now()

        # 4. Find the card
        with Session(engine) as session:
            # Search by name (case-insensitive partial match)
            query = select(CreditCard).where(
                col(CreditCard.name).ilike(f"%{card_name}%")
            )
            cards = session.exec(query).all()

            if not cards:
                return f"❌ Error: No card found matching '{card_name}'. Use get_my_cards() to see available cards."

            if len(cards) > 1:
                card_names = [f"- {c.name} (ID: {c.id})" for c in cards]
                return (
                    f"❌ Error: Multiple cards match '{card_name}'. Please be more specific:\n"
                    + "\n".join(card_names)
                )

            card = cards[0]

            # --- Create the Expense ---
            expense = Expense(
                amount=amount,
                merchant=merchant,
                category=category,
                platform=platform,
                date=transaction_date,
                card_id=card.id,
                points_earned=0.0,  # TODO: Calculate based on reward rules
            )

            session.add(expense)
            session.commit()
            session.refresh(expense)

            # --- Check if category is excluded ---
            categories_data = load_categories()
            is_excluded = any(
                cat["name"] == category and cat.get("excluded_from_rewards", False)
                for cat in categories_data["categories"]
            )

            excluded_note = ""
            if is_excluded:
                excluded_note = (
                    "\n⚠️ Note: This category is typically excluded from rewards."
                )

            return (
                f"✅ Transaction Added Successfully!\n\n"
                f"📝 Details:\n"
                f"   ID: {expense.id}\n"
                f"   Amount: ₹{expense.amount:,.2f}\n"
                f"   Merchant: {expense.merchant}\n"
                f"   Category: {expense.category}\n"
                f"   Platform: {expense.platform}\n"
                f"   Card: {card.name}\n"
                f"   Date: {expense.date.strftime('%Y-%m-%d')}\n"
                f"   Points Earned: {expense.points_earned}"
                f"{excluded_note}"
            )

    except Exception as e:
        logger.error(f"Error adding transaction: {str(e)}")
        logger.error(traceback.format_exc())
        return f"❌ Error adding transaction: {str(e)}"


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
