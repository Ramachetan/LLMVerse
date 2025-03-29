# Task 10: Financial Agent with LlamaIndex

This repository contains a multi-agent system built with LlamaIndex for performing fundamental financial analysis on companies using their stock symbols.

## Overview

The system leverages the AgentWorkflow class from LlamaIndex to create a coordinated multi-agent system that analyzes financial data and provides insights on a company's financial health.

## Agents

The system is composed of four specialized agents:

1. **FundamentalAgent**
   - Collects fundamental financial ratios for a given stock symbol using the FinanceToolkit package
   - Initiates the analysis workflow and passes data to specialized analysis agents

2. **ProfitabilityAgent**
   - Analyzes profitability metrics including ROA, ROE, Net Profit Margin, and Gross Margin
   - Compares values against industry thresholds to assess financial health
   - Assigns scores and provides justifications for each ratio

3. **LiquidityAgent**
   - Examines liquidity and solvency metrics including Current Ratio, Quick Ratio, Debt-to-Equity Ratio, and Interest Coverage Ratio
   - Evaluates the company's ability to meet short-term obligations
   - Determines financial stability using established thresholds

4. **SupervisorAgent**
   - Consolidates analyses from all specialist agents
   - Provides a comprehensive overview of the company's financial health
   - Offers strategic recommendations based on identified strengths and weaknesses

## Example Analysis: Twilio Inc. (TWLO)

The notebook includes a demonstration using Twilio Inc. (NYSE: TWLO) as an example. The analysis revealed:

LLM Raw output:

📤 Output: Okay, let's analyze TWLO's financial health based on the provided profitability ratios and thresholds.

**1. Return on Assets (ROA): -0.0102 (-1.02%)**

*   **Score:** 2/10
*   **Justification:** TWLO's ROA is negative (-1.02%). This indicates that the company is losing money relative to its total assets. The threshold for a healthy ROA is >5%, and even a moderate ROA is between 2% and 5%. A negative ROA signifies poor asset utilization and inefficiency in generating profits from its asset base. It suggests that the company's investments in assets are not yielding positive returns.
*   **Implication:** This is a significant red flag. It suggests the company is not effectively using its assets to generate profit.

**2. Return on Equity (ROE): -0.0124 (-1.24%)**

*   **Score:** 2/10
*   **Justification:** TWLO's ROE is also negative (-1.24%). This means the company is losing money relative to shareholders' equity. A healthy ROE is >15%, and a moderate ROE is between 8% and 15%. A negative ROE indicates that the company is destroying shareholder value rather than creating it.
*   **Implication:** This is another major concern. It indicates that the company is not generating returns for its shareholders.

**3. Net Profit Margin: -0.0245 (-2.45%)**

*   **Score:** 3/10
*   **Justification:** TWLO's Net Profit Margin is negative (-2.45%). This means that after accounting for all expenses (including cost of goods sold, operating expenses, interest, and taxes), the company is operating at a loss. A healthy net profit margin is >10%, and a moderate margin is between 5% and 10%. A negative margin indicates that the company's pricing strategy, cost management, or both are not effective in generating profits.
*   **Implication:** This confirms the issues highlighted by ROA and ROE. The company is not profitable at the net income level.

**4. Gross Margin: 0.511 (51.1%)**

*   **Score:** 8/10
*   **Justification:** TWLO's Gross Margin is 51.1%. This is above the healthy threshold of >40%. It indicates that the company is effectively managing its cost of goods sold (COGS) relative to its revenue. It suggests that the company has a good handle on the direct costs associated with producing its services.
*   **Implication:** This is a positive sign. It shows that the company can generate a healthy profit from each sale before considering operating expenses, interest, and taxes.

**Overall Insight on TWLO's Financial Health:**

Based on the profitability ratios, TWLO's financial health appears to be **weak**.

*   **Strengths:** The company has a strong Gross Margin, indicating efficient management of its direct costs. This suggests that the underlying business model has the potential for profitability.
*   **Weaknesses:** The negative ROA, ROE, and Net Profit Margin are significant concerns. These ratios indicate that the company is not effectively managing its overall expenses and is currently operating at a loss. The company is not generating returns for its shareholders or effectively utilizing its assets.

**Conclusion:**

TWLO needs to focus on improving its overall profitability. While the strong Gross Margin is encouraging, the company must address its operating expenses, interest expenses, and/or tax burden to achieve positive net income, ROA, and ROE. Strategies might include:

*   **Cost Reduction:** Identifying and reducing unnecessary operating expenses.
*   **Pricing Optimization:** Evaluating pricing strategies to ensure they are competitive yet profitable.
*   **Asset Management:** Improving the efficiency of asset utilization to generate higher returns.
*   **Revenue Growth:** Increasing revenue to offset fixed costs and improve profitability.

Without significant improvements in these areas, TWLO's financial health will remain a concern.

## Setup Instructions

### Prerequisites

- Python 3.10+
- Financial data API key

### Installation

1. Install required packages:
```bash
pip install financetoolkit llama-index llama-index-llms-google-genai python-dotenv
```

2. Set up your environment variables:

   Create a `.env` file in the root directory and add your financial data API key:
     ```bash
     FINANCE_API_KEY=your_api_key_here
     API_KEY=your_api_key_here
     # API Key is for Google GenAI. You can get it from Google AI Studio (https://aistudio.google.com/).
     ```


