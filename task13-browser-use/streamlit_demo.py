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

load_dotenv()

if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
class PCEComparisonPrompt(SystemPrompt):
    def important_rules(self) -> str:
        existing_rules = super().important_rules()
        new_rules = """
        9. MOST IMPORTANT RULES:
        - Extract the latest PCE inflation rate from the Bureau of Economic Analysis (BEA) website https://www.bea.gov/data/personal-consumption-expenditures-price-index
        - Extract the forecast PCE values from the user-provided forecast website
        """
        return f'{existing_rules}\n{new_rules}'


def initialize_agent(query: str, forecast_url: str):
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=os.getenv('GEMINI_API_KEY'))
    controller = Controller()
    browser = Browser(config=BrowserConfig())
    
    # Construct a more specific task query using the provided forecast URL
    task = f"""Compare the current PCE inflation rate from https://www.bea.gov/data/personal-consumption-expenditures-price-index with what was forecast by economists on {forecast_url}. Extract both overall PCE and core PCE (excluding food and energy) if available.
    - Always provide your findings in this specific format:
          1. Date of the latest PCE report
          2. Actual PCE value (overall rate and core rate if available)
          3. Forecast PCE value that economists predicted
          4. The difference between actual and forecast values
          5. Format all numerical findings as percentages with appropriate precision
        - Present your findings in a markdown table with the following columns: 
          | Metric | Date | Actual | Forecast | Difference |
        - If you cannot find forecasted values, clearly state this in your response
        - When multiple time periods are available (monthly, annual), prioritize the most recent monthly figures
    """

    return Agent(
        task=task,
        llm=llm,
        controller=controller,
        browser=browser,
        use_vision=True,
        max_actions_per_step=1,
        system_prompt_class=PCEComparisonPrompt
    ), browser

st.title('PCE Data Comparison Agent 📊')
st.markdown("""
This tool compares the latest Personal Consumption Expenditures (PCE) inflation data 
from the Bureau of Economic Analysis with forecasted values from economic sources.
""")

# Preset options for forecast websites
forecast_sources = {
    "MarketWatch": "https://www.marketwatch.com/economy-politics/calendar",
    "Morningstar": "https://www.morningstar.com/economy/february-pce-inflation-forecasts-show-price-pressures-remaining-stubbornly-high",
    "Trading Economics": "https://tradingeconomics.com/united-states/personal-spending",
    "Investing.com": "https://www.investing.com/economic-calendar/core-pce-price-index-905",
    "Custom URL": "custom"
}

# Source selection
selected_source = st.selectbox(
    "Select forecast source:",
    options=list(forecast_sources.keys())
)

# Custom URL input if selected
if selected_source == "Custom URL":
    forecast_url = st.text_input("Enter custom forecast URL:")
else:
    forecast_url = forecast_sources[selected_source]
    if forecast_url != "custom":
        st.markdown(f"Using forecast from: [{selected_source}]({forecast_url})")

if st.button('Run Comparison'):
    if not forecast_url or forecast_url == "custom":
        st.error("Please enter a valid forecast URL.")
    else:
        st.write('Initializing agent...')
        
        # Construct query with specific instructions to format as a table
        query = f"Compare the latest PCE inflation data with forecasted values from {selected_source}"
        agent, browser = initialize_agent(query, forecast_url)

        async def run_agent():
            with st.spinner('Analyzing PCE data...'):
                history = await agent.run(max_steps=25)
                result = history.final_result()
                if result:
                    st.markdown("## Results")
                    st.markdown(result)
                    
                    # Store results in session state for potential download
                    if "PCE" in result and "|" in result:
                        st.session_state.last_result = result
                else:
                    st.write('No result returned from the agent.')
            st.success('Analysis completed! 🎉')

        asyncio.run(run_agent())

        st.button('Close Browser', on_click=lambda: asyncio.run(browser.close()))

# Add download button if results are available
if 'last_result' in st.session_state:
    if st.button('Download Results as CSV'):
        # Convert the markdown table to CSV
        lines = st.session_state.last_result.split('\n')
        table_lines = [line for line in lines if line.startswith('|') and '-|-' not in line]
        headers = table_lines[0].split('|')[1:-1]  # Remove empty first/last elements
        headers = [h.strip() for h in headers]
        
        data = []
        for line in table_lines[1:]:
            row = line.split('|')[1:-1]
            row = [cell.strip() for cell in row]
            data.append(row)
        
        df = pd.DataFrame(data, columns=headers)
        csv = df.to_csv(index=False)
        
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="pce_comparison.csv",
            mime="text/csv"
        )

# Add explanatory section
with st.expander("What is PCE?"):
    st.markdown("""
    **Personal Consumption Expenditures (PCE)** is a measure of consumer spending on goods and services in the U.S. economy. 
    
    The PCE Price Index is the Federal Reserve's preferred measure of inflation, as it:
    - Covers a wide range of household spending
    - Captures substitution between categories as prices change
    - Is less volatile than other measures like CPI
    
    **Core PCE** excludes food and energy prices, which tend to be more volatile.
    
    The Fed typically targets 2% annual PCE inflation over the long run.
    """)