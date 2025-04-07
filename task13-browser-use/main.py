from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent
import os
import asyncio
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.controller.service import Controller

load_dotenv()

async def main():
    task = 'Compare the current headline PCE inflation rate with what was forecast by economists on'
    model = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=os.getenv('GEMINI_API_KEY'))
    
    controller = Controller()
    browser = Browser(config=BrowserConfig())
    
    agent = Agent(
        task=task,
        llm=model,
        controller=controller,
        browser=browser,
        use_vision=True,
        max_actions_per_step=1,
    )

    history = await agent.run()

    result = history.final_result()
    if result:
        print('Result:', result)
    else:
        print('No result')


if __name__ == '__main__':
    asyncio.run(main())