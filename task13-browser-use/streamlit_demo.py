import asyncio
import os
import sys
import streamlit as st
from dotenv import load_dotenv
from browser_use import Agent, SystemPrompt
from browser_use.controller.service import Controller
from browser_use.browser.browser import Browser, BrowserConfig
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
class MySystemPrompt(SystemPrompt):
    def important_rules(self) -> str:
        existing_rules = super().important_rules()
        new_rules = """
        9. MOST IMPORTANT RULE:
        - ALWAYS Extract the latest PCE inflation rate from the Bureau of Economic Analysis (BEA) website https://www.bea.gov/data/personal-consumption-expenditures-price-index"""
        return f'{existing_rules}\n{new_rules}'


def initialize_agent(query: str):
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=os.getenv('GEMINI_API_KEY'))
    controller = Controller()
    browser = Browser(config=BrowserConfig())

    return Agent(
        task=query,
        llm=llm,
        controller=controller,
        browser=browser,
        use_vision=True,
        max_actions_per_step=1,
        system_prompt_class=MySystemPrompt
    ), browser

st.title('Automated Browser Agent with LLMs 🤖')

query = st.text_input('Enter your query:', 'Compare the current PCE inflation rate from https://www.bea.gov/data/personal-consumption-expenditures-price-index with what was forecast by economists on https://www.morningstar.com/economy/february-pce-inflation-forecasts-show-price-pressures-remaining-stubbornly-high')

if st.button('Run Agent'):
    st.write('Initializing agent...')
    agent, browser = initialize_agent(query)

    async def run_agent():
        with st.spinner('Running automation...'):
            history = await agent.run(max_steps=25)
            result = history.final_result()
            if result:
                st.write('Result:', result)
            else:
                st.write('No result')
        st.success('Task completed! 🎉')

    asyncio.run(run_agent())

    st.button('Close Browser', on_click=lambda: asyncio.run(browser.close()))
