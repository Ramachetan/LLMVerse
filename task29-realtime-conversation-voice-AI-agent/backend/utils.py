import audioop
import logging


logger = logging.getLogger(__name__)

# Audio Format Specifics
TWILIO_SAMPLE_RATE = 8000
TWILIO_AUDIO_FORMAT = "audio/x-mulaw" # Twilio uses μ-law
GEMINI_INPUT_SAMPLE_RATE = 16000
GEMINI_OUTPUT_SAMPLE_RATE = 24000
GEMINI_AUDIO_FORMAT = "audio/pcm" # Gemini uses Linear16 PCM

def reset_resample_states():
    global resample_state_8k_to_16k, resample_state_24k_to_8k
    resample_state_8k_to_16k = None
    resample_state_24k_to_8k = None
    logger.debug("Audio resampling states reset.")

def mulaw8k_to_pcm16k(mulaw_data: bytes) -> bytes:
    """Convert 8-bit mulaw@8kHz to 16-bit PCM@16kHz (basic resampling)"""
    global resample_state_8k_to_16k
    try:
        # 1. Convert 8-bit mulaw to 16-bit linear PCM (still @ 8kHz)
        pcm_8k_data = audioop.ulaw2lin(mulaw_data, 2) # 2 bytes per sample output

        # 2. Resample 8kHz to 16kHz using audioop.ratecv (basic quality)
        # Parameters: (fragment, sampwidth, nchannels, inrate, outrate, state)
        pcm_16k_data, resample_state_8k_to_16k = audioop.ratecv(
            pcm_8k_data, 2, 1, TWILIO_SAMPLE_RATE, GEMINI_INPUT_SAMPLE_RATE, resample_state_8k_to_16k
        )
        return pcm_16k_data
    except audioop.error as e:
        logger.error(f"Audioop error during mulaw->pcm16k conversion: {e}")
        return b"" # Return empty bytes on error


def pcm24k_to_mulaw8k(pcm_data: bytes) -> bytes:
    """Convert 16-bit PCM@24kHz to 8-bit mulaw@8kHz (basic resampling)"""
    global resample_state_24k_to_8k
    
    if not pcm_data:
        logger.warning("Received empty PCM data for conversion")
        return b""
        
    try:
        logger.debug(f"Converting {len(pcm_data)} bytes of PCM data")
        
        # Check if the input data is actually 16-bit (2 bytes per sample)
        if len(pcm_data) % 2 != 0:
            logger.error(f"PCM data length ({len(pcm_data)}) is not divisible by 2. Padding with zero.")
            pcm_data += b'\x00'  # Pad with a zero byte
            
        # 1. Resample 24kHz to 8kHz using audioop.ratecv (basic quality)
        pcm_8k_data, resample_state_24k_to_8k = audioop.ratecv(
            pcm_data, 2, 1, GEMINI_OUTPUT_SAMPLE_RATE, TWILIO_SAMPLE_RATE, resample_state_24k_to_8k
        )
        logger.debug(f"Resampled to {len(pcm_8k_data)} bytes")
        
        # 2. Convert 16-bit linear PCM to 8-bit mulaw
        mulaw_data = audioop.lin2ulaw(pcm_8k_data, 2)
        logger.debug(f"Converted to {len(mulaw_data)} bytes of μ-law")
        
        return mulaw_data
    except audioop.error as e:
        logger.error(f"Audioop error during pcm24k->mulaw8k conversion: {e}")
        # Dump first few bytes for debugging
        if pcm_data:
            logger.error(f"First 20 bytes of problematic PCM data: {pcm_data[:20].hex()}")
        return b""  # Return empty bytes on error
    except Exception as e:
        logger.error(f"Unexpected error in pcm24k->mulaw8k: {type(e).__name__} - {e}", exc_info=True)
        return b""