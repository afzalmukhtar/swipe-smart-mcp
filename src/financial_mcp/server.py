"""Financial MCP Server - Main server implementation."""

import asyncio
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel,
)
from pydantic import BaseModel

from .database import FinancialDatabase
from .models import Expense, CreditCard, ExpenseFilter
from .analytics import FinancialAnalytics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FinancialMCPServer:
    """Financial MCP Server for expense tracking and credit card optimization."""
    
    def __init__(self):
        self.server = Server("financial-mcp-server")
        self.db = FinancialDatabase()
        self.analytics = FinancialAnalytics(self.db)
        self._setup_tools()
        self._setup_resources()
    
    def _setup_tools(self):
        """Set up all available MCP tools."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available financial tools."""
            return [
                Tool(
                    name="add_expense",
                    description="Add a new expense with automatic categorization and reward tracking",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Expense amount"},
                            "description": {"type": "string", "description": "Expense description"},
                            "category": {"type": "string", "description": "Expense category (optional, auto-detected if not provided)"},
                            "payment_method": {"type": "string", "description": "Payment method (cash, credit-card, upi, etc.)"},
                            "credit_card": {"type": "string", "description": "Credit card name (if payment_method is credit-card)"},
                            "payment_portal": {"type": "string", "description": "Payment portal used (optional)"},
                            "person": {"type": "string", "description": "Person who made the expense"},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format (optional, defaults to today)"},
                        },
                        "required": ["amount", "description", "payment_method", "person"],
                    },
                ),
                Tool(
                    name="list_expenses",
                    description="List expenses with filtering options",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Number of expenses to return (default: 10)"},
                            "category": {"type": "string", "description": "Filter by category"},
                            "payment_method": {"type": "string", "description": "Filter by payment method"},
                            "person": {"type": "string", "description": "Filter by person"},
                            "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                            "month": {"type": "string", "description": "Filter by month (YYYY-MM)"},
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="get_best_card",
                    description="Get the best credit card recommendation for a specific category",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Expense category"},
                            "amount": {"type": "number", "description": "Purchase amount (optional)"},
                        },
                        "required": ["category"],
                    },
                ),
                Tool(
                    name="get_summary",
                    description="Get financial summary for a specific period",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {"type": "string", "description": "Period type: 'month', 'quarter', 'year', or 'custom'"},
                            "year": {"type": "integer", "description": "Year (required for month/quarter/year)"},
                            "month": {"type": "integer", "description": "Month (1-12, required for month)"},
                            "quarter": {"type": "integer", "description": "Quarter (1-4, required for quarter)"},
                            "start_date": {"type": "string", "description": "Start date for custom period (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "End date for custom period (YYYY-MM-DD)"},
                        },
                        "required": ["period"],
                    },
                ),
                Tool(
                    name="add_credit_card",
                    description="Add a new credit card with reward details",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Credit card name/nickname"},
                            "bank": {"type": "string", "description": "Bank name"},
                            "reward_categories": {"type": "object", "description": "Reward categories and rates (e.g., {'dining': 3, 'groceries': 2, 'default': 1})"},
                            "annual_fee": {"type": "number", "description": "Annual fee amount"},
                            "bonus_categories": {"type": "object", "description": "Quarterly/temporary bonus categories"},
                        },
                        "required": ["name", "bank", "reward_categories"],
                    },
                ),
                Tool(
                    name="export_data",
                    description="Export financial data in various formats",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {"type": "string", "description": "Export format: 'csv', 'excel', or 'json'"},
                            "output_path": {"type": "string", "description": "Output file path"},
                            "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                            "categories": {"type": "array", "items": {"type": "string"}, "description": "Categories to include"},
                        },
                        "required": ["format", "output_path"],
                    },
                ),
                Tool(
                    name="analyze_spending",
                    description="Analyze spending patterns and get insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "analysis_type": {"type": "string", "description": "Type: 'trends', 'categories', 'cards', or 'rewards'"},
                            "period": {"type": "string", "description": "Period: 'month', 'quarter', 'year'"},
                            "year": {"type": "integer", "description": "Year for analysis"},
                            "month": {"type": "integer", "description": "Month (1-12, for monthly analysis)"},
                        },
                        "required": ["analysis_type"],
                    },
                ),
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "add_expense":
                    return await self._handle_add_expense(arguments)
                elif name == "list_expenses":
                    return await self._handle_list_expenses(arguments)
                elif name == "get_best_card":
                    return await self._handle_get_best_card(arguments)
                elif name == "get_summary":
                    return await self._handle_get_summary(arguments)
                elif name == "add_credit_card":
                    return await self._handle_add_credit_card(arguments)
                elif name == "export_data":
                    return await self._handle_export_data(arguments)
                elif name == "analyze_spending":
                    return await self._handle_analyze_spending(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    def _setup_resources(self):
        """Set up available resources."""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="financial://config",
                    name="Financial Configuration",
                    description="Current financial tracking configuration",
                    mimeType="application/json",
                ),
                Resource(
                    uri="financial://cards",
                    name="Credit Cards",
                    description="List of configured credit cards",
                    mimeType="application/json",
                ),
            ]
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "financial://config":
                config = await self.db.get_configuration()
                return json.dumps(config, indent=2)
            elif uri == "financial://cards":
                cards = await self.db.get_credit_cards()
                return json.dumps([card.dict() for card in cards], indent=2)
            else:
                raise ValueError(f"Unknown resource: {uri}")
    
    async def _handle_add_expense(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle add_expense tool call."""
        expense_data = {
            "amount": Decimal(str(args["amount"])),
            "description": args["description"],
            "payment_method": args["payment_method"],
            "person": args["person"],
            "category": args.get("category"),
            "credit_card": args.get("credit_card"),
            "payment_portal": args.get("payment_portal"),
            "date": datetime.strptime(args.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        }
        
        expense = await self.db.add_expense(expense_data)
        
        # Calculate rewards if credit card was used
        rewards_info = ""
        if expense.payment_method == "credit-card" and expense.credit_card:
            rewards = await self.analytics.calculate_rewards(expense)
            if rewards:
                rewards_info = f"\n💰 Estimated rewards: {rewards['amount']} {rewards['type']}"
        
        return [TextContent(
            type="text",
            text=f"✅ Expense added successfully!\n"
                 f"💸 Amount: ${expense.amount}\n"
                 f"📝 Description: {expense.description}\n"
                 f"🏷️ Category: {expense.category}\n"
                 f"💳 Payment: {expense.payment_method}"
                 f"{f' ({expense.credit_card})' if expense.credit_card else ''}"
                 f"{rewards_info}"
        )]
    
    async def _handle_list_expenses(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle list_expenses tool call."""
        filter_params = ExpenseFilter(**args)
        expenses = await self.db.get_expenses(filter_params)
        
        if not expenses:
            return [TextContent(type="text", text="No expenses found matching the criteria.")]
        
        total = sum(expense.amount for expense in expenses)
        
        expense_list = "\n".join([
            f"• ${expense.amount} - {expense.description} "
            f"({expense.category}, {expense.payment_method}, {expense.date})"
            for expense in expenses
        ])
        
        return [TextContent(
            type="text",
            text=f"📊 Found {len(expenses)} expenses (Total: ${total})\n\n{expense_list}"
        )]
    
    async def _handle_get_best_card(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle get_best_card tool call."""
        category = args["category"]
        amount = args.get("amount", 100)  # Default amount for calculation
        
        best_card = await self.analytics.get_best_card_for_category(category, amount)
        
        if not best_card:
            return [TextContent(
                type="text",
                text=f"❌ No credit cards found for category '{category}'. Add some credit cards first!"
            )]
        
        reward_rate = best_card["reward_rate"]
        estimated_rewards = amount * reward_rate / 100
        
        return [TextContent(
            type="text",
            text=f"🏆 Best card for '{category}': {best_card['name']}\n"
                 f"💳 Bank: {best_card['bank']}\n"
                 f"⭐ Reward rate: {reward_rate}%\n"
                 f"💰 Estimated rewards for ${amount}: ${estimated_rewards:.2f}"
        )]
    
    async def _handle_get_summary(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle get_summary tool call."""
        summary = await self.analytics.get_financial_summary(args)
        
        return [TextContent(
            type="text",
            text=f"📈 Financial Summary\n"
                 f"💸 Total Spending: ${summary['total_spending']}\n"
                 f"📊 Number of Transactions: {summary['transaction_count']}\n"
                 f"🏷️ Top Categories:\n" +
                 "\n".join([f"  • {cat}: ${amount}" for cat, amount in summary['top_categories']]) +
                 f"\n💳 Payment Methods:\n" +
                 "\n".join([f"  • {method}: ${amount}" for method, amount in summary['payment_methods']]) +
                 (f"\n💰 Total Rewards Earned: ${summary['total_rewards']}" if summary.get('total_rewards') else "")
        )]
    
    async def _handle_add_credit_card(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle add_credit_card tool call."""
        card_data = {
            "name": args["name"],
            "bank": args["bank"],
            "reward_categories": args["reward_categories"],
            "annual_fee": args.get("annual_fee", 0),
            "bonus_categories": args.get("bonus_categories", {}),
        }
        
        card = await self.db.add_credit_card(card_data)
        
        return [TextContent(
            type="text",
            text=f"✅ Credit card added successfully!\n"
                 f"💳 Card: {card.name} ({card.bank})\n"
                 f"💰 Annual Fee: ${card.annual_fee}\n"
                 f"⭐ Reward Categories: {card.reward_categories}"
        )]
    
    async def _handle_export_data(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle export_data tool call."""
        result = await self.analytics.export_data(args)
        
        return [TextContent(
            type="text",
            text=f"✅ Data exported successfully!\n"
                 f"📁 File: {result['file_path']}\n"
                 f"📊 Records: {result['record_count']}\n"
                 f"📅 Date Range: {result['date_range']}"
        )]
    
    async def _handle_analyze_spending(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle analyze_spending tool call."""
        analysis = await self.analytics.analyze_spending(args)
        
        return [TextContent(
            type="text",
            text=f"🔍 Spending Analysis: {args['analysis_type'].title()}\n\n{analysis['summary']}\n\n"
                 f"📈 Key Insights:\n" +
                 "\n".join([f"• {insight}" for insight in analysis['insights']])
        )]


async def main():
    """Main function to run the MCP server."""
    server_instance = FinancialMCPServer()
    
    # Initialize database
    await server_instance.db.initialize()
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server_instance.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="financial-mcp-server",
                server_version="0.1.0",
                capabilities=server_instance.server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
