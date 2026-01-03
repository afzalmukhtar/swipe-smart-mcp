![Swipe Smart MCP - AI-powered credit card rewards optimizer with futuristic digital interface showing multiple credit cards and reward tracking visualization](./Swipe-Smart-MCP.png)

<p align="center">
  <em>Banner image generated using Gemini Nano Banana Pro</em>
</p>

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

**Method 1: Using the shell script**
```json
{
  "mcpServers": {
    "swipe-smart": {
      "command": "/path/to/swipe-smart-mcp/run_mcp.sh"
    }
  }
}
```

**Method 2: Using uv directly with bash**
```json
{
  "mcpServers": {
    "swipe-smart": {
      "command": "bash",
      "args": ["-c", "cd /path/to/swipe-smart-mcp && uv run server.py"]
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

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

**Note:** By contributing, you agree to assign copyright to the project owner (see CLA in CONTRIBUTING.md).

## ⚖️ License & Commercial Use

This project is licensed under the **[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)**.

### ✅ Permitted Uses (Free)

- **Personal Use:** Use this for your own hobbies, private study, or personal credit card optimization
- **Education:** Universities and schools can use this for teaching and research
- **Noncommercial Organizations:** Charities, educational institutions, and government organizations

### ❌ Commercial Use is Prohibited

You may **NOT** use this software for any business purpose, including but not limited to:
- Internal business tools or employee use
- Hosting it as a service (SaaS) for customers
- Bundling it in a commercial product
- Any activity that provides commercial advantage or monetary compensation

### 💼 Need a Commercial License?

If you are a company and want to use Swipe Smart MCP for your business, please contact me:

* 📧 **Email:** [serac.amber4242@eagereverest.com](mailto:serac.amber4242@eagereverest.com)
  *(Note: This is a masked email for privacy, but it forwards directly to my main inbox.)*

* 👔 **LinkedIn:** [Afzal Mukhtar](https://www.linkedin.com/in/afzalmukhtar)
  *(Feel free to verify my profile or DM me if you prefer.)*

> 💡 **Important:** Please mention **"Swipe Smart MCP Commercial License"** as the subject of your email. If you don't receive a reply within 24 hours, please reach out via LinkedIn DM.

**Full License:** See [LICENSE](LICENSE) file for complete terms.
