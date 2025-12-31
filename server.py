import json
import traceback
from datetime import datetime, timedelta
from logging import getLogger
from pathlib import Path
from typing import Optional

from ddgs import DDGS
from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, and_, col, func, or_, select

from src.db import engine
from src.logic.recommender import recommend_all_cards
from src.logic.rewards import calculate_rewards
from src.models import (
    AdjustmentType,
    BucketScope,
    CapBucket,
    CreditCard,
    Expense,
    PeriodType,
    PointAdjustment,
    RedemptionPartner,
    RewardRule,
)

# Path to categories data
CATEGORIES_FILE = Path(__file__).parent / "data" / "categories.json"

# Bank domain mapping - loaded dynamically from data/bank_domains.json
BANK_DOMAINS_FILE = Path(__file__).parent / "data" / "bank_domains.json"


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
                card_data: dict[str, list[dict[str, str]]] = {
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
    is_online: Optional[bool] = None,
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
        is_online: Explicit flag if known (True=Online, False=Offline). If None, system infers.

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

            # 5. Infer is_online if not provided (Smart Logic)
            if is_online is None:
                # A. Check Category
                if category in [
                    "Shopping - Online",
                    "Travel - Flights",
                    "Travel - Cabs & Rideshare",
                    "Entertainment",
                    "Education",
                ]:
                    is_online = True

                # B. Check Merchant (Common Examples)
                online_merchants = [
                    "Amazon",
                    "Flipkart",
                    "Myntra",
                    "Uber",
                    "Ola",
                    "Swiggy",
                    "Zomato",
                    "Netflix",
                    "Spotify",
                    "Apple",
                    "Google",
                ]
                if any(m.lower() in merchant.lower() for m in online_merchants):
                    is_online = True

                # C. Check Platform
                if platform in ["SmartBuy", "Gyftr"]:
                    is_online = True

            # 6. Create Expense & Calculate Rewards
            expense = Expense(
                amount=amount,
                merchant=merchant,
                category=category,
                platform=platform,
                date=transaction_date,
                card_id=card.id,
                points_earned=0.0,
                is_online=is_online,
            )
            # Link the card object so the relationship is available immediately
            expense.card = card

            # Calculate Rewards
            reward_result = calculate_rewards(session, expense)
            expense.points_earned = reward_result.total_points

            # Save breakdown in notes
            if reward_result.breakdown:
                expense.notes = "\n".join(reward_result.breakdown)

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
                    "is_online": expense.is_online,
                },
                "meta": {
                    "is_excluded_category": is_excluded,
                    "reward_breakdown": reward_result.breakdown,
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
def get_card_addition_guidelines() -> dict:
    """
    **IMPORTANT: Call this tool BEFORE adding any credit card.**

    Returns guidelines for adding a new credit card, including:
    - What information to collect from the user (REQUIRED - only user knows)
    - What information to search online (reward rules, caps, etc.)
    - The workflow for adding a card step by step

    You MUST read these guidelines before starting the card addition workflow.
    """
    return {
        "status": "success",
        "workflow": [
            "1. Call this tool to get guidelines",
            "2. Collect REQUIRED fields from user (they must provide these)",
            "3. Call search_card_info(card_name) to find reward rules online",
            "4. Call add_credit_card with user-provided info → get card_id",
            "5. Call add_cap_buckets if card has caps (BEFORE rules if rules reference caps)",
            "6. Call add_reward_rules with rules extracted from search",
            "7. Call add_redemption_partners if card has transfer partners",
        ],
        "user_required_fields": {
            "name": "Full card name (e.g., 'HDFC Regalia Gold', 'SBI Cashback')",
            "bank": "Issuing bank (e.g., 'HDFC', 'SBI', 'ICICI', 'Axis', 'Amex')",
            "monthly_limit": "Credit limit in INR (e.g., 500000)",
            "billing_cycle_start": "Day of month when bill generates (1-31)",
        },
        "user_optional_fields": {
            "network": "Card network - Default: 'Visa'. Options: Visa, Mastercard, RuPay, Amex, Diners",
            "tier_status": "Membership tiers if applicable (e.g., {'membership': 'prime'} for Amazon ICICI)",
        },
        "search_for_online": [
            "Reward rates by category (e.g., 5% on dining, 2% on all spends)",
            "Accelerated categories and platforms (e.g., 10x on SmartBuy)",
            "Monthly/yearly caps on rewards",
            "Point value and redemption options",
            "Transfer partners (airlines, hotels) and ratios",
            "Card benefits summary for description field",
        ],
        "valid_networks": ["Visa", "Mastercard", "RuPay", "Amex", "Diners"],
        "common_rewards_currencies": [
            "Reward Points",
            "Cashback",
            "Amazon Pay Balance",
            "Membership Rewards",
            "Miles",
        ],
        "behavior_rules": [
            "ALWAYS ask user for: name, bank, monthly_limit, billing_cycle_start",
            "NEVER guess the credit limit or billing date - user MUST provide",
            "Search online for reward rules, caps, and benefits",
            "Use card description to summarize key benefits for future reference",
            "If card has tiered rewards (Prime/Non-Prime), set tier_status accordingly",
        ],
        "example_flow": {
            "user_says": "Add my HDFC Regalia Gold card",
            "you_ask": "I'll help you add the HDFC Regalia Gold. I need a few details:\n1. What's your credit limit?\n2. What day does your billing cycle start (1-31)?",
            "user_provides": "Limit is 5 lakhs, billing on 15th",
            "then": "Call search_card_info('HDFC Regalia Gold', 'HDFC') to get reward rules, then call add_credit_card",
        },
    }


def _load_bank_domains() -> dict[str, str]:
    """Load bank domains from JSON file."""
    try:
        with open(BANK_DOMAINS_FILE, "r") as f:
            data = json.load(f)
            return data.get("domains", {})
    except Exception as e:
        logger.warning(f"Failed to load bank domains: {e}")
        return {}


def _get_issuer_domain(bank: str) -> str | None:
    """Get the issuer domain for a bank name."""
    domains = _load_bank_domains()
    bank_lower = bank.lower().strip()
    return domains.get(bank_lower)


def _build_card_queries(card_name: str, issuer_domain: str | None = None) -> list[dict]:
    """
    Build exhaustive search queries for credit card info.
    Returns list of {query, category, priority} dicts.
    
    Based on comprehensive analysis of 150 queries across 70+ domains.
    Prioritizes high-signal sources: TechnoFino, CardExpert, Reddit, official PDFs.
    """

    queries = []
    
    # ==================== TIER 1: OFFICIAL DOCS ====================
    if issuer_domain:
        queries.extend([
            {"query": f'site:{issuer_domain} "{card_name}" MITC filetype:pdf', "category": "official_docs", "priority": 1},
            {"query": f'site:{issuer_domain} "{card_name}" KFS filetype:pdf', "category": "official_docs", "priority": 1},
            {"query": f'site:{issuer_domain} "{card_name}" fees charges', "category": "official_docs", "priority": 1},
        ])
    queries.extend([
        {"query": f'"{card_name}" MITC filetype:pdf', "category": "official_docs", "priority": 1},
        {"query": f'"{card_name}" "Key Facts Statement" filetype:pdf', "category": "official_docs", "priority": 1},
    ])
    
    # ==================== TIER 1: COMMUNITY (BEST FOR EDGE CASES) ====================
    queries.extend([
        {"query": f'site:technofino.in "{card_name}" cap exclusion MCC', "category": "community", "priority": 1},
        {"query": f'site:technofino.in "{card_name}" devaluation rewards', "category": "community", "priority": 1},
        {"query": f'site:technofino.in "{card_name}" rupay upi threshold', "category": "community", "priority": 1},
        {"query": f'site:reddit.com/r/CreditCardsIndia "{card_name}"', "category": "community", "priority": 1},
        {"query": f'site:reddit.com/r/CreditCardsIndia "{card_name}" cap exclusion', "category": "community", "priority": 2},
    ])
    
    # ==================== TIER 1: CC REVIEW SITES ====================
    queries.extend([
        {"query": f'site:cardexpert.in "{card_name}"', "category": "cc_review", "priority": 1},
        {"query": f'site:cardinsider.com "{card_name}"', "category": "cc_review", "priority": 1},
        {"query": f'site:cardmaven.in "{card_name}"', "category": "cc_review", "priority": 2},
        {"query": f'site:rewardmatrix.in "{card_name}"', "category": "cc_review", "priority": 2},
        {"query": f'site:pointsmath.com "{card_name}"', "category": "cc_review", "priority": 2},
    ])
    
    # ==================== TIER 2: AGGREGATORS ====================
    queries.extend([
        {"query": f'site:paisabazaar.com "{card_name}"', "category": "aggregator", "priority": 2},
        {"query": f'site:bankbazaar.com "{card_name}"', "category": "aggregator", "priority": 3},
        {"query": f'site:1finance.co.in "{card_name}"', "category": "aggregator", "priority": 2},
    ])
    
    # ==================== TIER 2: FINANCIAL SITES ====================
    queries.extend([
        {"query": f'site:finology.in "{card_name}"', "category": "financial", "priority": 3},
        {"query": f'site:ourmoneyguide.com "{card_name}"', "category": "financial", "priority": 3},
        {"query": f'site:cardnitty.com "{card_name}"', "category": "financial", "priority": 3},
    ])
    
    # ==================== REWARDS MATH ====================
    queries.extend([
        {"query": f'"{card_name}" reward rate "per 100" cashback', "category": "rewards_math", "priority": 2},
        {"query": f'"{card_name}" accelerated bonus categories rewards', "category": "rewards_math", "priority": 2},
        {"query": f'"{card_name}" milestone welcome bonus rewards', "category": "rewards_math", "priority": 3},
        {"query": f'"{card_name}" expiry validity forfeiture rewards', "category": "rewards_math", "priority": 3},
    ])
    
    # ==================== CAPS & EXCLUSIONS ====================
    queries.extend([
        {"query": f'"{card_name}" cap capping maximum "per month" rewards', "category": "caps_exclusions", "priority": 1},
        {"query": f'"{card_name}" excluded exclusions MCC "not eligible"', "category": "caps_exclusions", "priority": 1},
        {"query": f'"{card_name}" fuel rent wallet insurance excluded', "category": "caps_exclusions", "priority": 2},
    ])
    
    # ==================== VARIANT / NETWORK RULES ====================
    queries.extend([
        {"query": f'"{card_name}" RuPay Visa Mastercard variant network', "category": "variant_rules", "priority": 2},
        {"query": f'"{card_name}" RuPay UPI minimum threshold "₹500"', "category": "variant_rules", "priority": 2},
        {"query": f'"{card_name}" UPI excluded "no rewards" MCC', "category": "variant_rules", "priority": 2},
    ])
    
    # ==================== REDEMPTION / TRANSFER ====================
    queries.extend([
        {"query": f'"{card_name}" redemption value "point value"', "category": "redemption", "priority": 3},
        {"query": f'"{card_name}" transfer partners airlines hotels', "category": "redemption", "priority": 3},
    ])

    return queries


@mcp.tool()
def search_card_info(card_name: str, bank: str = "", max_results: int = 15) -> dict:
    """
    Searches the web for credit card reward information using targeted DuckDuckGo queries.
    Focuses on official docs (MITC/KFS/T&Cs), reviewers, and community sources.

    Args:
        card_name: The name of the credit card (e.g., "HDFC Regalia Gold", "SBI Cashback").
        bank: Optional bank name for targeted site: searches (e.g., "HDFC", "ICICI", "Axis").
        max_results: Maximum total results to return. Default 15.

    Returns:
        dict with categorized search results (official_docs, rewards_math, caps, reviews, community).
        Use this information to extract reward rules for add_reward_rules().
    """
    try:
        # Get issuer domain for targeted searches
        issuer_domain = _get_issuer_domain(bank) if bank else None

        # Build targeted queries
        query_configs = _build_card_queries(card_name, issuer_domain)

        # Sort by priority
        query_configs.sort(key=lambda x: x["priority"])

        all_results = []
        seen_urls = set()

        with DDGS() as ddgs:
            for qc in query_configs:
                if len(all_results) >= max_results:
                    break

                try:
                    # Take top 1-2 results per query to stay focused
                    results = list(ddgs.text(qc["query"], max_results=2))
                    for r in results:
                        url = r.get("href", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(
                                {
                                    "title": r.get("title", ""),
                                    "snippet": r.get("body", ""),
                                    "url": url,
                                    "category": qc["category"],
                                    "is_pdf": url.lower().endswith(".pdf"),
                                }
                            )
                except Exception as e:
                    logger.warning(f"Query failed: {qc['query'][:50]}... - {e}")
                    continue

        if not all_results:
            return {
                "status": "warning",
                "message": f"No results found for '{card_name}'. You may need to add rules manually.",
                "results": [],
            }

        # Group by category for easier processing
        categorized = {
            "official_docs": [r for r in all_results if r["category"] == "official_docs"],
            "community": [r for r in all_results if r["category"] == "community"],
            "cc_review": [r for r in all_results if r["category"] == "cc_review"],
            "aggregator": [r for r in all_results if r["category"] == "aggregator"],
            "financial": [r for r in all_results if r["category"] == "financial"],
            "rewards_math": [r for r in all_results if r["category"] == "rewards_math"],
            "caps_exclusions": [r for r in all_results if r["category"] == "caps_exclusions"],
            "variant_rules": [r for r in all_results if r["category"] == "variant_rules"],
            "redemption": [r for r in all_results if r["category"] == "redemption"],
        }

        return {
            "status": "success",
            "card_name": card_name,
            "bank": bank or "unknown",
            "issuer_domain": issuer_domain,
            "total_results": len(all_results),
            "results_by_category": categorized,
            "all_results": all_results[:max_results],
            "extraction_guide": {
                "reward_rules": [
                    "Look for: 'X points per ₹100' or 'X% cashback'",
                    "Convert to multiplier: 5% = 0.05, 10 points per ₹100 = 0.10",
                    "Note accelerated categories: Dining, Travel, Shopping, Fuel, etc.",
                ],
                "caps": [
                    "Look for: 'maximum X points per month/statement cycle'",
                    "Note which categories have caps vs unlimited",
                ],
                "exclusions": [
                    "Look for: 'excluded MCCs', 'not eligible', 'excluded categories'",
                    "Common exclusions: Fuel, Wallet loads, Insurance, Govt payments, Rent",
                ],
                "point_value": [
                    "Look for: redemption value, '1 point = ₹X'",
                    "Note transfer partner ratios if mentioned",
                ],
            },
        }

    except Exception as e:
        logger.error(f"Error searching for card info: {e}")
        return {
            "status": "error",
            "message": f"Search failed: {str(e)}. You may need to add rules manually.",
        }


@mcp.tool()
def add_credit_card(
    name: str,
    bank: str,
    monthly_limit: float,
    billing_cycle_start: int,
    network: str = "Visa",
    rewards_currency: str = "Reward Points",
    base_point_value: float = 0.25,
    description: Optional[str] = None,
    tier_status: Optional[dict] = None,
) -> dict:
    """
    Registers a new credit card in the database with basic user-provided info.

    This is STEP 1 of adding a card. After this, call:
    - add_reward_rules() to add reward rules
    - add_cap_buckets() to add spending caps
    - add_redemption_partners() to add transfer partners

    Args:
        name: Full card name (e.g., "HDFC Regalia Gold", "SBI Cashback").
        bank: Issuing bank (e.g., "HDFC", "SBI", "ICICI").
        monthly_limit: Credit limit in INR.
        billing_cycle_start: Day of month when bill generates (1-31).
        network: Card network. Default "Visa". Options: Visa, Mastercard, RuPay, Amex, Diners.
        rewards_currency: Type of rewards. Default "Reward Points". Options: Reward Points, Cashback, Miles, etc.
        base_point_value: Value per point in INR. Default 0.25. (e.g., 0.25 means 1 point = ₹0.25).
        description: Card benefits summary (from online search). Helps LLM understand card features.
        tier_status: Membership tiers as dict (e.g., {"membership": "prime"} for Amazon ICICI Prime).

    Returns:
        dict with status, card_id (needed for adding rules), and card details.
    """
    try:
        # Validate billing_cycle_start
        if not 1 <= billing_cycle_start <= 31:
            return {
                "status": "error",
                "message": "billing_cycle_start must be between 1 and 31.",
            }

        # Validate network
        valid_networks = ["Visa", "Mastercard", "RuPay", "Amex", "Diners", "Unknown"]
        if network not in valid_networks:
            return {
                "status": "error",
                "message": f"Invalid network. Must be one of: {valid_networks}",
            }

        with Session(engine) as session:
            # Check if card with same name already exists
            existing = session.exec(
                select(CreditCard).where(col(CreditCard.name).ilike(name))
            ).first()

            if existing:
                return {
                    "status": "error",
                    "message": f"Card '{name}' already exists with ID {existing.id}. Use a different name or delete the existing card first.",
                }

            # Create the card
            card = CreditCard(
                name=name,
                bank=bank,
                network=network,
                monthly_limit=monthly_limit,
                billing_cycle_start=billing_cycle_start,
                rewards_currency=rewards_currency,
                base_point_value=base_point_value,
                description=description,
                tier_status=tier_status or {},
            )

            session.add(card)
            session.commit()
            session.refresh(card)

            logger.info(f"Added credit card: {name} (ID: {card.id})")

            return {
                "status": "success",
                "message": f"✅ Card '{name}' added successfully!",
                "card_id": card.id,
                "card": {
                    "id": card.id,
                    "name": card.name,
                    "bank": card.bank,
                    "network": card.network,
                    "monthly_limit": card.monthly_limit,
                    "billing_cycle_start": card.billing_cycle_start,
                    "rewards_currency": card.rewards_currency,
                    "base_point_value": card.base_point_value,
                },
                "next_steps": [
                    f"Call add_reward_rules(card_id={card.id}, rules=[...]) to add reward rules",
                    f"Call add_cap_buckets(card_id={card.id}, buckets=[...]) if card has caps",
                    f"Call add_redemption_partners(card_id={card.id}, partners=[...]) if card has transfer partners",
                ],
            }

    except Exception as e:
        logger.error(f"Error adding credit card: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


@mcp.tool()
def add_reward_rules(card_id: int, rules: list[dict]) -> dict:
    """
    Adds reward rules to an existing credit card. Call this AFTER add_credit_card.

    Each rule defines how points are earned for a specific category/merchant/platform.

    Args:
        card_id: The ID of the card (returned by add_credit_card).
        rules: List of rule dictionaries. Each rule should have:
            - category (str): Category name, merchant, or platform (e.g., "Dining", "Amazon", "SmartBuy")
            - base_multiplier (float): Base reward rate (e.g., 0.02 for 2%)
            - bonus_multiplier (float): Additional bonus rate (e.g., 0.03 for 3% extra). Default 0.
            - min_spend (float): Minimum spend to trigger rule. Default 0.
            - match_conditions (dict): Tier conditions (e.g., {"membership": "prime"}). Default None.
            - cap_bucket_name (str): Name of cap bucket to link. Default None.

    Returns:
        dict with status and list of created rule IDs.

    Example:
        add_reward_rules(card_id=1, rules=[
            {"category": "Dining", "base_multiplier": 0.04, "bonus_multiplier": 0.01},
            {"category": "All Spends", "base_multiplier": 0.02, "bonus_multiplier": 0},
            {"category": "SmartBuy", "base_multiplier": 0.10, "cap_bucket_name": "SmartBuy Monthly Cap"},
        ])
    """
    try:
        if not rules:
            return {"status": "error", "message": "No rules provided."}

        with Session(engine) as session:
            # Verify card exists
            card = session.get(CreditCard, card_id)
            if not card:
                return {
                    "status": "error",
                    "message": f"Card with ID {card_id} not found.",
                }

            # Get existing cap buckets for this card (for linking)
            existing_buckets = session.exec(
                select(CapBucket).where(CapBucket.card_id == card_id)
            ).all()
            bucket_map = {b.name: b.id for b in existing_buckets}

            created_rules = []
            for rule_data in rules:
                # Validate required fields
                if "category" not in rule_data:
                    return {
                        "status": "error",
                        "message": "Each rule must have a 'category' field.",
                    }
                if "base_multiplier" not in rule_data:
                    return {
                        "status": "error",
                        "message": f"Rule for '{rule_data['category']}' missing 'base_multiplier'.",
                    }

                # Find cap bucket if specified
                cap_bucket_id = None
                if "cap_bucket_name" in rule_data and rule_data["cap_bucket_name"]:
                    bucket_name = rule_data["cap_bucket_name"]
                    if bucket_name in bucket_map:
                        cap_bucket_id = bucket_map[bucket_name]
                    else:
                        return {
                            "status": "error",
                            "message": f"Cap bucket '{bucket_name}' not found. Create it first with add_cap_buckets.",
                        }

                rule = RewardRule(
                    card_id=card_id,
                    category=rule_data["category"],
                    base_multiplier=rule_data["base_multiplier"],
                    bonus_multiplier=rule_data.get("bonus_multiplier", 0.0),
                    min_spend=rule_data.get("min_spend", 0.0),
                    match_conditions=rule_data.get("match_conditions"),
                    cap_bucket_id=cap_bucket_id,
                )
                session.add(rule)
                session.flush()  # Get the ID
                created_rules.append(
                    {
                        "id": rule.id,
                        "category": rule.category,
                        "rate": f"{(rule.base_multiplier + rule.bonus_multiplier) * 100:.1f}%",
                    }
                )

            session.commit()

            return {
                "status": "success",
                "message": f"✅ Added {len(created_rules)} reward rules to {card.name}",
                "card_id": card_id,
                "rules_created": created_rules,
            }

    except Exception as e:
        logger.error(f"Error adding reward rules: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


@mcp.tool()
def add_cap_buckets(card_id: int, buckets: list[dict]) -> dict:
    """
    Adds cap buckets (spending limits) to an existing credit card.
    Call this BEFORE add_reward_rules if rules need to reference caps.

    Args:
        card_id: The ID of the card (returned by add_credit_card).
        buckets: List of bucket dictionaries. Each bucket should have:
            - name (str): Descriptive name (e.g., "SmartBuy Monthly Cap", "Dining Quarterly Cap")
            - max_points (float): Maximum points that can be earned in this bucket
            - period (str): Reset period. Options: "daily", "statement_month", "quarter", "statement_year". Default "statement_month".
            - scope (str): What the cap applies to. Options: "category", "global". Default "category".

    Returns:
        dict with status and list of created bucket IDs.

    Example:
        add_cap_buckets(card_id=1, buckets=[
            {"name": "SmartBuy Monthly Cap", "max_points": 5000, "period": "statement_month"},
            {"name": "Total Monthly Cap", "max_points": 15000, "period": "statement_month", "scope": "global"},
        ])
    """
    try:
        if not buckets:
            return {"status": "error", "message": "No buckets provided."}

        valid_periods = ["daily", "statement_month", "quarter", "statement_year"]
        valid_scopes = ["category", "global"]

        with Session(engine) as session:
            # Verify card exists
            card = session.get(CreditCard, card_id)
            if not card:
                return {
                    "status": "error",
                    "message": f"Card with ID {card_id} not found.",
                }

            created_buckets = []
            for bucket_data in buckets:
                # Validate required fields
                if "name" not in bucket_data:
                    return {
                        "status": "error",
                        "message": "Each bucket must have a 'name' field.",
                    }
                if "max_points" not in bucket_data:
                    return {
                        "status": "error",
                        "message": f"Bucket '{bucket_data['name']}' missing 'max_points'.",
                    }

                # Validate period
                period_str = bucket_data.get("period", "statement_month")
                if period_str not in valid_periods:
                    return {
                        "status": "error",
                        "message": f"Invalid period '{period_str}'. Must be one of: {valid_periods}",
                    }

                # Validate scope
                scope_str = bucket_data.get("scope", "category")
                if scope_str not in valid_scopes:
                    return {
                        "status": "error",
                        "message": f"Invalid scope '{scope_str}'. Must be one of: {valid_scopes}",
                    }

                bucket = CapBucket(
                    card_id=card_id,
                    name=bucket_data["name"],
                    max_points=bucket_data["max_points"],
                    period=PeriodType(period_str),
                    bucket_scope=BucketScope(scope_str),
                )
                session.add(bucket)
                session.flush()
                created_buckets.append(
                    {
                        "id": bucket.id,
                        "name": bucket.name,
                        "max_points": bucket.max_points,
                        "period": period_str,
                    }
                )

            session.commit()

            return {
                "status": "success",
                "message": f"✅ Added {len(created_buckets)} cap buckets to {card.name}",
                "card_id": card_id,
                "buckets_created": created_buckets,
            }

    except Exception as e:
        logger.error(f"Error adding cap buckets: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


@mcp.tool()
def add_redemption_partners(card_id: int, partners: list[dict]) -> dict:
    """
    Adds redemption/transfer partners to an existing credit card.
    These are airlines, hotels, or other programs where points can be transferred.

    Args:
        card_id: The ID of the card (returned by add_credit_card).
        partners: List of partner dictionaries. Each should have:
            - partner_name (str): Name of the partner (e.g., "Singapore Airlines", "Marriott")
            - transfer_ratio (float): Points needed per 1 partner point (e.g., 2.0 means 2 card points = 1 mile)
            - estimated_value (float): Estimated value per partner point in INR (e.g., 1.5 for airline miles)

    Returns:
        dict with status and list of created partner IDs.

    Example:
        add_redemption_partners(card_id=1, partners=[
            {"partner_name": "Singapore Airlines", "transfer_ratio": 1.0, "estimated_value": 1.50},
            {"partner_name": "Marriott Bonvoy", "transfer_ratio": 2.0, "estimated_value": 0.80},
        ])
    """
    try:
        if not partners:
            return {"status": "error", "message": "No partners provided."}

        with Session(engine) as session:
            # Verify card exists
            card = session.get(CreditCard, card_id)
            if not card:
                return {
                    "status": "error",
                    "message": f"Card with ID {card_id} not found.",
                }

            created_partners = []
            for partner_data in partners:
                # Validate required fields
                if "partner_name" not in partner_data:
                    return {
                        "status": "error",
                        "message": "Each partner must have a 'partner_name' field.",
                    }
                if "transfer_ratio" not in partner_data:
                    return {
                        "status": "error",
                        "message": f"Partner '{partner_data['partner_name']}' missing 'transfer_ratio'.",
                    }
                if "estimated_value" not in partner_data:
                    return {
                        "status": "error",
                        "message": f"Partner '{partner_data['partner_name']}' missing 'estimated_value'.",
                    }

                partner = RedemptionPartner(
                    card_id=card_id,
                    partner_name=partner_data["partner_name"],
                    transfer_ratio=partner_data["transfer_ratio"],
                    estimated_value=partner_data["estimated_value"],
                )
                session.add(partner)
                session.flush()
                created_partners.append(
                    {
                        "id": partner.id,
                        "name": partner.partner_name,
                        "ratio": f"{partner.transfer_ratio}:1",
                        "value": f"₹{partner.estimated_value}/point",
                    }
                )

            session.commit()

            return {
                "status": "success",
                "message": f"✅ Added {len(created_partners)} transfer partners to {card.name}",
                "card_id": card_id,
                "partners_created": created_partners,
            }

    except Exception as e:
        logger.error(f"Error adding redemption partners: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


# ----------------- The Points System -----------------
#       This tracks your points earned per card
# -----------------------------------------------------


@mcp.tool()
def get_reward_balance(card_name: str) -> dict:
    """
    Checks the current accumulated reward points for a specific card.

    Args:
        card_name: The name of the card to check.

    Returns:
        Dictionary with total points, period breakdown, and card details.
    """
    try:
        with Session(engine) as session:
            query = select(CreditCard).where(
                col(CreditCard.name).ilike(f"%{card_name}%")
            )
            cards = session.exec(query).all()

            if not cards:
                return {"status": "error", "message": f"Card '{card_name}' not found."}

            if len(cards) > 1:
                return {
                    "status": "error",
                    "message": "Multiple cards found. Please be specific.",
                    "matches": [{"id": c.id, "name": c.name} for c in cards],
                }

            card = cards[0]

            # Get total points earned all time
            total_points = (
                session.exec(
                    select(func.sum(Expense.points_earned)).where(
                        Expense.card_id == card.id
                    )
                ).first()
                or 0.0
            )

            # Get points this month
            now = datetime.now()
            month_start = datetime(now.year, now.month, 1)
            monthly_points = (
                session.exec(
                    select(func.sum(Expense.points_earned)).where(
                        Expense.card_id == card.id,
                        Expense.date >= month_start,
                    )
                ).first()
                or 0.0
            )

            # Get transaction count
            tx_count = (
                session.exec(
                    select(func.count(Expense.id)).where(Expense.card_id == card.id)
                ).first()
                or 0
            )

            # Get total adjustments (bonuses - redemptions)
            total_adjustments = (
                session.exec(
                    select(func.sum(PointAdjustment.amount)).where(
                        PointAdjustment.card_id == card.id
                    )
                ).first()
                or 0.0
            )

            current_balance = total_points + total_adjustments

            return {
                "status": "success",
                "card": {
                    "id": card.id,
                    "name": card.name,
                    "bank": card.bank,
                    "rewards_currency": card.rewards_currency,
                    "point_value": card.base_point_value,
                },
                "balance": {
                    "total_earned": round(total_points, 2),
                    "total_adjustments": round(total_adjustments, 2),
                    "current_balance": round(current_balance, 2),
                    "estimated_value": round(
                        current_balance * card.base_point_value, 2
                    ),
                    "earned_this_month": round(monthly_points, 2),
                    "transaction_count": tx_count,
                },
            }

    except Exception as e:
        logger.error(f"Error getting reward balance: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def adjust_reward_points(
    card_name: str,
    points: float,
    reason: str,
    adjustment_type: str = "correction",
    reference: Optional[str] = None,
) -> dict:
    """
    Adjusts the point balance for a card. Use for redemptions, bonuses, or corrections.

    Args:
        card_name: The card to adjust.
        points: Points to add (+ve) or remove (-ve). Use negative for redemptions.
        reason: Description (e.g., "Redeemed for Amazon voucher", "Welcome bonus").
        adjustment_type: One of: redemption, signup_bonus, referral, promo, correction, expiration.
        reference: Optional reference (order ID, promo code).

    Returns:
        Dictionary with adjustment details and new balance.
    """
    try:
        # Validate adjustment type
        valid_types = [
            "redemption",
            "signup_bonus",
            "referral",
            "promo",
            "correction",
            "expiration",
        ]
        if adjustment_type not in valid_types:
            return {
                "status": "error",
                "message": f"Invalid adjustment_type. Must be one of: {valid_types}",
            }

        with Session(engine) as session:
            # Find the card
            query = select(CreditCard).where(
                col(CreditCard.name).ilike(f"%{card_name}%")
            )
            cards = session.exec(query).all()

            if not cards:
                return {"status": "error", "message": f"Card '{card_name}' not found."}

            if len(cards) > 1:
                return {
                    "status": "error",
                    "message": "Multiple cards found. Please be specific.",
                    "matches": [{"id": c.id, "name": c.name} for c in cards],
                }

            card = cards[0]

            # Create the adjustment
            adjustment = PointAdjustment(
                card_id=card.id,
                amount=points,
                adjustment_type=AdjustmentType(adjustment_type),
                description=reason,
                reference=reference,
            )
            session.add(adjustment)
            session.commit()
            session.refresh(adjustment)

            # Calculate new balance
            total_earned = (
                session.exec(
                    select(func.sum(Expense.points_earned)).where(
                        Expense.card_id == card.id
                    )
                ).first()
                or 0.0
            )

            total_adjustments = (
                session.exec(
                    select(func.sum(PointAdjustment.amount)).where(
                        PointAdjustment.card_id == card.id
                    )
                ).first()
                or 0.0
            )

            new_balance = total_earned + total_adjustments

            return {
                "status": "success",
                "message": f"Points adjusted: {'+' if points >= 0 else ''}{points}",
                "adjustment": {
                    "id": adjustment.id,
                    "type": adjustment_type,
                    "amount": points,
                    "description": reason,
                    "reference": reference,
                    "date": adjustment.date.strftime("%Y-%m-%d %H:%M"),
                },
                "balance": {
                    "total_earned": round(total_earned, 2),
                    "total_adjustments": round(total_adjustments, 2),
                    "current_balance": round(new_balance, 2),
                },
            }

    except Exception as e:
        logger.error(f"Error adjusting points: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_card_description(card_id: int) -> dict:
    """
    Retrieves the description and key details of a credit card.
    Useful for understanding card benefits before making a purchase decision.

    Args:
        card_id: The ID of the credit card.

    Returns:
        Dictionary with card name, description, tier status, and reward info.
    """
    try:
        with Session(engine) as session:
            card = session.get(CreditCard, card_id)

            if not card:
                return {
                    "status": "error",
                    "message": f"Card with ID {card_id} not found.",
                }

            return {
                "status": "success",
                "card": {
                    "id": card.id,
                    "name": card.name,
                    "bank": card.bank,
                    "network": card.network,
                    "description": card.description or "No description available.",
                    "tier_status": card.tier_status or {},
                    "rewards_currency": card.rewards_currency,
                    "point_value": card.base_point_value,
                    "billing_cycle_start": card.billing_cycle_start,
                },
            }

    except Exception as e:
        logger.error(f"Error getting card description: {e}")
        return {"status": "error", "message": str(e)}


# ======================= CARD RECOMMENDATION =======================
# Tool to find the best card for a purchase
# ====================================================================


@mcp.tool()
def get_best_card_for_purchase(
    amount: float,
    merchant: str,
    category: str,
    platform: str = "Direct",
) -> dict:
    """
    Finds the BEST credit card to use for a specific purchase.

    Call this tool when user asks:
    - "Which card should I use for X?"
    - "What's the best card for this purchase?"
    - "How can I maximize rewards on X?"

    Args:
        amount: Purchase amount in INR (e.g., 5000)
        merchant: Where the purchase is being made (e.g., "Amazon", "Swiggy", "MakeMyTrip")
        category: Purchase category. Use valid categories from get_expense_logging_rules.
        platform: Payment platform (Default: "Direct"). Options: Direct, SmartBuy, Amazon Pay, CRED

    Returns:
        dict containing recommendations and guidelines for interpreting/presenting results.
    """
    try:
        with Session(engine) as session:
            results = recommend_all_cards(
                session,
                amount=amount,
                merchant=merchant,
                category=category,
                platform=platform,
            )

            if not results:
                return {
                    "status": "error",
                    "message": "No cards found in wallet. Add cards first using add_credit_card.",
                }

            # Pre-formatted comparison for easy display
            quick_comparison = []
            for card in results[:5]:
                quick_comparison.append({
                    "rank": card["rank"],
                    "card": f"{card['card_name']} ({card['bank']})",
                    "points": f"{card['points']['total']:,.0f}",
                    "multiplier": f"{card['multipliers']['effective']}x",
                    "best_value": f"₹{card['cash_value']['best_value']:,.0f}",
                    "best_via": card["cash_value"]["best_partner"],
                    "cashback_value": f"₹{card['cash_value']['base_value']:,.0f}",
                    "warning": card["cap_status"]["warning"],
                })

            return {
                "status": "success",
                "purchase": f"₹{amount:,.0f} {merchant} ({category})",
                "recommendation_count": len(results),
                "best_card": results[0] if results else None,
                "quick_comparison": quick_comparison,
                "all_recommendations": results,
                "understanding_the_results": {
                    "card_name": "Card identification",
                    "points.total": "Raw points earned (base + bonus)",
                    "multipliers.effective": "Earn rate (e.g., 5.0x = 5 points per ₹1)",
                    "matched_rule": "Which reward rule triggered (e.g., 'Shopping', 'Dining')",
                    "cash_value.best_value": "**PRIMARY METRIC** - Maximum ₹ value achievable",
                    "cash_value.best_partner": "How to redeem for maximum value",
                    "cash_value.base_value": "Direct cashback value (simpler redemption)",
                    "cap_status.warning": "Warning message if near cap limit",
                    "rank": "1 = best, 2 = second best, etc.",
                },
                "how_to_respond": {
                    "format": "Present recommendation clearly, then optionally show comparison",
                    "1_recommendation": "Use [card_name] for this ₹[amount] [category] purchase",
                    "2_reason": "You'll earn [points] points ([multiplier]x rate) worth ₹[best_value]",
                    "3_redemption": "Redeem via [best_partner] for maximum value",
                    "4_alternative": "If rank 2 is close in value, mention it",
                    "5_warning": "Include cap_status.warning if present",
                },
                "example_responses": [
                    {
                        "scenario": "Simple Purchase",
                        "response": "For this ₹5,000 Amazon purchase, use your **HDFC Infinia**.\nYou'll earn 25,000 points (5x rate) worth **₹50,000** via Marriott Bonvoy.\nAlternative: HDFC Regalia Gold gives ₹49,000 value.",
                    },
                    {
                        "scenario": "With Cap Warning",
                        "response": "Use **Axis Ace** for this ₹4,000 utility bill — earns 8,500 points worth ₹8,500.\n⚠️ Note: You've used 85% of your monthly bonus cap.",
                    },
                    {
                        "scenario": "Comparison List (if user asks to compare)",
                        "response": "For ₹5,000 Amazon Shopping:\n\n1. **HDFC Infinia** → ₹50,000 (via Marriott Bonvoy) ✅ BEST\n2. HDFC Regalia Gold → ₹49,000 (via Marriott Bonvoy)\n3. IDFC First Select → ₹22,500 (via Club Vistara)\n\nRecommendation: Use HDFC Infinia for maximum value.",
                    },
                ],
                "behavior_rules": [
                    "Always recommend the #1 ranked card (highest best_value)",
                    "Mention the redemption partner for maximum value",
                    "If best_partner is NOT 'Direct Cashback', also mention cashback_value as simpler alternative",
                    "Include alternative card if rank 2 is within 20% of rank 1 value",
                    "Always include warning if present",
                    "Format amounts with ₹ and commas (e.g., ₹50,000)",
                    "Use quick_comparison for formatted display when user asks to compare cards",
                ],
            }

    except Exception as e:
        logger.error(f"Error in card recommendation: {e}")
        return {"status": "error", "message": str(e)}


# ======================= EXPENSE ANALYSIS =======================
# Tool to analyze spending patterns and reward efficiency
# ================================================================


@mcp.tool()
def analyze_expenses(
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Analyzes spending patterns and reward earnings for a given period.

    Call this tool when user asks:
    - "How did I spend this month?"
    - "Show me my spending summary"
    - "What's my reward rate?"
    - "Where is my money going?"

    Args:
        period: Time period to analyze. Options: "week", "month", "quarter", "year"
                Ignored if start_date/end_date provided.
        start_date: Custom start date (YYYY-MM-DD). Optional.
        end_date: Custom end date (YYYY-MM-DD). Optional.

    Returns:
        dict with spending summary, category breakdown, card usage, and insights.
    """
    try:
        with Session(engine) as session:
            # Determine date range
            today = datetime.now().date()

            if start_date and end_date:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                period_label = f"{start_date} to {end_date}"
            else:
                if period == "week":
                    start = today - timedelta(days=7)
                    period_label = "Last 7 days"
                elif period == "quarter":
                    start = today - timedelta(days=90)
                    period_label = "Last 90 days"
                elif period == "year":
                    start = today - timedelta(days=365)
                    period_label = "Last 365 days"
                else:  # default: month
                    start = today - timedelta(days=30)
                    period_label = "Last 30 days"
                end = today

            # Query expenses in date range
            query = (
                select(Expense)
                .join(CreditCard)
                .where(Expense.date >= start)
                .where(Expense.date <= end)
            )
            expenses = list(session.exec(query).all())

            if not expenses:
                return {
                    "status": "success",
                    "period": period_label,
                    "message": "No transactions found for this period.",
                    "summary": {
                        "total_spend": 0,
                        "transaction_count": 0,
                        "total_points": 0,
                    },
                }

            # Calculate totals
            total_spend = sum(e.amount for e in expenses)
            total_points = sum(e.points_earned or 0 for e in expenses)
            transaction_count = len(expenses)
            avg_transaction = total_spend / transaction_count if transaction_count else 0

            # Category breakdown
            category_spend = {}
            category_points = {}
            for e in expenses:
                cat = e.category or "Uncategorized"
                category_spend[cat] = category_spend.get(cat, 0) + e.amount
                category_points[cat] = category_points.get(cat, 0) + (e.points_earned or 0)

            # Sort by spend descending
            sorted_categories = sorted(
                category_spend.items(), key=lambda x: x[1], reverse=True
            )

            category_breakdown = []
            for cat, spend in sorted_categories:
                points = category_points.get(cat, 0)
                pct = (spend / total_spend * 100) if total_spend else 0
                category_breakdown.append({
                    "category": cat,
                    "spend": f"₹{spend:,.0f}",
                    "spend_raw": spend,
                    "points": f"{points:,.0f}",
                    "percent_of_total": f"{pct:.1f}%",
                })

            # Card usage breakdown
            card_spend = {}
            card_points = {}
            card_names = {}
            for e in expenses:
                cid = e.card_id
                card_spend[cid] = card_spend.get(cid, 0) + e.amount
                card_points[cid] = card_points.get(cid, 0) + (e.points_earned or 0)
                if cid not in card_names and e.card:
                    card_names[cid] = f"{e.card.name} ({e.card.bank})"

            sorted_cards = sorted(
                card_spend.items(), key=lambda x: x[1], reverse=True
            )

            card_breakdown = []
            for cid, spend in sorted_cards:
                points = card_points.get(cid, 0)
                pct = (spend / total_spend * 100) if total_spend else 0
                card_breakdown.append({
                    "card": card_names.get(cid, f"Card {cid}"),
                    "spend": f"₹{spend:,.0f}",
                    "spend_raw": spend,
                    "points": f"{points:,.0f}",
                    "percent_of_total": f"{pct:.1f}%",
                })

            # Calculate effective reward rate
            # Estimate value: use average base_point_value across cards
            cards = list(session.exec(select(CreditCard)).all())
            avg_point_value = sum(c.base_point_value for c in cards) / len(cards) if cards else 0.30
            estimated_value = total_points * avg_point_value
            effective_rate = (estimated_value / total_spend * 100) if total_spend else 0

            # Top merchants
            merchant_spend = {}
            for e in expenses:
                m = e.merchant or "Unknown"
                merchant_spend[m] = merchant_spend.get(m, 0) + e.amount

            top_merchants = sorted(
                merchant_spend.items(), key=lambda x: x[1], reverse=True
            )[:5]

            return {
                "status": "success",
                "period": period_label,
                "summary": {
                    "total_spend": f"₹{total_spend:,.0f}",
                    "total_spend_raw": total_spend,
                    "transaction_count": transaction_count,
                    "avg_transaction": f"₹{avg_transaction:,.0f}",
                    "total_points": f"{total_points:,.0f}",
                    "estimated_value": f"₹{estimated_value:,.0f}",
                    "effective_reward_rate": f"{effective_rate:.2f}%",
                },
                "top_categories": category_breakdown[:5],
                "all_categories": category_breakdown,
                "card_usage": card_breakdown,
                "top_merchants": [
                    {"merchant": m, "spend": f"₹{s:,.0f}"} for m, s in top_merchants
                ],
                "how_to_present": {
                    "headline": f"In {period_label}, you spent {total_spend:,.0f} across {transaction_count} transactions",
                    "highlight_1": "Top category and spend from top_categories[0]",
                    "highlight_2": "Most used card from card_usage[0]",
                    "highlight_3": f"Earned {total_points:,.0f} points worth ~₹{estimated_value:,.0f}",
                    "reward_insight": f"Effective reward rate is {effective_rate:.2f}%",
                },
            }

    except Exception as e:
        logger.error(f"Error analyzing expenses: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run()
