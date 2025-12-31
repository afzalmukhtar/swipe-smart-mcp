# MCP Server Test Queries

Use these queries to test every tool and feature of the Financial MCP Server.
Ask these to an LLM connected to the server.

---

## 🔍 WALLET & CARD INFO (get_my_cards, get_card_rules, get_card_description)

1. "Show me all my credit cards"
2. "What cards do I have in my wallet?"
3. "List my cards with their credit limits"
4. "What's the billing cycle for my HDFC cards?"
5. "Show me the reward rules for HDFC Infinia"
6. "What are the multipliers on my Axis Ace card?"
7. "Which categories get bonus points on HDFC Regalia Gold?"
8. "Tell me about my SBI Cashback card benefits"
9. "What's the point value for ICICI Amazon Pay card?"
10. "Show caps and limits for AU LIT card"

---

## 💳 CARD RECOMMENDATION (get_best_card_for_purchase)

11. "Which card should I use for a ₹5,000 Amazon purchase?"
12. "Best card for a ₹2,500 Swiggy order?"
13. "I'm booking a ₹50,000 flight on MakeMyTrip, which card?"
14. "Recommend a card for ₹3,000 grocery shopping at BigBasket"
15. "Which card for ₹1,500 Uber ride?"
16. "Best card to use for ₹10,000 shopping on Flipkart?"
17. "I need to pay ₹8,000 electricity bill, which card?"
18. "Which card for ₹15,000 hotel booking?"
19. "Compare my cards for a ₹6,000 dining bill at a restaurant"
20. "Which card maximizes rewards for ₹4,000 Netflix subscription?"
21. "Best card for ₹25,000 fuel purchase at HP petrol pump?"
22. "I'm paying ₹12,000 insurance premium, which card should I avoid?"
23. "Which card for ₹500 coffee at Starbucks?"
24. "Best card for a ₹1,00,000 international flight booking?"
25. "Compare cards for ₹7,500 Zomato order"

---

## 📊 EXPENSE ANALYSIS (analyze_expenses)

26. "How did I spend this month?"
27. "Show me my spending summary for the last week"
28. "Where is my money going? Show me category breakdown"
29. "What's my effective reward rate?"
30. "Which card am I using the most?"
31. "Show me my top 5 spending categories this quarter"
32. "Analyze my expenses for the last year"
33. "What are my top merchants by spend?"
34. "How much have I spent on travel this year?"
35. "Show spending analysis from January to March 2025"

---

## 💰 REWARD BALANCE (get_reward_balance, adjust_reward_points)

36. "What's my reward points balance on HDFC Infinia?"
37. "How many points do I have on all my cards?"
38. "Check my Amex Membership Rewards balance"
39. "What's the estimated value of my HDFC points?"
40. "I redeemed 10,000 points on HDFC Regalia Gold for a flight, record it"
41. "Add 5,000 signup bonus points to my Axis Ace card"
42. "I got a referral bonus of 2,000 points on SBI Cashback, add it"
43. "Record that I used 15,000 points on ICICI Amazon Pay for shopping"
44. "My 3,000 points expired on AU LIT card, update the balance"
45. "Add a correction of +500 points to IDFC First Select"

---

## ➕ ADD TRANSACTIONS (get_expense_logging_rules, add_transaction)

46. "I spent ₹3,500 at Amazon using my HDFC Infinia card"
47. "Log a ₹1,200 Swiggy order on Axis Ace"
48. "Add a transaction: ₹8,000 flight on Indigo with HDFC Regalia Gold"
49. "I paid ₹2,500 electricity bill with SBI Cashback"
50. "Record ₹450 Uber ride on ICICI Amazon Pay"
51. "Log ₹15,000 grocery shopping at DMart on AU LIT"
52. "I spent ₹6,000 on Netflix using Amex Platinum"
53. "Add expense: ₹25,000 hotel at Marriott with HDFC Infinia via SmartBuy"
54. "I paid ₹1,800 for Zomato through CRED using Axis Ace"
55. "Log ₹50,000 insurance payment on IDFC First Select"

---

## 📜 TRANSACTION QUERIES (get_transactions)

56. "Show me my last 5 transactions"
57. "What did I spend on dining this month?"
58. "Show transactions on HDFC Infinia"
59. "List all my Amazon transactions"
60. "Show expenses over ₹10,000"
61. "What did I spend at Swiggy and Zomato?"
62. "Show me transactions from last week"
63. "List all fuel expenses this quarter"
64. "Show transactions on HDFC cards only"
65. "What did I spend between Dec 1 and Dec 15?"

---

## ➕ ADD NEW CARD (get_card_addition_guidelines, add_credit_card, add_reward_rules, add_cap_buckets, add_redemption_partners)

66. "I want to add my new OneCard credit card"
67. "Add my HDFC Millennia card with ₹2,00,000 limit, billing on 5th"
68. "Help me set up my ICICI Coral card"
69. "I got a new Axis Atlas card, add it to my wallet"
70. "Search for reward rules on IndusInd Legend card"
71. "What are the benefits of SBI Elite card?" (triggers search_card_info)
72. "Add reward rules to my newly added card"
73. "Set up monthly caps for my HDFC Millennia"
74. "Add Marriott Bonvoy as a transfer partner for my new card"

---

## 🗑️ DELETE OPERATIONS (delete_transaction, delete_credit_card)

75. "Delete my last transaction"
76. "Remove the ₹500 Starbucks expense I added by mistake"
77. "Delete transaction ID 45"
78. "I want to remove my old SBI SimplyCLICK card from wallet"
79. "Delete the card with ID 10"

---

## 🔎 SEARCH CARD INFO (search_card_info)

80. "Search for HDFC Diners Club Black reward structure"
81. "Find information about Axis Magnus card benefits"
82. "What are the reward rates on RBL World Safari?"
83. "Search for ICICI Sapphiro card caps and exclusions"
84. "Find Amex Gold Charge card transfer partners"

---

## 🧠 COMPLEX/MULTI-TOOL QUERIES

85. "I'm planning to buy a ₹80,000 laptop from Amazon - which card should I use and what's the best redemption option?"
86. "Show me how much I spent on travel and recommend the best card for my next trip"
87. "What's my most rewarding card and how many points do I have on it?"
88. "Add my ₹5,000 Flipkart purchase on the best card for shopping"
89. "Compare my reward earnings this month vs last month"
90. "I want to maximize rewards on a ₹30,000 purchase - show all my options"
91. "Which categories am I overspending on and which card should I use for each?"
92. "Show my total points across all cards and their estimated value"
93. "I need to pay ₹1,00,000 in bills this month - help me split across cards for max rewards"
94. "What card should I use for daily Uber rides to work?"
95. "Review my wallet - am I using the right cards for my spending patterns?"

---

## 🎯 EDGE CASES & ERROR HANDLING

96. "Which card for a ₹100 purchase?" (very small amount)
97. "Best card for ₹5,00,000 jewellery purchase?" (excluded category)
98. "Add a transaction without specifying the card" (should ask for card)
99. "Show transactions for a card I don't have"
100. "What's the balance on a non-existent card?"

---

## ✅ EXPECTED TOOL MAPPING

| Query Type | Primary Tool(s) |
|------------|-----------------|
| 1-10 | `get_my_cards`, `get_card_rules`, `get_card_description` |
| 11-25 | `get_best_card_for_purchase` |
| 26-35 | `analyze_expenses` |
| 36-45 | `get_reward_balance`, `adjust_reward_points` |
| 46-55 | `get_expense_logging_rules`, `add_transaction` |
| 56-65 | `get_transactions` |
| 66-74 | `get_card_addition_guidelines`, `add_credit_card`, `add_reward_rules`, `add_cap_buckets`, `add_redemption_partners`, `search_card_info` |
| 75-79 | `delete_transaction`, `delete_credit_card` |
| 80-84 | `search_card_info` |
| 85-95 | Multiple tools combined |
| 96-100 | Error handling / validation |

---

## 🚀 HOW TO TEST

1. Connect your LLM to the MCP server
2. Ask queries one by one or in batches
3. Verify the LLM:
   - Calls the correct tool
   - Parses the response correctly
   - Formats the output per guidelines
   - Handles errors gracefully
4. Check database state after mutations (add/delete)

---
---

# 🆕 FRESH DATABASE TEST SEQUENCE

**Run these queries IN ORDER on a fresh/empty database.**

Before starting, reset your database:
```bash
rm wallet.db  # Delete existing database
uv run python -c "from src.db import engine; from sqlmodel import SQLModel; SQLModel.metadata.create_all(engine)"
```

---

## PHASE 1: EMPTY STATE CHECKS (Queries F1-F5)

F1. "Show me all my credit cards"
> Expected: "Your wallet is empty" or similar

F2. "How did I spend this month?"
> Expected: "No transactions found"

F3. "Which card should I use for ₹5,000 Amazon purchase?"
> Expected: "No cards found. Add cards first."

F4. "What's my reward balance?"
> Expected: Error or empty state message

F5. "Show my last 5 transactions"
> Expected: Empty list

---

## PHASE 2: ADD FIRST CARD - HDFC Regalia Gold (Queries F6-F12)

F6. "I want to add my HDFC Regalia Gold credit card"
> Expected: Should ask for limit, billing cycle

F7. "My limit is ₹3,00,000 and billing cycle starts on the 15th"
> Expected: Card added, returns card_id (likely 1)

F8. "Search for HDFC Regalia Gold reward rules online"
> Expected: Web search results with reward info

F9. "Add these reward rules to my HDFC Regalia Gold: 4x on travel, 2x on dining, 1x base rate"
> Expected: Rules added successfully

F10. "Add a monthly cap of 15,000 points for accelerated categories on HDFC Regalia Gold"
> Expected: Cap bucket added

F11. "Add Marriott Bonvoy as a transfer partner with 1:1 ratio and ₹0.35 per point value"
> Expected: Partner added

F12. "Show me the rules for my HDFC Regalia Gold now"
> Expected: Full rules, caps, partners displayed

---

## PHASE 3: ADD SECOND CARD - Axis Ace (Queries F13-F18)

F13. "Add my Axis Ace credit card with ₹1,50,000 limit, billing on 1st"
> Expected: Card added, card_id = 2

F14. "Search for Axis Ace reward structure"
> Expected: Web search results

F15. "Add reward rules: 5% cashback on bill payments, 2% on others. Point value is ₹1 (cashback card)"
> Expected: Rules added

F16. "Set a monthly cap of ₹500 cashback on bill payments for Axis Ace"
> Expected: Cap added

F17. "Show me all my cards now"
> Expected: 2 cards - HDFC Regalia Gold, Axis Ace

F18. "Compare rules between my two cards"
> Expected: Side by side comparison

---

## PHASE 4: ADD THIRD CARD - ICICI Amazon Pay (Queries F19-F22)

F19. "Add ICICI Amazon Pay card, ₹2,00,000 limit, billing on 10th, I have Amazon Prime"
> Expected: Card added with tier_status for Prime

F20. "Add rules: 5% on Amazon, 2% on bill payments, 1% on others"
> Expected: Rules added

F21. "Show all my cards with their reward rates"
> Expected: 3 cards listed

F22. "Which card has the best base reward rate?"
> Expected: Analysis of the 3 cards

---

## PHASE 5: FIRST TRANSACTIONS (Queries F23-F32)

F23. "I spent ₹8,500 at Amazon using my ICICI Amazon Pay card"
> Expected: Transaction added, points calculated (5% = 425 pts)

F24. "Log ₹3,200 electricity bill payment on Axis Ace"
> Expected: Transaction added (5% = 160 or ₹160 cashback)

F25. "Add ₹12,000 MakeMyTrip flight booking on HDFC Regalia Gold"
> Expected: Transaction added (4x = 48,000 pts)

F26. "I paid ₹2,800 for dinner at a restaurant using HDFC Regalia Gold"
> Expected: Transaction added (2x = 5,600 pts)

F27. "Log ₹1,500 Uber ride on ICICI Amazon Pay"
> Expected: Transaction added (1% = 15 pts)

F28. "Show me my last 5 transactions"
> Expected: 5 transactions listed

F29. "How much have I spent so far?"
> Expected: Analysis showing ~₹28,000 total

F30. "What's my reward balance on HDFC Regalia Gold?"
> Expected: Points from the 2 transactions

F31. "Check points on all my cards"
> Expected: Balances for all 3 cards

F32. "What's my effective reward rate so far?"
> Expected: Calculated based on points earned vs spent

---

## PHASE 6: CARD RECOMMENDATIONS (Queries F33-F40)

F33. "Which card should I use for a ₹5,000 Flipkart purchase?"
> Expected: Compares 3 cards, recommends one

F34. "Best card for ₹4,000 Swiggy order?"
> Expected: Recommendation with reasoning

F35. "I'm booking a ₹25,000 hotel, which card?"
> Expected: HDFC Regalia Gold (travel bonus)

F36. "Which card for ₹6,000 phone bill?"
> Expected: Axis Ace (5% on bills)

F37. "Best card for ₹15,000 Amazon purchase?"
> Expected: ICICI Amazon Pay (5% on Amazon)

F38. "Compare all cards for a ₹10,000 grocery purchase"
> Expected: Comparison table

F39. "Which card should I AVOID for a ₹50,000 insurance payment?"
> Expected: Mentions exclusions if any

F40. "I want to maximize rewards on ₹20,000 spend - split recommendations?"
> Expected: Multi-card strategy

---

## PHASE 7: MORE TRANSACTIONS (Queries F41-F48)

F41. "Log ₹950 Starbucks on HDFC Regalia Gold"
> Expected: Dining category, 2x points

F42. "I spent ₹7,200 on Netflix annual subscription using Axis Ace"
> Expected: Entertainment/bills category

F43. "Add ₹4,500 BigBasket grocery order on ICICI Amazon Pay"
> Expected: 1% rate

F44. "Log ₹18,000 Airbnb booking on HDFC Regalia Gold"
> Expected: Travel, 4x points

F45. "I paid ₹3,300 for Jio recharge using Axis Ace"
> Expected: Bill payment, 5%

F46. "Add ₹6,800 Myntra shopping on ICICI Amazon Pay"
> Expected: 1% base rate

F47. "Show all my transactions now"
> Expected: 11 transactions

F48. "What's my total spend this month?"
> Expected: Sum of all transactions

---

## PHASE 8: ANALYSIS & INSIGHTS (Queries F49-F55)

F49. "Analyze my spending - where is my money going?"
> Expected: Category breakdown

F50. "Which card am I using the most?"
> Expected: Usage breakdown by card

F51. "What's my best performing card by reward rate?"
> Expected: Analysis based on points earned

F52. "Show my top 3 spending categories"
> Expected: Travel, Shopping, Bills likely

F53. "How much value have I earned in rewards?"
> Expected: Total points × point values

F54. "Am I using the right cards for my purchases?"
> Expected: Optimization suggestions

F55. "Show complete spending summary"
> Expected: Full dashboard-style output

---

## PHASE 9: POINT ADJUSTMENTS (Queries F56-F60)

F56. "I got a 5,000 point signup bonus on HDFC Regalia Gold, add it"
> Expected: Bonus added

F57. "Add 2,000 referral bonus points to Axis Ace"
> Expected: Referral added

F58. "I redeemed 10,000 points on HDFC Regalia Gold for Amazon voucher"
> Expected: Redemption recorded, balance reduced

F59. "Check my updated balance on HDFC Regalia Gold"
> Expected: Original + bonus - redemption

F60. "Show point history for all cards"
> Expected: Earnings + adjustments

---

## PHASE 10: ADD FOURTH CARD (Queries F61-F65)

F61. "Add my new SBI Cashback card - ₹1,00,000 limit, billing on 20th"
> Expected: Card added

F62. "Add rules: 5% on online spends, 1% offline. It's a cashback card with ₹1 point value"
> Expected: Rules added

F63. "Show all 4 of my cards"
> Expected: Complete wallet view

F64. "Now which card is best for ₹5,000 Amazon?"
> Expected: Compares 4 cards now

F65. "Compare my cashback cards vs reward point cards"
> Expected: Axis Ace, SBI Cashback vs HDFC, ICICI

---

## PHASE 11: DELETE OPERATIONS (Queries F66-F70)

F66. "Delete my last transaction"
> Expected: Most recent removed

F67. "Show transactions again to confirm"
> Expected: One less transaction

F68. "I want to remove my SBI Cashback card"
> Expected: Card deleted with cascade

F69. "Show my cards"
> Expected: Back to 3 cards

F70. "Confirm SBI card is gone from recommendations"
> Expected: Only 3 cards in comparison

---

## PHASE 12: FINAL VALIDATION (Queries F71-F75)

F71. "Give me a complete summary of my wallet"
> Expected: All cards, rules, balances

F72. "What's my total reward value across all cards?"
> Expected: Sum of all point values

F73. "Show spending analysis for all time"
> Expected: Complete analysis

F74. "Which card should I use most based on my spending pattern?"
> Expected: Smart recommendation

F75. "Review my wallet setup - any suggestions?"
> Expected: Optimization tips

---

## ✅ FRESH DB TEST CHECKLIST

| Phase | Queries | Tests |
|-------|---------|-------|
| 1 | F1-F5 | Empty state handling |
| 2 | F6-F12 | Add first card with full setup |
| 3 | F13-F18 | Add second card |
| 4 | F19-F22 | Add third card with tier |
| 5 | F23-F32 | First transactions & balances |
| 6 | F33-F40 | Card recommendations |
| 7 | F41-F48 | More transactions |
| 8 | F49-F55 | Analysis & insights |
| 9 | F56-F60 | Point adjustments |
| 10 | F61-F65 | Add fourth card |
| 11 | F66-F70 | Delete operations |
| 12 | F71-F75 | Final validation |

**Total: 75 sequential queries building a complete wallet from scratch.**
