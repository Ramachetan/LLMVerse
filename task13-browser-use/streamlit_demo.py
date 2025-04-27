import asyncio
import os
import sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from browser_use import Agent, SystemPrompt
from browser_use.controller.service import Controller
from browser_use.browser.browser import Browser, BrowserConfig
from langchain_google_genai import ChatGoogleGenerativeAI
import traceback # --- Added for better error reporting ---

# Load environment variables from .env file
load_dotenv()

# Set asyncio policy for Windows if applicable
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Append parent directory to sys.path if browser_use is located there
# Adjust this if your project structure is different
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Custom System Prompt (Unchanged) ---
class PCEComparisonPrompt(SystemPrompt):
    def important_rules(self) -> str:
        existing_rules = super().important_rules()
        new_rules = """
        9. MOST IMPORTANT RULES:
        - Extract the latest PCE inflation rate from the Bureau of Economic Analysis (BEA) website https://www.bea.gov/data/personal-consumption-expenditures-price-index
        - Extract the forecast PCE values from the user-provided forecast website using the LATEST reporting period found on the BEA site.
        """
        return f'{existing_rules}\n{new_rules}'

# --- Refined Agent Initialization Function ---
def initialize_agent(forecast_url: str):
    """Initializes the AI agent with a detailed task prompt."""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            st.error("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")
            return None, None

        llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=api_key) # --- Using flash for potential speed/cost savings ---
        controller = Controller()
        # --- Added headless=False for debugging, change to True for production ---
        browser = Browser(config=BrowserConfig(headless=False))

        # --- THE NEW DETAILED TASK PROMPT ---
        task = f"""
        Your goal is to compare the latest official US PCE inflation data with economist forecasts and provide a brief summary.

        **Step 1: Get Actual Data from BEA**
        - Go to the official BEA PCE page: https://www.bea.gov/data/personal-consumption-expenditures-price-index
        - Identify the **latest reporting period** for which PCE data has been released (e.g., "February 2024"). Note this period accurately.
        - Find the **Month-over-Month (MoM) percentage change** for that latest period for:
            1. Overall PCE Price Index (often just labeled 'PCE price index')
            2. Core PCE Price Index (explicitly labeled 'excluding food and energy')
        - Record these as the 'Actual (%)' values. Pay close attention to the correct month and MoM metric. Discard annual (YoY) figures unless MoM is unavailable.

        **Step 2: Get Forecast Data**
        - Go to the forecast calendar URL provided: {forecast_url}
        - Locate the economic calendar entries for **'PCE Price Index MoM'** and **'Core PCE Price Index MoM'** that correspond to the **exact same reporting period** you identified in Step 1 (e.g., 'February 2024'). The *release* date on the calendar might be later (e.g., in March), but you MUST find the data *for* the reporting month identified in Step 1.
        - Extract the corresponding **'Forecast'** or **'Consensus'** value (usually a MoM percentage) for both Overall PCE and Core PCE for that specific period.
        - Record these as the 'Forecast (%)' values.

        **Step 3: Calculate, Format Output, and Summarize**
        - Calculate the 'Difference (%)' (Actual - Forecast) for both metrics. Handle non-numeric values gracefully.
        - Present your findings first in a markdown table with the following exact columns and structure. Use percentage signs (%) and appropriate precision (usually one decimal place for MoM figures like +0.3%).

        | Metric                 | Reporting Period | Actual (%) | Forecast (%) | Difference (%) |
        |------------------------|-----------------|------------|--------------|----------------|
        | Overall PCE (MoM)    | [Latest Period] | [Actual %] | [Forecast %] | [Difference %] |
        | Core PCE (MoM)       | [Latest Period] | [Actual %] | [Forecast %] | [Difference %] |

        - **After the table**, provide a very detailed textual summary analyzing the results. Compare the actual figures to the forecasts. For example, state whether inflation was higher, lower, or in line with expectations based on the data presented in the table.

        **Important Rules:**
        - Prioritize Month-over-Month (MoM) data.
        - If you cannot find a specific value (e.g., the forecast for Core PCE), clearly write 'Not Found' in the corresponding cell of the table AND mention this limitation in your summary if relevant. Do not make up data.
        - Ensure the 'Reporting Period' column accurately reflects the month/year the data pertains to.
        - Double-check that you are extracting PCE data, not CPI. Verify the 'MoM' aspect.
        - Perform the task diligently. Accuracy is paramount.
        """

        agent = Agent(
            task=task,
            llm=llm,
            controller=controller,
            browser=browser,
            use_vision=True, # Keep vision enabled, might help with complex calendars
            max_actions_per_step=1, # Keep 1 for more deliberate steps
            system_prompt_class=PCEComparisonPrompt
        )
        return agent, browser

    except Exception as e:
        st.error(f"Error initializing agent: {e}")
        st.error(traceback.format_exc()) # --- Show full traceback for debugging ---
        return None, None

# --- Streamlit UI Setup ---
st.set_page_config(layout="wide") # --- Use wider layout ---
st.title('📊 Automated PCE Inflation Comparison Agent')
st.markdown("""
This tool uses an AI agent to browse the web, retrieve the latest official PCE inflation data from the **Bureau of Economic Analysis (BEA)**,
and compare it against economist forecasts from a selected source.
""")

# --- Create a two-column layout for the main content ---
# col1, col2 = st.columns([1, 1])  # Equal width columns

with st.sidebar:
    # --- User Friendliness: Explanation ---
    st.info("ℹ️ **How it works:** The AI agent will open a browser (you might see it pop up if not running headless), navigate the websites, analyze the content, and extract the required data. This process can take **1-3 minutes** depending on website speed and complexity.")

    forecast_sources = {
        "Oxford Economics – US PCE Nowcast": "https://www.oxfordeconomics.com/resource/us-pce-nowcast-shows-no-slowdown-in-price-pressures/",
        "Cleveland Fed – Inflation Nowcasting": "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting",
        "Bloomberg – PCE Inflation Coverage": "https://www.bloomberg.com/news/articles/2025-03-28/us-pce-inflation-accelerates-spending-is-weaker-than-forecast",
        "Reuters – PCE Inflation Analysis": "https://www.reuters.com/markets/us/us-consumer-spending-rises-february-core-inflation-firmer-2025-03-28/",
        "Wall Street Journal – PCE Inflation Report": "https://www.wsj.com/economy/central-banking/pce-inflation-accelerated-in-december-be039e82",
        "MarketWatch – PCE Inflation Tracker": "https://www.marketwatch.com/story/pce-inflation-tracker-2025-03-28",
        "Yahoo Finance – PCE Inflation Forecast": "https://finance.yahoo.com/news/pce-inflation-forecast-2025-03-28",
        "Trading Economics – PCE Forecast": "https://tradingeconomics.com/united-states/pce-forecast",
        "Custom URL": "custom"
    }

    selected_source_name = st.selectbox(
        "Select forecast source:",
        options=list(forecast_sources.keys()),
        index=0 # Default to MarketWatch
    )

    forecast_url = ""
    if selected_source_name == "Custom URL":
        forecast_url = st.text_input(
            "Enter custom forecast URL:",
            placeholder="https://www.example-economic-calendar.com" # --- Added placeholder ---
        )
    else:
        forecast_url = forecast_sources[selected_source_name]
        st.markdown(f"Using forecast data from: [{selected_source_name}]({forecast_url})")

    # --- Session State Initialization ---
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
    if 'browser_instance' not in st.session_state:
        st.session_state.browser_instance = None

    # --- Run Button and Agent Logic ---
    if st.button('🚀 Run Comparison', key='run_button'):
        if not forecast_url or forecast_url == "custom" and not st.text_input: # --- Check if custom URL is actually entered ---
            st.error("Please select a valid source or enter a custom forecast URL.")
        else:
            st.session_state.last_result = None # Clear previous results
            st.session_state.browser_instance = None # Clear previous browser instance ref

            st.write('Initializing agent...')
            agent, browser = initialize_agent(forecast_url)

            if agent and browser:
                st.session_state.browser_instance = browser # --- Store browser instance ---

                async def run_agent_async():
                    result_markdown = None
                    history = None
                    try:
                        # --- More descriptive spinner ---
                        with st.spinner(f"🤖 Agent is browsing BEA and {selected_source_name}... This may take a minute or two."):
                            history = await agent.run(max_steps=30) # --- Increased max_steps slightly ---
                            result_markdown = history.final_result() if history else None

                        # --- RESULT VALIDATION ---
                        if result_markdown and '|' in result_markdown and 'Metric' in result_markdown and 'Actual (%)' in result_markdown and 'Forecast (%)' in result_markdown:
                            st.session_state.last_result = result_markdown # Store valid result
                            st.success('Analysis completed successfully! 🎉')
                        elif result_markdown:
                            st.warning("⚠️ Agent finished but the output format wasn't the expected table.")
                            st.markdown("### Raw Agent Output:")
                            st.markdown(result_markdown) # Show raw output for debugging
                            st.session_state.last_result = None # Do not store invalid result for download
                        else:
                            st.error("❌ Agent did not return a result. It might have timed out or encountered an issue.")
                            st.session_state.last_result = None
                            # --- Optionally show history if available ---
                            if history:
                                st.warning("Displaying agent action history for debugging:")
                                st.json(history.to_dict()["history"])


                    except Exception as e:
                        st.error(f"An error occurred during agent execution: {e}")
                        st.error(traceback.format_exc()) # --- Show full traceback ---
                        st.session_state.last_result = None
                        # --- Optionally show history if available even on error ---
                        if history:
                             st.warning("Displaying agent action history (up to error):")
                             st.json(history.to_dict()["history"])


                # --- Run the async function ---
                asyncio.run(run_agent_async())
            else:
                # Initialization failed, error already shown in initialize_agent
                pass # Avoid running if agent/browser setup failed

    # --- Close Browser Button ---
    # Place it outside the main button logic so it's available if needed
    if st.session_state.get('browser_instance'): # Check if browser was stored
        if st.button('🛑 Close Agent Browser', key='close_button'):
            async def close_browser_async():
                browser_to_close = st.session_state.browser_instance
                if browser_to_close:
                    try:
                        with st.spinner("Closing browser..."):
                            await browser_to_close.close()
                        st.info("Browser closed.")
                        st.session_state.browser_instance = None # Clear reference
                        # Use rerun to update UI state, removing the button
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error closing browser: {e}")
                        st.session_state.browser_instance = None # Clear reference anyway

            asyncio.run(close_browser_async())

    # --- Download Button Logic ---
    if st.session_state.get('last_result'): # Check if a valid result is stored
        st.markdown("---") # Add a separator
        st.subheader("Download Results")
        if st.button('💾 Download Results as CSV', key='download_button'):
            try:
                result_md = st.session_state.last_result
                lines = result_md.strip().split('\n')
                table_lines = [line for line in lines if line.strip().startswith('|')]

                if len(table_lines) < 2: # Need header + separator + at least one data row technically, but check > 1 for header + data
                     raise ValueError("Markdown table format not recognized or empty.")

                # Extract headers (from the first line starting with |)
                headers = [h.strip() for h in table_lines[0].strip('|').split('|')]

                # Extract data (from lines after the separator '---|---')
                data_lines = table_lines[2:] # Skip header and separator
                data = []
                for line in data_lines:
                     row = [cell.strip() for cell in line.strip('|').split('|')]
                     if len(row) == len(headers): # Ensure row matches header count
                         data.append(row)
                     else:
                        st.warning(f"Skipping malformed table row: {line}") # Warn about bad rows

                if not data:
                     raise ValueError("No valid data rows found in the markdown table.")

                df = pd.DataFrame(data, columns=headers)
                csv = df.to_csv(index=False)

                st.download_button(
                    label="Click to Download CSV", # Label for the actual download link
                    data=csv,
                    file_name="pce_comparison_results.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error(f"Error converting results to CSV: {e}")
                st.error("Please check the format of the results table above.")
                st.error(traceback.format_exc())

# Display the results in the second column if they exist
# with col2:
st.subheader("Results")
if st.session_state.get('last_result'):
    st.markdown(st.session_state.last_result)
else:
    st.info("Run the comparison to see results here.")

# --- Explanatory Section (Unchanged) ---
st.markdown("---")
with st.expander("ℹ️ What is PCE Inflation?"):
    st.markdown("""
    **Personal Consumption Expenditures (PCE)** is a measure of consumer spending on goods and services in the U.S. economy published monthly by the Bureau of Economic Analysis (BEA).

    The **PCE Price Index** derived from this data is the **Federal Reserve's preferred measure of inflation** because it:
    - Covers a wider range of household spending than the CPI (Consumer Price Index).
    - Better accounts for consumers substituting goods/services as prices change.
    - Uses weights based on more up-to-date spending patterns.

    **Core PCE** excludes volatile food and energy prices to show the underlying inflation trend. The Fed typically targets **2% annual Core PCE inflation** over the long run.

    This tool compares the latest *actual* PCE data released by the BEA with *forecasts* made by economists before the release.
    """)