import asyncio
import base64
import json
import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from google import genai
from google.genai import types
from fastapi.middleware.cors import CORSMiddleware
from utils.utils import mulaw8k_to_pcm16k, pcm24k_to_mulaw8k
from utils.tool_executor import ToolExecutor  # Import our new ToolExecutor
from utils.tools_router import router as tools_router  # Import our new router

# --- Configuration & Setup ---
load_dotenv() # Load environment variables from .env file

logging.basicConfig(level=logging.INFO) # Use INFO for general flow, DEBUG for more detail
logger = logging.getLogger(__name__)

# --- Environment Variables & Constants ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please create a .env file.")

# Public URL (replace with your actual ngrok/deployment URL)
# Extract hostname from the full ngrok URL (e.g., "abcd-12-34-56-78.ngrok-free.app")
YOUR_PUBLIC_HOSTNAME = os.getenv("PUBLIC_HOSTNAME", "YOUR_NGROK_OR_DEPLOYMENT_HOSTNAME") # Or set directly here
if "YOUR_NGROK_OR_DEPLOYMENT_HOSTNAME" in YOUR_PUBLIC_HOSTNAME:
     logger.warning("PUBLIC_HOSTNAME not set in environment. Using placeholder. Replace with your actual ngrok or deployment hostname.")


TWILIO_WEBSOCKET_URL = f"wss://{YOUR_PUBLIC_HOSTNAME}/audio_stream"
logger.info(f"Twilio WebSocket URL: {TWILIO_WEBSOCKET_URL}")

logger.debug(f"WebSocket URL for Twilio: {TWILIO_WEBSOCKET_URL}")
# Gemini Configuration
GEMINI_MODEL_NAME = "gemini-2.0-flash-live-001"
GEMINI_VOICE_NAME = "Puck"

with open("system.md", "r") as f:
    GEMINI_SYSTEM_PROMPT = f.read().strip()

# Initialize the Tool Executor
tool_executor = ToolExecutor()

# Audio Format Specifics
TWILIO_SAMPLE_RATE = 8000
TWILIO_AUDIO_FORMAT = "audio/x-mulaw" # Twilio uses μ-law
GEMINI_INPUT_SAMPLE_RATE = 16000
GEMINI_OUTPUT_SAMPLE_RATE = 24000
GEMINI_AUDIO_FORMAT = "audio/pcm" # Gemini uses Linear16 PCM

# Initialize Gemini Client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Google GenAI Client: {e}")
    raise

# State variable for audioop resampling
resample_state_8k_to_16k = None
resample_state_24k_to_8k = None

# --- FastAPI Application ---
app = FastAPI()

# CORS Middleware Configuration (optional, adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the tools router
app.include_router(tools_router)

@app.post("/incoming_call", response_class=PlainTextResponse)
async def incoming_call(request: Request):
    """Handles incoming Twilio call and connects it to the WebSocket stream."""
    logger.info(f"Incoming call from: {request.client.host}") # Log caller IP or identifier if available
    response = VoiceResponse()
    response.say("Hello! Please wait while I connect you to our AI assistant.", voice='Polly.Joanna-Neural') # Example voice
    connect = Connect()
    connect.stream(url=TWILIO_WEBSOCKET_URL)
    response.append(connect)
    response.pause(length=3600) # Keep call parked for 1 hour
    twiml_response = str(response)
    logger.debug(f"Responding to /incoming_call with TwiML: {twiml_response}")

    return Response(content=twiml_response, media_type="application/xml")


@app.websocket("/audio_stream")
async def audio_stream_websocket(websocket: WebSocket):
    """Handles the bidirectional audio stream between Twilio and Gemini."""
    await websocket.accept()
    logger.info(f"WebSocket connection established from: {websocket.client.host}")

    stream_sid = None
    gemini_session = None
    audio_queue = asyncio.Queue() # Queue for Twilio -> Gemini audio chunks
    twilio_send_queue = asyncio.Queue() # Queue for Gemini -> Twilio audio chunks
    stream_active = asyncio.Event() # Flag to signal when Twilio stream has started

    # reset_resample_states() # Reset audio conversion state for this new call

    async def twilio_receiver():
        """Receives messages from Twilio WebSocket."""
        nonlocal stream_sid
        logger.info("Twilio receiver task started.")
        try:
            while True:
                message_str = await websocket.receive_text()
                # logger.debug(f"Raw Twilio message: {message_str[:200]}...") # Log truncated message
                data = json.loads(message_str)
                event = data.get("event")

                if event == "connected":
                    logger.info("Twilio 'connected' event received.")
                elif event == "start":
                    # Correctly extract the nested streamSid (Standard Twilio Format)
                    start_data = data.get("start", {}) # Get the nested "start" object, default to {} if missing
                    stream_sid = start_data.get("streamSid") # Get streamSid from the nested object
                    logger.info(f"Twilio 'start' event received. SID: {stream_sid}")
                    if stream_sid:
                        # Signal that we can now start the Gemini session
                        stream_active.set()
                    else:
                        logger.error("Stream SID not found in 'start' event payload.")
                        # Decide how to handle this - maybe close the connection?
                        # For now, just log and don't set stream_active
                elif event == "media":
                    if not stream_sid:
                        logger.warning("Received 'media' event before 'start'. Ignoring.")
                        continue
                    payload = data["media"]["payload"]
                    mulaw_bytes = base64.b64decode(payload)
                    # logger.debug(f"Received {len(mulaw_bytes)} bytes of mulaw audio from Twilio.")
                    await audio_queue.put(mulaw_bytes)
                elif event == "stop":
                    logger.info("Twilio 'stop' event received.")
                    await audio_queue.put(None) # Signal end of audio from Twilio
                    break # Stop receiving from Twilio
                elif event == "mark":
                    mark_name = data.get("mark", {}).get("name")
                    logger.info(f"Twilio 'mark' event received: {mark_name}")
                else:
                    logger.warning(f"Received unknown Twilio event: {event}")
        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected.")
            await audio_queue.put(None) # Signal end if Twilio disconnects abruptly
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from Twilio: {e}")
            await audio_queue.put(None)
        except Exception as e:
            logger.error(f"Error in Twilio receiver: {type(e).__name__} - {e}", exc_info=True)
            await audio_queue.put(None) # Signal end on other errors
        finally:
            logger.info("Twilio receiver task finished.")
            stream_active.set() # Ensure other tasks can exit if receiver fails early
            await audio_queue.put(None) # Final signal just in case

    async def gemini_processor():
        """Connects to Gemini, processes audio from queue, starts receiver task."""
        nonlocal gemini_session
        logger.info("Gemini processor task waiting for Twilio stream to start...")
        await stream_active.wait() # Wait until Twilio 'start' event is received
        if not stream_sid:
             logger.error("Twilio stream did not start correctly. Aborting Gemini processor.")
             return

        logger.info("Twilio stream started. Connecting to Gemini Live API...")

        try:
            # Get tools from the ToolExecutor
            tools = tool_executor.get_tools_for_gemini()
            
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE_NAME)
                    ),
                    # language_code="te-IN", # Optional
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=GEMINI_SYSTEM_PROMPT)]
                ),
                tools=tools,  # Use dynamically loaded tools
            )

            # Connect using the config object
            async with client.aio.live.connect(model=GEMINI_MODEL_NAME, config=config) as session:
                gemini_session = session
                logger.info("Connected to Gemini Live API.")
                gemini_receiver_task = asyncio.create_task(gemini_audio_receiver(session))

                while True:
                    mulaw_chunk = await audio_queue.get()
                    if mulaw_chunk is None:
                        logger.info("End of Twilio audio stream signaled.")
                        break # Exit loop when Twilio audio ends

                    # 1. Convert mulaw 8kHz to PCM 16kHz
                    pcm16k_chunk = mulaw8k_to_pcm16k(mulaw_chunk)

                    # 2. Send to Gemini if conversion was successful
                    if pcm16k_chunk:
                        # logger.debug(f"Sending {len(pcm16k_chunk)} bytes of PCM 16kHz audio to Gemini.")
                        try:
                             # Send audio optimized for responsiveness
                             await session.send_realtime_input(
                                audio=types.Blob(data=pcm16k_chunk, mime_type=f"{GEMINI_AUDIO_FORMAT};rate={GEMINI_INPUT_SAMPLE_RATE}")
                            )
                        except Exception as gemini_send_e:
                            logger.error(f"Error sending audio to Gemini: {gemini_send_e}", exc_info=True)
                            # Decide how to handle: break, retry, log?
                            break
                    else:
                         logger.warning("Skipping empty chunk after audio conversion.")

                    await asyncio.sleep(0.005) # Small sleep to yield control

                logger.info("Waiting for Gemini receiver task to complete...")
                # Wait for the Gemini receiver to finish processing any remaining audio from Gemini
                await gemini_receiver_task # Wait for it to finish

        except Exception as e:
            logger.error(f"Error in Gemini processor: {type(e).__name__} - {e}", exc_info=True)
        finally:
            logger.info("Gemini processor task finished.")
            # Ensure the queue has a final None signal for the Twilio sender
            await twilio_send_queue.put(None)


    async def gemini_audio_receiver(session):
        """Receives audio and potentially function calls from Gemini and queues audio for sending back to Twilio."""
        logger.info("Gemini receiver task started.")
        try:
            while True:
                complete_flag = False
                function_call_in_progress = False # Flag to track if we are waiting for function results

                async for response in session.receive():
                    # logger.info(f"Received response from Gemini: {response}")

                    # --- Handle Function Calls ---
                    if response.tool_call:
                        logger.info(f"Received tool call from Gemini: {response.tool_call}")
                        function_call_in_progress = True # Mark that we are processing a function call
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            logger.info(f"Processing function call: {fc.name} with args: {fc.args}")
                            
                            try:
                                # Use our ToolExecutor to execute the function
                                result = tool_executor.execute_tool(fc.name, fc.args)
                                logger.info(f"Function '{fc.name}' returned: {result}")

                                # Prepare the response for Gemini
                                function_response = types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": result} # Send the actual result back
                                )
                                function_responses.append(function_response)
                            except Exception as func_e:
                                logger.error(f"Error executing function {fc.name}: {func_e}", exc_info=True)
                                # Send an error response back to Gemini
                                function_response = types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"error": f"Failed to execute function: {str(func_e)}"}
                                )
                                function_responses.append(function_response)

                        # Send the collected responses back to Gemini
                        if function_responses:
                            logger.info(f"Sending {len(function_responses)} function responses to Gemini.")
                            await session.send_tool_response(function_responses=function_responses)
                        # After sending tool response, continue the loop to get Gemini's next response

                    # --- Handle Server Content (Audio/Text) ---
                    elif response.server_content and response.server_content.model_turn:
                        part = response.server_content.model_turn.parts[0]

                        if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                            pcm24k_chunk = part.inline_data.data
                            # logger.debug(f"Received audio chunk from Gemini: {len(pcm24k_chunk)} bytes") # Debug level

                            # Convert Gemini's PCM 24kHz to Twilio's mulaw 8kHz
                            mulaw8k_chunk = pcm24k_to_mulaw8k(pcm24k_chunk)

                            if mulaw8k_chunk:
                                # logger.debug(f"Converted audio to mulaw: {len(mulaw8k_chunk)} bytes") # Debug level
                                await twilio_send_queue.put(mulaw8k_chunk)
                            else:
                                logger.warning("Audio conversion resulted in empty chunk.")
                        elif part.text:
                            logger.info(f"Gemini Text Response: {part.text}")
                            # Note: Currently not sending text back via audio, only logging.
                            # You might want to synthesize this text to speech if needed.
                        # else: # Log only if unexpected empty part
                        #     logger.warning(f"Received part with no audio or text: {part}")

                    # --- Handle Other Events ---
                    if response.server_content and response.server_content.interrupted:
                        logger.warning("Gemini generation interrupted.")
                    if response.server_content and response.server_content.generation_complete:
                        logger.info("Gemini generation complete event received.")
                        complete_flag = True
                        if not function_call_in_progress: # Only send end-of-turn marker if not waiting for function result processing
                             await twilio_send_queue.put(b"") # Send empty chunk as end-of-turn marker
                        function_call_in_progress = False # Reset flag after completion

                    if response.go_away:
                        logger.warning(f"Gemini GoAway received: TimeLeft={response.go_away.time_left}. Connection will close.")
                        return  # Exit the entire function

                    if response.usage_metadata:
                        logger.info(f"Gemini Usage: {response.usage_metadata.total_token_count} total tokens")

                # --- Loop Exit Logic ---
                if complete_flag:
                    logger.info("Response turn complete. Waiting for next user input or function result...")
                    await asyncio.sleep(0.1) # Small sleep
                    # Continue the outer loop
                else:
                    logger.warning("Exited Gemini receive loop unexpectedly (without completion flag or go_away). Breaking.")
                    break # Exit outer loop if inner loop finishes without completion

        except asyncio.CancelledError:
            logger.info("Gemini receiver task cancelled.")
        except Exception as e:
            logger.error(f"Error receiving from Gemini: {type(e).__name__} - {e}", exc_info=True)
        finally:
            logger.info("Gemini receiver task finished.")
            # Signal end to the sender queue
            await twilio_send_queue.put(None)


    async def twilio_sender():
        """Sends audio from the queue back to Twilio WebSocket."""
        logger.info("Twilio sender task started.")
        while True:
            mulaw8k_chunk = await twilio_send_queue.get()
            
            # Check for complete termination signal
            if mulaw8k_chunk is None:
                logger.info("End of Gemini audio stream signaled.")
                break # Exit loop
                
            # Check for empty chunk (end of turn, not end of conversation)
            if len(mulaw8k_chunk) == 0:
                logger.info("Empty audio chunk received, signaling end of turn")
                twilio_send_queue.task_done()
                continue # Skip this chunk but keep the loop running

            if not stream_sid:
                logger.warning("Twilio stream SID not available. Cannot send media.")
                twilio_send_queue.task_done()
                continue

            logger.info(f"Sending {len(mulaw8k_chunk)} bytes of audio to Twilio")
            try:
                # 1. Encode as Base64
                base64_audio = base64.b64encode(mulaw8k_chunk).decode('utf-8')

                # 2. Format Twilio WebSocket message
                twilio_message = json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": base64_audio
                    }
                })

                # 3. Send back to Twilio
                await websocket.send_text(twilio_message)
                logger.debug(f"Successfully sent audio to Twilio")
                twilio_send_queue.task_done() # Mark task as done for queue management

            except WebSocketDisconnect:
                logger.warning("Twilio WebSocket disconnected while trying to send media.")
                twilio_send_queue.task_done()
                break
            except Exception as e:
                logger.error(f"Error sending audio to Twilio: {type(e).__name__} - {e}", exc_info=True)
                twilio_send_queue.task_done()

            await asyncio.sleep(0.005) # Small sleep to yield control

        logger.info("Twilio sender task finished.")


    # --- Task Management ---
    # Create tasks for handling each direction
    receiver_twilio_task = asyncio.create_task(twilio_receiver())
    processor_gemini_task = asyncio.create_task(gemini_processor())
    sender_twilio_task = asyncio.create_task(twilio_sender())

    # Wait for Twilio receiver to end (when the actual call ends)
    try:
        await receiver_twilio_task
        logger.info("Twilio receiver task completed normally.")
    except Exception as e:
        logger.error(f"Twilio receiver task failed with: {e}", exc_info=True)
    finally:
        logger.info("Twilio connection ended. Cleaning up...")
        
        # Cancel the other tasks
        for task in [processor_gemini_task, sender_twilio_task]:
            if not task.done():
                logger.debug(f"Cancelling task: {task}")
                task.cancel()

        # Wait briefly for cancelled tasks to finish cleanup
        try:
            await asyncio.wait([t for t in [processor_gemini_task, sender_twilio_task] 
                            if not t.done()], timeout=5.0)
        except Exception as e:
            logger.error(f"Error waiting for tasks to cancel: {e}")

        # Check for exceptions in completed tasks
        for task in [processor_gemini_task, sender_twilio_task]:
            if task.cancelled():
                logger.debug(f"Task {task} was cancelled.")
            elif task.exception():
                exc = task.exception()
                logger.error(f"Task {task} raised an exception: {type(exc).__name__} - {exc}", exc_info=exc)


    # Ensure WebSocket is closed if not already disconnected
    if websocket.client_state != websocket.client_state.DISCONNECTED:
        try:
            await websocket.close()
            logger.info("WebSocket connection explicitly closed.")
        except RuntimeError as e:
            logger.warning(f"Error closing WebSocket (may already be closed): {e}")

    logger.info(f"WebSocket handler finished for connection from: {websocket.client.host}")
    # reset_resample_states() # Clean up audio state


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server on 0.0.0.0:5000")
    logger.info(f"Twilio WebSocket endpoint: {TWILIO_WEBSOCKET_URL}")
    if "YOUR_NGROK_OR_DEPLOYMENT_HOSTNAME" in YOUR_PUBLIC_HOSTNAME:
        logger.warning("Reminder: Ensure PUBLIC_HOSTNAME is correctly set and accessible.")

    # Use standard uvicorn worker, add keepalive pings for WebSockets
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=5000,
        reload=False, # Reload can cause issues with WebSockets/async tasks state
        ws_ping_interval=20, # Send ping every 20s
        ws_ping_timeout=20, # Wait 20s for pong response
        # workers=1 # Usually 1 worker is fine unless you need high concurrency
    )