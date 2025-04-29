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
from utils import reset_resample_states, mulaw8k_to_pcm16k, pcm24k_to_mulaw8k

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
GEMINI_SYSTEM_PROMPT = "You are a helpful and friendly voice assistant. Keep your responses concise."

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

    reset_resample_states() # Reset audio conversion state for this new call

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
                    stream_sid = data.get("streamSid")
                    logger.info(f"Twilio 'start' event received. SID: {stream_sid}")
                    # Signal that we can now start the Gemini session
                    stream_active.set()
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
            config = types.LiveConnectConfig( # Use types.
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig( # Use types.
                    voice_config=types.VoiceConfig( # Use types.
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE_NAME) # Use types.
                    ),
                    # language_code="en-US" # Optional
                ),
                system_instruction=types.Content( # Use types.
                    parts=[types.Part(text=GEMINI_SYSTEM_PROMPT)] # Use types.
                )
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
                                audio=types.Blob(data=pcm16k_chunk, mime_type=f"{GEMINI_AUDIO_FORMAT};rate={GEMINI_INPUT_SAMPLE_RATE}") # Use types.
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
        """Receives audio from Gemini and queues it for sending back to Twilio."""
        logger.info("Gemini receiver task started.")
        try:
            while True:
                complete_flag = False
                
                async for response in session.receive():
                    logger.info(f"Received response from Gemini: {type(response)}")
                    
                    # Check for audio data
                    if response.server_content and response.server_content.model_turn:
                        part = response.server_content.model_turn.parts[0]
                        
                        if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                            pcm24k_chunk = part.inline_data.data
                            logger.info(f"Received audio chunk from Gemini: {len(pcm24k_chunk)} bytes")
                            
                            # Convert Gemini's PCM 24kHz to Twilio's mulaw 8kHz
                            mulaw8k_chunk = pcm24k_to_mulaw8k(pcm24k_chunk)
                            
                            if mulaw8k_chunk:
                                logger.info(f"Converted audio to mulaw: {len(mulaw8k_chunk)} bytes")
                                await twilio_send_queue.put(mulaw8k_chunk)
                            else:
                                logger.warning("Audio conversion failed - empty chunk after conversion")
                        elif part.text:
                            logger.info(f"Gemini Text Response: {part.text}")
                        else:
                            logger.warning(f"Received part with no audio or text: {part}")

                    # Handle other potentially useful events
                    if response.server_content and response.server_content.interrupted:
                        logger.warning("Gemini generation interrupted.")
                    if response.server_content and response.server_content.generation_complete:
                        logger.info("Gemini generation complete event received.")
                        complete_flag = True
                        # Send an empty chunk as an end-of-turn marker
                        await twilio_send_queue.put(b"")
                        
                    if response.go_away:
                        logger.warning(f"Gemini GoAway received: TimeLeft={response.go_away.time_left}. Connection will close.")
                        return  # Exit the entire function
                        
                    if response.usage_metadata:
                        logger.info(f"Gemini Usage: {response.usage_metadata.total_token_count} total tokens")
                
                if complete_flag:
                    # If we got a complete flag, the inner loop is done but we want to restart
                    logger.info("Response turn complete. Waiting for next user input...")
                    # Wait for a short time to avoid spinning too fast if something's wrong
                    await asyncio.sleep(0.1)
                    # Don't break - let the outer loop continue
                else:
                    # If we exit the inner loop without a complete flag, something went wrong
                    logger.warning("Exited Gemini receive loop without completion flag. Breaking.")
                    break

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
    reset_resample_states() # Clean up audio state


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