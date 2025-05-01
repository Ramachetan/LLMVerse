import logging
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import io

logger = logging.getLogger(__name__)

# Audio Format Specifics (Keep these for clarity)
TWILIO_SAMPLE_RATE = 8000
TWILIO_CHANNELS = 1
TWILIO_SAMPLE_WIDTH = 1 # bytes per sample for mulaw

GEMINI_INPUT_SAMPLE_RATE = 16000
GEMINI_INPUT_CHANNELS = 1
GEMINI_INPUT_SAMPLE_WIDTH = 2 # bytes per sample for 16-bit PCM

GEMINI_OUTPUT_SAMPLE_RATE = 24000
GEMINI_OUTPUT_CHANNELS = 1
GEMINI_OUTPUT_SAMPLE_WIDTH = 2 # bytes per sample for 16-bit PCM

# No longer needed with pydub's approach
# def reset_resample_states():
#     pass # Keep the function signature if called elsewhere, but do nothing

def mulaw8k_to_pcm16k(mulaw_data: bytes) -> bytes:
    """Convert 8-bit mulaw@8kHz/mono to 16-bit PCM@16kHz/mono using pydub"""
    if not mulaw_data:
        return b""
    try:
        # 1. Create AudioSegment from raw mulaw data
        audio_segment = AudioSegment(
            data=mulaw_data,
            sample_width=TWILIO_SAMPLE_WIDTH,
            frame_rate=TWILIO_SAMPLE_RATE,
            channels=TWILIO_CHANNELS
        )

        # 2. Resample to Gemini's input rate (16kHz)
        # Pydub handles conversion to PCM implicitly when changing sample rate/width
        audio_segment = audio_segment.set_frame_rate(GEMINI_INPUT_SAMPLE_RATE)

        # 3. Ensure it's 16-bit (set_sample_width)
        audio_segment = audio_segment.set_sample_width(GEMINI_INPUT_SAMPLE_WIDTH)

        # 4. Ensure mono
        audio_segment = audio_segment.set_channels(GEMINI_INPUT_CHANNELS)

        # 5. Get the raw PCM data
        pcm_16k_data = audio_segment.raw_data
        # logger.debug(f"Converted {len(mulaw_data)} mulaw bytes to {len(pcm_16k_data)} PCM 16kHz bytes")
        return pcm_16k_data

    except CouldntDecodeError as e:
        logger.error(f"Pydub couldn't decode mulaw data: {e}")
        return b""
    except Exception as e:
        logger.error(f"Error during mulaw->pcm16k conversion with pydub: {type(e).__name__} - {e}", exc_info=True)
        return b""


def pcm24k_to_mulaw8k(pcm_data: bytes) -> bytes:
    """Convert 16-bit PCM@24kHz/mono to 8-bit mulaw@8kHz/mono using pydub"""
    if not pcm_data:
        # logger.warning("Received empty PCM data for conversion")
        return b""

    # Ensure data length is even for 16-bit PCM
    if len(pcm_data) % GEMINI_OUTPUT_SAMPLE_WIDTH != 0:
        logger.warning(f"PCM data length ({len(pcm_data)}) is not a multiple of sample width ({GEMINI_OUTPUT_SAMPLE_WIDTH}). Truncating last byte.")
        pcm_data = pcm_data[:-1] # Truncate the last byte
        if not pcm_data:
             logger.error("PCM data became empty after truncation.")
             return b""

    try:
        # logger.debug(f"Converting {len(pcm_data)} bytes of PCM 24kHz data")
        # 1. Create AudioSegment from raw PCM data
        audio_segment = AudioSegment(
            data=pcm_data,
            sample_width=GEMINI_OUTPUT_SAMPLE_WIDTH,
            frame_rate=GEMINI_OUTPUT_SAMPLE_RATE,
            channels=GEMINI_OUTPUT_CHANNELS
        )

        # 2. Resample down to Twilio's rate (8kHz)
        audio_segment = audio_segment.set_frame_rate(TWILIO_SAMPLE_RATE)

        # 3. Ensure mono
        audio_segment = audio_segment.set_channels(TWILIO_CHANNELS)

        # 4. Export as mulaw
        # We use BytesIO to capture the output of export
        buffer = io.BytesIO()
        # Specify codec explicitly for raw mulaw output
        audio_segment.export(buffer, format="mulaw", codec="pcm_mulaw")
        mulaw_data = buffer.getvalue()
        buffer.close()

        # logger.debug(f"Converted to {len(mulaw_data)} bytes of μ-law 8kHz")
        return mulaw_data

    except CouldntDecodeError as e:
        logger.error(f"Pydub couldn't decode PCM data: {e}")
        return b""
    except Exception as e:
        logger.error(f"Error during pcm24k->mulaw8k conversion with pydub: {type(e).__name__} - {e}", exc_info=True)
        # Dump first few bytes for debugging
        if pcm_data:
            logger.error(f"First 20 bytes of problematic PCM data: {pcm_data[:20].hex()}")
        return b""