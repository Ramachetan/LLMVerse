import asyncio
import base64
import json
import logging
# import audioop # No longer needed
from pydub import AudioSegment # Import pydub
from pydub.utils import get_array_type # Helper for numpy conversion
import sounddevice as sd
import numpy as np
import websockets
import requests
from lxml import etree # For parsing TwiML

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FASTAPI_URL = "http://localhost:5000"
INCOMING_CALL_ENDPOINT = f"{FASTAPI_URL}/incoming_call"

# Audio Settings (Match Twilio Input)
INPUT_SAMPLE_RATE = 8000  # Target rate for Twilio (μ-law)
INPUT_CHANNELS = 1
INPUT_DTYPE = 'int16' # Intermediate dtype before μ-law conversion
OUTPUT_SAMPLE_RATE = 8000 # Expected rate from backend (μ-law)
OUTPUT_CHANNELS = 1
OUTPUT_DTYPE = 'int16' # dtype after μ-law decoding
BLOCK_SIZE = 1600  # How many frames per block (e.g., 200ms chunks at 8kHz)
BYTES_PER_SAMPLE_INPUT = np.dtype(INPUT_DTYPE).itemsize
BYTES_PER_SAMPLE_OUTPUT = np.dtype(OUTPUT_DTYPE).itemsize

# --- Global State ---
websocket_connection = None
stream_sid_global = "test_stream_sid_12345" # Simulate a Stream SID
audio_input_active = asyncio.Event()
audio_output_queue = asyncio.Queue()
main_loop = None # Add global variable for the main event loop

# --- Audio Handling ---

def audio_input_callback(indata, frames, time, status):
    """Callback function for sounddevice input stream."""
    # logger.debug(f"Audio input callback triggered with {frames} frames, status: {status}") # Reduce noise
    if status:
        logger.warning(f"Input Status: {status}")
    if audio_input_active.is_set() and websocket_connection and main_loop: # Check main_loop
        # ... inside audio_input_callback ...
        try:
            audio_segment = AudioSegment(
                data=indata.tobytes(), # Get raw bytes from numpy array
                sample_width=BYTES_PER_SAMPLE_INPUT, # Should be 2 for int16
                frame_rate=INPUT_SAMPLE_RATE,
                channels=INPUT_CHANNELS
            )
            mulaw_segment = audio_segment.export(format="mulaw", parameters=["-ar", str(INPUT_SAMPLE_RATE)])
            mulaw_bytes = mulaw_segment.read()
            mulaw_segment.close() # Close the BytesIO object

            # logger.debug(f"Captured {len(mulaw_bytes)} mulaw bytes")

            # Prepare Twilio media message
            payload = base64.b64encode(mulaw_bytes).decode('utf-8')
            media_message = {
                "event": "media",
                "sequenceNumber": "2", # You might want to increment this
                "media": {
                    "track": "inbound",
                    "chunk": "1", # You might want to increment this
                    "timestamp": "0", # You might want a real timestamp
                    "payload": payload
                },
                "streamSid": stream_sid_global
            }

            # Send the message asynchronously using run_coroutine_threadsafe
            # Use asyncio.create_task to avoid blocking the callback # <-- Old comment, remove or update
            # asyncio.create_task(websocket_connection.send(json.dumps(media_message))) # <-- This caused the error
            asyncio.run_coroutine_threadsafe(
                websocket_connection.send(json.dumps(media_message)),
                main_loop
            )
            # logger.debug(f"Scheduled send for {len(mulaw_bytes)} mulaw bytes.")

        except Exception as e:
            logger.error(f"Error in audio input callback: {e}", exc_info=True)

async def play_audio_output():
    """Plays audio received from the WebSocket."""
    logger.info("Audio output player started.")
    output_stream_started = False
    try:
        # Use sd.OutputStream directly to allow checking if it's active
        stream = sd.OutputStream(samplerate=OUTPUT_SAMPLE_RATE,
                                 channels=OUTPUT_CHANNELS,
                                 dtype=OUTPUT_DTYPE,
                                 blocksize=BLOCK_SIZE)
        with stream: # Use the stream within a context manager
            logger.info(f"Output audio stream opened ({OUTPUT_SAMPLE_RATE} Hz)")
            output_stream_started = True
            while True:
                mulaw_bytes = await audio_output_queue.get()
                if mulaw_bytes is None:
                    logger.info("Output player received stop signal.")
                    break
                try:
                    logger.debug(f"Dequeued {len(mulaw_bytes)} mulaw bytes for playback.") # Log dequeued size
                    if len(mulaw_bytes) > 0:
                        # Use pydub to decode μ-law to linear PCM
                        # Create an AudioSegment from the raw μ-law data
                        audio_segment = AudioSegment(
                            data=mulaw_bytes,
                            sample_width=1, # μ-law is 1 byte per sample
                            frame_rate=OUTPUT_SAMPLE_RATE, # Assuming output is 8kHz
                            channels=OUTPUT_CHANNELS
                        )
                        # Convert to numpy array (implicitly converts to PCM)
                        # Ensure the array type matches OUTPUT_DTYPE ('int16')
                        array_type = get_array_type(BYTES_PER_SAMPLE_OUTPUT * 8) # e.g., 'h' for int16
                        pcm_array = np.array(audio_segment.get_array_of_samples(), dtype=array_type)

                        logger.debug(f"Decoded to PCM array shape: {pcm_array.shape}, dtype: {pcm_array.dtype}") # Log decoded array info

                        # Check if array contains non-zero data (optional, can be verbose)
                        # if np.any(pcm_array):
                        #     logger.debug("PCM array contains non-zero data.")
                        # else:
                        #     logger.warning("PCM array contains only zeros.")

                        stream.write(pcm_array) # Use stream.write for lower latency playback
                        logger.debug(f"Wrote {len(pcm_array)} samples to output stream.")

                    else:
                        logger.info("Received empty audio chunk (likely end of turn).")

                except Exception as e:
                    logger.error(f"Error processing/playing audio chunk: {e}", exc_info=True) # Log full traceback
                finally:
                    audio_output_queue.task_done()

    except sd.PortAudioError as e:
        logger.error(f"PortAudio error in output stream: {e}")
        logger.error("Available output devices:")
        try:
            print(sd.query_devices()) # Print devices if stream fails
        except Exception:
            logger.error("Could not query audio devices.")
    except Exception as e:
        logger.error(f"Error in audio output player: {e}", exc_info=True)
    finally:
        if not output_stream_started:
             logger.error("Audio output stream failed to start.")
        logger.info("Audio output player finished.")


# --- WebSocket Client ---

async def websocket_client(uri):
    """Connects to the WebSocket and handles communication."""
    global websocket_connection
    logger.info(f"Attempting to connect to WebSocket: {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            websocket_connection = websocket
            logger.info("WebSocket connection established.")

            # 1. Send "connected" event
            await websocket.send(json.dumps({
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0"
            }))
            logger.info("Sent 'connected' event.")

            # 2. Send "start" event
            start_message = {
                "event": "start",
                "sequenceNumber": "1",
                "start": {
                    "accountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    "streamSid": stream_sid_global,
                    "callSid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    "tracks": ["inbound"],
                    "mediaFormat": {
                        "encoding": "audio/x-mulaw",
                        "sampleRate": INPUT_SAMPLE_RATE,
                        "channels": 1
                    }
                },
                "protocol": "Call",
                "version": "1.0.0"
            }
            await websocket.send(json.dumps(start_message))
            logger.info(f"Sent 'start' event with streamSid: {stream_sid_global}")

            # Signal that audio input can start
            audio_input_active.set()
            logger.info("Audio input marked as active.")

            # Start the audio output player task
            output_task = asyncio.create_task(play_audio_output())

            # 3. Receive messages from backend (Gemini audio)
            try:
                while True:
                    message_str = await websocket.recv()
                    logger.debug(f"Received raw message: {message_str[:150]}...") # Log received message start
                    data = json.loads(message_str)
                    event = data.get("event")

                    if event == "media":
                        payload = data.get("media", {}).get("payload")
                        if payload:
                            mulaw_bytes = base64.b64decode(payload)
                            logger.debug(f"Received and decoded {len(mulaw_bytes)} mulaw bytes from backend payload.") # Log received size
                            await audio_output_queue.put(mulaw_bytes)
                        else:
                             logger.warning("Received media event with no payload.")
                    elif event == "mark":
                        mark_name = data.get("mark", {}).get("name")
                        logger.info(f"Received 'mark' event: {mark_name}")
                    elif event == "stop":
                        logger.info("Received 'stop' event from backend.")
                        break # Backend explicitly stopped
                    else:
                        logger.warning(f"Received unknown event: {event}")

            except websockets.exceptions.ConnectionClosedOK:
                logger.info("WebSocket connection closed normally.")
            except websockets.exceptions.ConnectionClosedError as e:
                logger.error(f"WebSocket connection closed with error: {e}")
            except Exception as e:
                logger.error(f"Error during WebSocket communication: {e}", exc_info=True)
            finally:
                logger.info("Stopping audio input...")
                audio_input_active.clear() # Stop the input callback from sending more

                logger.info("Signaling audio output player to stop...")
                await audio_output_queue.put(None) # Signal output player to stop
                await output_task # Wait for player to finish

    except websockets.exceptions.InvalidURI:
        logger.error(f"Invalid WebSocket URI: {uri}")
    except ConnectionRefusedError:
        logger.error(f"Connection refused for WebSocket URI: {uri}. Is the backend running?")
    except Exception as e:
        logger.error(f"Failed to connect to WebSocket: {e}", exc_info=True)
    finally:
        websocket_connection = None
        logger.info("WebSocket client finished.")


# --- Main Execution ---

async def main():
    global main_loop # Declare intent to modify global variable
    main_loop = asyncio.get_running_loop() # Get the main event loop

    # 1. Simulate the incoming call to get the WebSocket URL
    logger.info(f"Sending POST request to {INCOMING_CALL_ENDPOINT}")
    websocket_url = None
    try:
        response = requests.post(INCOMING_CALL_ENDPOINT)
        response.raise_for_status() # Raise exception for bad status codes
        logger.info(f"Received TwiML response (status: {response.status_code})")
        # logger.debug(f"TwiML Content: {response.text}")

        # Parse TwiML to find the WebSocket URL
        if response.headers.get('Content-Type') == 'application/xml' and response.text:
            tree = etree.fromstring(response.content)
            # Find <Stream> element and get its 'url' attribute
            stream_elements = tree.xpath('.//Stream')
            if stream_elements:
                websocket_url = stream_elements[0].get('url')
                logger.info(f"Extracted WebSocket URL from TwiML: {websocket_url}")
            else:
                logger.error("Could not find <Stream> element in TwiML response.")
                return # Exit if no URL
        else:
            logger.error(f"Unexpected response content type or empty body: {response.headers.get('Content-Type')}")
            return # Exit

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to make initial POST request: {e}")
        return # Exit if POST fails
    except etree.XMLSyntaxError as e:
        logger.error(f"Failed to parse TwiML response: {e}")
        return # Exit if TwiML parsing fails
    except Exception as e:
        logger.error(f"An unexpected error occurred during the POST request or TwiML parsing: {e}", exc_info=True)
        return

    if not websocket_url:
        logger.error("Failed to obtain WebSocket URL. Exiting.")
        return

    # 2. Start audio input stream
    logger.info(f"Starting audio input stream ({INPUT_SAMPLE_RATE} Hz)...")
    input_stream = None # Define variable to hold the stream object
    try:
        # Use sd.InputStream directly to manage it explicitly
        input_stream = sd.InputStream(samplerate=INPUT_SAMPLE_RATE,
                                      blocksize=BLOCK_SIZE,
                                      channels=INPUT_CHANNELS,
                                      dtype=INPUT_DTYPE,
                                      callback=audio_input_callback)
        input_stream.start() # Start the stream

        logger.info("Microphone stream started. Press Ctrl+C to stop.")
        # 3. Run the WebSocket client
        await websocket_client(websocket_url)

    except sd.PortAudioError as e:
        logger.error(f"PortAudio error: {e}. Do you have a working microphone connected and selected?")
        logger.error("Available input devices:")
        try:
            print(sd.query_devices())
        except Exception:
            logger.error("Could not query audio devices.")
    except Exception as e:
        logger.error(f"An error occurred in main execution: {e}", exc_info=True)
    finally:
        logger.info("Main execution finished.")
        # Ensure input is stopped if loop exits unexpectedly
        if input_stream:
            logger.info("Stopping microphone stream...")
            input_stream.stop()
            input_stream.close()
        audio_input_active.clear()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Ctrl+C detected. Shutting down.")
    finally:
        logger.info("Test client finished.")