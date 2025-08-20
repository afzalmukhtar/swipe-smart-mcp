"""Database operations for Financial MCP Server."""

import sqlite3
import aiosqlite
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

from .models import Expense, CreditCard, ExpenseFilter, Configuration


class FinancialDatabase:
    """SQLite database manager for financial data."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        if db_path is None:
            # Default to user's home directory
            home = Path.home()
            self.db_path = home / ".financial_mcp" / "financial.db"
            self.db_path.parent.mkdir(exist_ok=True)
        else:
            self.db_path = Path(db_path)
    
    async def initialize(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await self._create_indexes(db)
            await db.commit()
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create database tables."""
        
        # Expenses table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount DECIMAL(10,2) NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                credit_card TEXT,
                payment_portal TEXT,
                person TEXT NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Credit cards table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS credit_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                bank TEXT NOT NULL,
                reward_categories TEXT NOT NULL,  -- JSON
                annual_fee DECIMAL(10,2) DEFAULT 0,
                bonus_categories TEXT DEFAULT '{}',  -- JSON
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Configuration table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS configuration (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection):
        """Create database indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)",
            "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",
            "CREATE INDEX IF NOT EXISTS idx_expenses_payment_method ON expenses(payment_method)",
            "CREATE INDEX IF NOT EXISTS idx_expenses_person ON expenses(person)",
            "CREATE INDEX IF NOT EXISTS idx_credit_cards_name ON credit_cards(name)",
        ]
        
        for index in indexes:
            await db.execute(index)
    
    async def add_expense(self, expense_data: Dict[str, Any]) -> Expense:
        """Add a new expense."""
        expense = Expense(**expense_data)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO expenses 
                (amount, description, category, payment_method, credit_card, 
                 payment_portal, person, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                float(expense.amount),
                expense.description,
                expense.category,
                expense.payment_method.value,
                expense.credit_card,
                expense.payment_portal,
                expense.person,
                expense.date.isoformat()
            ))
            
            expense.id = cursor.lastrowid
            await db.commit()
        
        return expense
    
    async def get_expenses(self, filter_params: ExpenseFilter) -> List[Expense]:
        """Get expenses with filtering."""
        query = "SELECT * FROM expenses WHERE 1=1"
        params = []
        
        if filter_params.category:
            query += " AND category = ?"
            params.append(filter_params.category)
        
        if filter_params.payment_method:
            query += " AND payment_method = ?"
            params.append(filter_params.payment_method.value)
        
        if filter_params.person:
            query += " AND person = ?"
            params.append(filter_params.person)
        
        if filter_params.start_date:
            query += " AND date >= ?"
            params.append(filter_params.start_date.isoformat())
        
        if filter_params.end_date:
            query += " AND date <= ?"
            params.append(filter_params.end_date.isoformat())
        
        if filter_params.month:
            query += " AND strftime('%Y-%m', date) = ?"
            params.append(filter_params.month)
        
        query += " ORDER BY date DESC, created_at DESC"
        query += f" LIMIT {filter_params.limit}"
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        
        expenses = []
        for row in rows:
            expense_dict = dict(row)
            expense_dict['amount'] = Decimal(str(expense_dict['amount']))
            expense_dict['date'] = datetime.strptime(expense_dict['date'], '%Y-%m-%d').date()
            expenses.append(Expense(**expense_dict))
        
        return expenses
    
    async def add_credit_card(self, card_data: Dict[str, Any]) -> CreditCard:
        """Add a new credit card."""
        card = CreditCard(**card_data)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO credit_cards 
                (name, bank, reward_categories, annual_fee, bonus_categories)
                VALUES (?, ?, ?, ?, ?)
            """, (
                card.name,
                card.bank,
                json.dumps(card.reward_categories),
                float(card.annual_fee),
                json.dumps(card.bonus_categories)
            ))
            
            card.id = cursor.lastrowid
            await db.commit()
        
        return card
    
    async def get_credit_cards(self, active_only: bool = True) -> List[CreditCard]:
        """Get credit cards."""
        query = "SELECT * FROM credit_cards"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
        
        cards = []
        for row in rows:
            card_dict = dict(row)
            card_dict['reward_categories'] = json.loads(card_dict['reward_categories'])
            card_dict['bonus_categories'] = json.loads(card_dict['bonus_categories'])
            card_dict['annual_fee'] = Decimal(str(card_dict['annual_fee']))
            cards.append(CreditCard(**card_dict))
        
        return cards
    
    async def get_configuration(self) -> Dict[str, Any]:
        """Get configuration settings."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT key, value FROM configuration")
            rows = await cursor.fetchall()
        
        config = {}
        for row in rows:
            try:
                config[row['key']] = json.loads(row['value'])
            except json.JSONDecodeError:
                config[row['key']] = row['value']
        
        # Return default configuration if empty
        if not config:
            default_config = Configuration()
            return default_config.dict()
        
        return config
    
    async def set_configuration(self, key: str, value: Any):
        """Set a configuration value."""
        json_value = json.dumps(value) if not isinstance(value, str) else value
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO configuration (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json_value))
            await db.commit()
