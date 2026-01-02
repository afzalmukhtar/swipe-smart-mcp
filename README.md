# Swipe Smart MCP 💳

An AI-powered MCP server that helps you **always swipe the right card** for maximum rewards.

## What It Does

Swipe Smart tracks your credit cards, their reward structures, and spending caps — then tells you which card to use for any purchase to maximize your points or cashback.

### Key Features

- **Smart Card Recommendations** — Ask "Which card for ₹5000 on Amazon?" and get the optimal choice
- **Reward Tracking** — Automatically calculates points earned on every transaction
- **Cap Awareness** — Knows when you've hit monthly reward caps and suggests alternatives
- **Multi-Card Wallet** — Manage unlimited cards with complex reward structures
- **Category Intelligence** — Understands 22+ spending categories with proper MCC mapping
- **Web Search** — Searches for card reward details when adding new cards

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/afzalmukhtar/swipe-smart-mcp.git
cd swipe-smart-mcp

# Install dependencies
uv sync

# Initialize the database
uv run python scripts/init_db.py

# (Optional) Seed with sample data
uv run python scripts/seed.py
```

### Running the Server

```bash
# Direct run
uv run server.py

# Or use the script
./run_mcp.sh
```

### Connecting to Claude Desktop

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "swipe-smart": {
      "command": "/path/to/swipe-smart-mcp/run_mcp.sh"
    }
  }
}
```

## Usage Examples

### Ask for Card Recommendations
> "Which card should I use for a ₹3000 Swiggy order?"

### Log Transactions
> "I spent ₹1500 at Amazon using my HDFC Regalia"

### Check Rewards
> "How many points do I have on my Infinia card?"

### Add a New Card
> "Add my new SBI Cashback card"

### Analyze Spending
> "Show me my spending breakdown for this month"

## Available Tools

| Tool | Description |
|------|-------------|
| `get_best_card_for_purchase` | Recommends optimal card for a purchase |
| `add_transaction` | Logs an expense and calculates rewards |
| `get_my_cards` | Lists all cards in your wallet |
| `get_card_rules` | Shows reward rules for a card |
| `get_reward_balance` | Checks points balance |
| `analyze_expenses` | Spending analysis and insights |
| `search_card_info` | Web search for card reward details |
| `add_credit_card` | Adds a new card to wallet |

## Project Structure

```
swipe-smart-mcp/
├── server.py           # MCP server with all tools
├── src/
│   ├── models.py       # Database models (Card, Expense, Rules)
│   ├── db.py           # Database connection
│   └── logic/
│       ├── rewards.py      # Reward calculation engine
│       └── recommender.py  # Card recommendation logic
├── data/
│   ├── categories.json     # Expense categories & MCC codes
│   └── bank_domains.json   # Bank website mappings
└── scripts/
    ├── init_db.py      # Database initialization
    └── seed.py         # Sample data seeder
```

## Supported Categories

Dining, Groceries, Fuel, Travel (Flights, Hotels, Rail), Shopping, Entertainment, Utilities, Telecom, Healthcare, Education, and more.

## License

MIT

---

Built for the Indian credit card rewards ecosystem 🇮🇳
