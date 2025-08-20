# 💳 Financial MCP Server

A Model Context Protocol (MCP) server for financial tracking and credit card reward optimization. Designed to work seamlessly with LLMs to manage your personal finances, track expenses, and maximize credit card rewards.

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/financial-mcp-server.git
cd financial-mcp-server

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

### Usage with LLMs

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "financial-tracker": {
      "command": "uv",
      "args": ["run", "financial-mcp-server"],
      "cwd": "/path/to/financial-mcp-server"
    }
  }
}
```

## 🛠️ Available Tools

### Expense Management
- `add_expense`: Add new expenses with automatic categorization
- `list_expenses`: Query expenses with flexible filtering
- `update_expense`: Modify existing expense records
- `delete_expense`: Remove expense records

### Credit Card Optimization
- `add_credit_card`: Register new credit cards with reward details
- `get_best_card`: Get optimal card recommendation for purchase category
- `track_rewards`: Calculate and track reward earnings
- `analyze_spending`: Get spending analysis across cards and categories

### Analytics & Reporting
- `get_summary`: Financial summary for any time period
- `spending_trends`: Analyze spending patterns and trends
- `category_breakdown`: Detailed breakdown by expense categories
- `reward_analysis`: Credit card reward optimization insights

### Data Export
- `export_data`: Export financial data in various formats (CSV, Excel, JSON)
- `backup_data`: Create complete data backups
- `import_data`: Import data from various sources

### Configuration
- `set_preferences`: Configure default settings and preferences
- `manage_categories`: Add/edit expense categories
- `manage_portals`: Configure payment portals and services

## 💡 Example LLM Interactions

```
"Add a $50 dinner expense to my account"
→ Uses add_expense tool with smart categorization

"What's the best credit card for groceries this month?"
→ Uses get_best_card tool with current reward categories

"Show me my spending summary for last month"
→ Uses get_summary tool with date filtering

"Export my Q1 data for tax purposes"
→ Uses export_data tool with quarterly filtering
```

## 🎯 Credit Card Reward Features

### Smart Recommendations
- Automatic best card selection based on purchase category
- Quarterly bonus category tracking
- Portal reward stacking suggestions
- Annual fee vs rewards analysis

### Reward Tracking
- Real-time reward calculations
- Multiple reward types (cashback, points, miles)
- Bonus category optimization
- Spending threshold tracking

## 📊 Data Management

### Storage
- **Local SQLite**: Secure local data storage
- **Privacy First**: All data stays on your machine
- **Backup Ready**: Easy export and backup options

### Security
- No external API calls for sensitive data
- Local processing only
- Optional encryption for data files

## 🔧 Configuration

### First Setup
The server will guide you through initial setup:
1. Currency preferences
2. Default categories
3. Credit card information
4. Reward tracking preferences

### Customization
- Custom expense categories
- Payment portal preferences
- Reward calculation rules
- Export formats and schedules

## 🌟 Benefits for LLM Integration

### Natural Language Processing
- Understands conversational expense entries
- Smart categorization from descriptions
- Flexible date parsing
- Context-aware recommendations

### Intelligent Analysis
- Proactive spending insights
- Automated reward optimization
- Trend detection and alerts
- Personalized financial advice

### Seamless Workflow
- No manual data entry required
- Automatic categorization
- Smart defaults based on history
- Contextual follow-up questions

## 📋 Requirements

- Python 3.11+
- SQLite (included with Python)
- MCP-compatible LLM client (Claude Desktop, etc.)

## 🔮 Advanced Features

### AI-Powered Insights
- Spending pattern recognition
- Anomaly detection
- Budget optimization suggestions
- Reward maximization strategies

### Integration Ready
- API endpoints for external tools
- Webhook support for real-time updates
- Export integration with tax software
- Banking API preparation (future)

## 📄 License

MIT License - Built for personal financial optimization and LLM integration.
