import asyncio
from google import genai
import os
import wave
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})
model = "gemini-2.0-flash-exp"

config = {"response_modalities": ["TEXT"]}

async def main():
    async with client.aio.live.connect(model=model, config=config) as session:
        while True:
            message = input("User> ")
            if message.lower() == "exit":
                break
            await session.send(input=message, end_of_turn=True)
            
            async for response in session.receive():
                print(f'Response: {response}')
                if response.text is not None:
                    print(response.text, end="")



# config = {"response_modalities": ["AUDIO"]}

# async def main():
#     async with client.aio.live.connect(model=model, config=config) as session:
#         wf = wave.open("audio.wav", "wb")
#         wf.setnchannels(1)
#         wf.setsampwidth(2)
#         wf.setframerate(24000)

#         message = "Hello? Gemini are you there?"
#         await session.send(input=message, end_of_turn=True)

#         async for response in session.receive():
#             if response.data is not None:
#                 wf.writeframes(response.data)

#         # async for idx,response in async_enumerate(session.receive()):
#         #     if response.data is not None:
#         #         wf.writeframes(response.data)

#             # Comment this out to print audio data info
#             # if response.server_content.model_turn is not None:
#             #      print(response.server_content.model_turn.parts[0].inline_data.mime_type)

#         wf.close()

if __name__ == "__main__":
    asyncio.run(main())