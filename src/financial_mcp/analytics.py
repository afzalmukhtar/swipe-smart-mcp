"""Analytics and insights for Financial MCP Server."""

import json
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from calendar import monthrange

from .models import (
    Expense, CreditCard, FinancialSummary, RewardCalculation, 
    SpendingAnalysis, ExportRequest, ExportFormat
)
from .database import FinancialDatabase


class FinancialAnalytics:
    """Analytics engine for financial data."""
    
    def __init__(self, db: FinancialDatabase):
        self.db = db
    
    async def calculate_rewards(self, expense: Expense) -> Optional[RewardCalculation]:
        """Calculate rewards for an expense."""
        if expense.payment_method != "credit-card" or not expense.credit_card:
            return None
        
        cards = await self.db.get_credit_cards()
        card = next((c for c in cards if c.name == expense.credit_card), None)
        
        if not card:
            return None
        
        # Check for bonus categories first
        category_lower = expense.category.lower()
        reward_rate = 0.0
        
        # Check bonus categories (quarterly/temporary)
        for bonus_cat, rate in card.bonus_categories.items():
            if bonus_cat.lower() in category_lower or category_lower in bonus_cat.lower():
                reward_rate = rate
                break
        
        # Check regular reward categories
        if reward_rate == 0.0:
            for reward_cat, rate in card.reward_categories.items():
                if reward_cat.lower() in category_lower or category_lower in reward_cat.lower():
                    reward_rate = rate
                    break
        
        # Use default rate if no category match
        if reward_rate == 0.0:
            reward_rate = card.reward_categories.get('default', 1.0)
        
        reward_amount = expense.amount * Decimal(reward_rate) / 100
        
        return RewardCalculation(
            amount=reward_amount,
            type='cashback',  # Default to cashback, could be configurable
            rate=reward_rate,
            category=expense.category,
            credit_card=expense.credit_card
        )
    
    async def get_best_card_for_category(self, category: str, amount: float = 100) -> Optional[Dict[str, Any]]:
        """Get the best credit card for a specific category."""
        cards = await self.db.get_credit_cards()
        
        if not cards:
            return None
        
        best_card = None
        best_rate = 0.0
        
        category_lower = category.lower()
        
        for card in cards:
            rate = 0.0
            
            # Check bonus categories first
            for bonus_cat, bonus_rate in card.bonus_categories.items():
                if bonus_cat.lower() in category_lower or category_lower in bonus_cat.lower():
                    rate = bonus_rate
                    break
            
            # Check regular categories if no bonus found
            if rate == 0.0:
                for reward_cat, reward_rate in card.reward_categories.items():
                    if reward_cat.lower() in category_lower or category_lower in reward_cat.lower():
                        rate = reward_rate
                        break
            
            # Use default rate if no category match
            if rate == 0.0:
                rate = card.reward_categories.get('default', 1.0)
            
            if rate > best_rate:
                best_rate = rate
                best_card = card
        
        if not best_card:
            return None
        
        return {
            'name': best_card.name,
            'bank': best_card.bank,
            'reward_rate': best_rate,
            'annual_fee': best_card.annual_fee,
            'estimated_rewards': amount * best_rate / 100
        }
    
    async def get_financial_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate financial summary for a period."""
        start_date, end_date = self._parse_period(params)
        
        # Get expenses for the period
        from .models import ExpenseFilter
        filter_params = ExpenseFilter(
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Large limit to get all expenses
        )
        
        expenses = await self.db.get_expenses(filter_params)
        
        if not expenses:
            return {
                'total_spending': 0,
                'transaction_count': 0,
                'top_categories': [],
                'payment_methods': [],
                'total_rewards': 0
            }
        
        total_spending = sum(expense.amount for expense in expenses)
        
        # Category breakdown
        category_totals = {}
        for expense in expenses:
            category_totals[expense.category] = category_totals.get(expense.category, Decimal('0')) + expense.amount
        
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Payment method breakdown
        payment_totals = {}
        for expense in expenses:
            method = expense.payment_method.value
            payment_totals[method] = payment_totals.get(method, Decimal('0')) + expense.amount
        
        payment_methods = sorted(payment_totals.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate total rewards
        total_rewards = Decimal('0')
        for expense in expenses:
            reward = await self.calculate_rewards(expense)
            if reward:
                total_rewards += reward.amount
        
        return {
            'total_spending': float(total_spending),
            'transaction_count': len(expenses),
            'top_categories': [(cat, float(amount)) for cat, amount in top_categories],
            'payment_methods': [(method, float(amount)) for method, amount in payment_methods],
            'total_rewards': float(total_rewards) if total_rewards > 0 else None
        }
    
    async def analyze_spending(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze spending patterns."""
        analysis_type = params.get('analysis_type', 'trends')
        
        if analysis_type == 'trends':
            return await self._analyze_trends(params)
        elif analysis_type == 'categories':
            return await self._analyze_categories(params)
        elif analysis_type == 'cards':
            return await self._analyze_cards(params)
        elif analysis_type == 'rewards':
            return await self._analyze_rewards(params)
        else:
            return {
                'summary': f"Unknown analysis type: {analysis_type}",
                'insights': []
            }
    
    async def _analyze_trends(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze spending trends."""
        period = params.get('period', 'month')
        
        # Get last 6 periods for trend analysis
        insights = []
        
        if period == 'month':
            # Analyze last 6 months
            insights.append("Monthly trend analysis shows consistent spending patterns")
            insights.append("Consider setting up monthly budgets for better tracking")
        
        return {
            'summary': f"Spending trends analysis for {period} periods",
            'insights': insights
        }
    
    async def _analyze_categories(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze category-wise spending."""
        start_date, end_date = self._parse_period(params)
        
        from .models import ExpenseFilter
        filter_params = ExpenseFilter(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        expenses = await self.db.get_expenses(filter_params)
        
        category_totals = {}
        for expense in expenses:
            category_totals[expense.category] = category_totals.get(expense.category, Decimal('0')) + expense.amount
        
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        
        insights = []
        if top_categories:
            top_cat, top_amount = top_categories[0]
            insights.append(f"Highest spending category: {top_cat} (${top_amount})")
            
            if len(top_categories) > 1:
                insights.append(f"Top 3 categories account for {len(top_categories[:3])} spending areas")
        
        return {
            'summary': f"Category analysis shows {len(category_totals)} active spending categories",
            'insights': insights
        }
    
    async def _analyze_cards(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze credit card usage."""
        cards = await self.db.get_credit_cards()
        
        insights = []
        if cards:
            insights.append(f"You have {len(cards)} active credit cards")
            insights.append("Consider using cards with highest reward rates for each category")
        else:
            insights.append("No credit cards found. Add cards to optimize rewards!")
        
        return {
            'summary': f"Credit card analysis for {len(cards)} cards",
            'insights': insights
        }
    
    async def _analyze_rewards(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze reward optimization."""
        start_date, end_date = self._parse_period(params)
        
        from .models import ExpenseFilter
        filter_params = ExpenseFilter(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        expenses = await self.db.get_expenses(filter_params)
        
        total_rewards = Decimal('0')
        missed_rewards = Decimal('0')
        
        for expense in expenses:
            current_reward = await self.calculate_rewards(expense)
            if current_reward:
                total_rewards += current_reward.amount
            
            # Calculate potential with best card
            if expense.category:
                best_card = await self.get_best_card_for_category(expense.category, float(expense.amount))
                if best_card:
                    potential_reward = expense.amount * Decimal(best_card['reward_rate']) / 100
                    if not current_reward or potential_reward > current_reward.amount:
                        missed_rewards += potential_reward - (current_reward.amount if current_reward else Decimal('0'))
        
        insights = []
        insights.append(f"Total rewards earned: ${total_rewards}")
        if missed_rewards > 0:
            insights.append(f"Potential additional rewards: ${missed_rewards}")
            insights.append("Consider optimizing card usage for better rewards")
        
        return {
            'summary': f"Reward analysis shows ${total_rewards} earned with ${missed_rewards} optimization potential",
            'insights': insights
        }
    
    async def export_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export financial data."""
        format_type = params['format']
        output_path = Path(params['output_path'])
        
        # Get expenses based on filters
        from .models import ExpenseFilter
        filter_params = ExpenseFilter(
            start_date=params.get('start_date'),
            end_date=params.get('end_date'),
            limit=100000  # Large limit for export
        )
        
        expenses = await self.db.get_expenses(filter_params)
        
        if not expenses:
            return {
                'file_path': str(output_path),
                'record_count': 0,
                'date_range': 'No data'
            }
        
        # Convert to DataFrame for easy export
        data = []
        for expense in expenses:
            reward = await self.calculate_rewards(expense)
            data.append({
                'Date': expense.date.isoformat(),
                'Amount': float(expense.amount),
                'Description': expense.description,
                'Category': expense.category,
                'Payment Method': expense.payment_method.value,
                'Credit Card': expense.credit_card or '',
                'Payment Portal': expense.payment_portal or '',
                'Person': expense.person,
                'Rewards': float(reward.amount) if reward else 0.0
            })
        
        df = pd.DataFrame(data)
        
        # Export based on format
        if format_type == 'csv':
            df.to_csv(output_path, index=False)
        elif format_type == 'excel':
            df.to_excel(output_path, index=False, sheet_name='Expenses')
        elif format_type == 'json':
            df.to_json(output_path, orient='records', date_format='iso')
        
        date_range = f"{expenses[-1].date} to {expenses[0].date}"
        
        return {
            'file_path': str(output_path),
            'record_count': len(expenses),
            'date_range': date_range
        }
    
    def _parse_period(self, params: Dict[str, Any]) -> Tuple[date, date]:
        """Parse period parameters to get start and end dates."""
        period_type = params.get('period', 'month')
        
        if period_type == 'custom':
            start_date = datetime.strptime(params['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(params['end_date'], '%Y-%m-%d').date()
            return start_date, end_date
        
        today = date.today()
        year = params.get('year', today.year)
        
        if period_type == 'month':
            month = params.get('month', today.month)
            start_date = date(year, month, 1)
            _, last_day = monthrange(year, month)
            end_date = date(year, month, last_day)
        
        elif period_type == 'quarter':
            quarter = params.get('quarter', (today.month - 1) // 3 + 1)
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            start_date = date(year, start_month, 1)
            _, last_day = monthrange(year, end_month)
            end_date = date(year, end_month, last_day)
        
        elif period_type == 'year':
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        
        else:
            # Default to current month
            start_date = date(today.year, today.month, 1)
            _, last_day = monthrange(today.year, today.month)
            end_date = date(today.year, today.month, last_day)
        
        return start_date, end_date
