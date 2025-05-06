import os
import asyncio
import logging
from datetime import timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
# Import GenAI libraries
# Ensure you have installed the correct package: pip install google-generativeai
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions # For specific error handling
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from dotenv import load_dotenv

# --- Configuration ---
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if present
load_dotenv()

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CLIENT = None
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY environment variable not set. LLM functionality will be disabled.")
    # Optionally raise an error if LLM is critical:
    # raise ValueError("GEMINI_API_KEY environment variable not set.")
else:
    try:
        # Initialize the Gemini client with the new API structure
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Google GenAI client configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure Google GenAI client: {e}", exc_info=True)
        GEMINI_CLIENT = None # Disable LLM if configuration fails

# --- Pydantic Models ---
class IngestRequest(BaseModel):
    url: str = Field(..., examples=["https://docs.python.org/3/tutorial/classes.html"])
    frequency: str = Field(..., examples=["5s", "1m", "1h"], description="Frequency in format like '5s', '10m', '1h'")
    # Add new fields for LLM
    instruction: Optional[str] = Field(None, examples=["Extract the main headings and summarize the content."], description="Instructions for the LLM to process the page content.")
    use_llm: bool = Field(False, description="Set to true to process content with the LLM using the provided instruction.")

    @field_validator('frequency')
    @classmethod
    def validate_frequency(cls, v):
        """Parses and validates the frequency string."""
        try:
            unit = v[-1].lower()
            value = int(v[:-1])
            if unit == 's':
                return timedelta(seconds=value)
            elif unit == 'm':
                return timedelta(minutes=value)
            elif unit == 'h':
                return timedelta(hours=value)
            else:
                raise ValueError("Invalid frequency unit. Use 's', 'm', or 'h'.")
        except (ValueError, IndexError):
            raise ValueError("Invalid frequency format. Use format like '5s', '10m', '1h'.")

    @field_validator('use_llm')
    @classmethod
    def check_llm_requirements(cls, use_llm, values):
        """Validate that if use_llm is True, instruction is present. Warn if API key is missing."""
        # Need to access 'instruction' which comes after 'use_llm' in definition
        # Pydantic v2 passes all validated fields so far in 'values.data'
        instruction = values.data.get('instruction')
        if use_llm:
            if not instruction:
                raise ValueError("Instruction must be provided when use_llm is True.")
            if not GEMINI_CLIENT:
                # Warn instead of raising an error
                logger.warning("GEMINI_CLIENT is not configured. LLM processing will likely fail.")
                # raise ValueError("Cannot use LLM because GEMINI_API_KEY is not configured.") # Original line
        return use_llm


# --- LLM Logic ---
async def generate_content_with_llm(html_content: str, instruction: str) -> Optional[str]:
    """
    Uses Google Gemini to generate content based on HTML and an instruction.

    Args:
        html_content: The HTML content of the page.
        instruction: The instruction for the LLM.

    Returns:
        The generated text content, or None if an error occurs.
    """
    if not GEMINI_CLIENT:
        logger.error("LLM processing skipped: GEMINI_API_KEY not configured.")
        return None

    logger.info(f"Generating content with LLM. Instruction: '{instruction[:100]}...'")
    # Limit HTML size to avoid exceeding token limits (adjust as needed)
    max_html_length = 100000 # Example limit, tune based on model and typical page size
    if len(html_content) > max_html_length:
        logger.warning(f"HTML content truncated to {max_html_length} characters for LLM processing.")
        html_content = html_content[:max_html_length]

    # Prepare the content for the LLM
    model_name = "gemini-2.5-flash-preview-04-17"
    
    try:
        # Format content according to the new API structure
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"{instruction}\n\nHere is the HTML content of the page:\n\n```html\n{html_content}\n```"
                    ),
                ],
            ),
        ]
        
        # Configure generation parameters
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
            system_instruction=[
                types.Part.from_text(text="You are an AI assistant that extracts and processes web content."),
            ],
        )
        
        # Non-streaming generation
        response = await asyncio.to_thread(
            GEMINI_CLIENT.models.generate_content,
            model=model_name,
            contents=contents,
            config=generate_content_config,
        )
        
        if not response or not hasattr(response, 'text'):
            logger.error("LLM response blocked or empty.")
            return None

        generated_text = response.text
        logger.info(f"LLM generated content successfully (length: {len(generated_text)}).")
        logger.info("\nFirst 500 chars of LLM content:")
        logger.info(generated_text[:500])
        return generated_text

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Google API error during LLM generation: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error during LLM generation: {e}", exc_info=True)
        return None


# --- Crawler & Processing Logic ---
# Renamed function and added llm parameters
async def crawl_and_process_content(url: str, instruction: Optional[str] = None, use_llm: bool = False):
    """
    Performs web crawling and either extracts Markdown or processes HTML with LLM.

    Args:
        url: The URL to crawl.
        instruction: Instruction for the LLM (if use_llm is True).
        use_llm: Flag to indicate whether to use the LLM.

    Returns:
        The processed content (Markdown or LLM output) as a string, or None.
    """
    logger.info(f"Starting crawl and process for URL: {url} (use_llm={use_llm})")
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
    )
    # Disable markdown extraction if using LLM, enable if not
    # Ensure HTML is extracted if using LLM
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url, config=run_config)

            if not result:
                logger.error(f"Failed to retrieve content from URL: {url}")
                return None

            if use_llm:
                if not instruction:
                    logger.error(f"Cannot use LLM for {url}: Instruction is missing.")
                    return None
                if not result.html:
                    logger.error(f"Cannot use LLM for {url}: Failed to extract HTML.")
                    return None
                logger.info(f"HTML content length for LLM processing: {len(result.html)}")
                # Call the LLM function
                processed_content = await generate_content_with_llm(result.html, instruction)
                if processed_content:
                    logger.info(f"Successfully processed content with LLM for URL: {url}")
                else:
                    logger.error(f"LLM processing failed for URL: {url}")
                return processed_content # Return LLM output or None
            else:
                # Original Markdown extraction logic
                # Check the correct attribute name based on the parameter used
                if not result.markdown: # Reverted attribute name
                    logger.error(f"Failed to extract markdown from URL: {url}")
                    return None
                markdown_content = result.markdown # Reverted attribute name
                logger.info(f"Successfully crawled URL: {url}. Markdown length: {len(markdown_content)}")
                logger.info("\nFirst 500 chars of markdown content:")
                logger.info(markdown_content[:500])
                return markdown_content

    except Exception as e:
        logger.error(f"Error during crawl/process for {url}: {e}", exc_info=True)
        return None

# --- Background Task ---
# Added instruction and use_llm parameters
async def periodic_crawl_task(url: str, frequency_delta: timedelta, instruction: Optional[str], use_llm: bool):
    """
    Runs the crawl_and_process_content function periodically in the background.

    Args:
        url: The URL to crawl.
        frequency_delta: The time interval between crawls.
        instruction: Instruction for the LLM (passed to crawl_and_process_content).
        use_llm: Flag for using LLM (passed to crawl_and_process_content).
    """
    logger.info(f"Starting periodic task for {url} with frequency {frequency_delta} (use_llm={use_llm})")
    while True:
        try:
            # Call the updated crawl/process function
            processed_content = await crawl_and_process_content(url, instruction, use_llm)

            if processed_content:
                content_type = "LLM output" if use_llm else "Markdown content"
                logger.info(f"{content_type} received for {url} (first 500 chars):\n{processed_content[:500]}")
                # --- Process the content ---
                # Example: Save to a file, store in DB, etc.
                # filename = f"{url.replace('https://', '').replace('/', '_')}_{datetime.now().isoformat()}.{'txt' if use_llm else 'md'}"
                # with open(filename, "w", encoding="utf-8") as f:
                #     f.write(processed_content)
                # logger.info(f"Saved content to {filename}")
            else:
                logger.warning(f"No content obtained for {url} in this cycle.")

            # Wait for the next cycle
            await asyncio.sleep(frequency_delta.total_seconds())

        except asyncio.CancelledError:
            logger.info(f"Periodic task for {url} cancelled.")
            break # Exit the loop if the task is cancelled
        except Exception as e:
            # Log errors but continue the loop
            logger.error(f"Unexpected error in periodic task for {url}: {e}", exc_info=True)
            # Optional: Implement a backoff strategy before retrying
            await asyncio.sleep(frequency_delta.total_seconds()) # Wait before retrying


# --- FastAPI Application ---
app = FastAPI(
    title="Crawler Ingestion Service",
    # Updated description
    description="API to periodically crawl URLs, extract markdown, or process content with an LLM.",
)

# In-memory store to keep track of running tasks (simple approach)
# Key: URL, Value: asyncio.Task
# WARNING: This is a basic implementation. In production, consider more robust task management.
running_tasks = {}

@app.post("/ingest", status_code=202)
async def ingest_url(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Accepts a URL, frequency, and optional LLM instructions.
    Starts a periodic background task to crawl and process content.
    """
    # Updated log message
    logger.info(f"Received ingest request for URL: {request.url} with frequency: {request.frequency}, use_llm: {request.use_llm}")
    if request.use_llm:
         logger.info(f"LLM Instruction provided: '{request.instruction[:100]}...'")


    # --- Task Management (Basic Example) ---
    # Optional: Check if a task for this URL is already running and decide how to handle it
    # (e.g., cancel the old one, return an error, or allow multiple).
    # Here, we'll cancel any existing task for the same URL before starting a new one.
    if request.url in running_tasks:
        existing_task = running_tasks[request.url]
        if not existing_task.done():
            logger.warning(f"Task already running for {request.url}. Cancelling previous task.")
            existing_task.cancel()
            try:
                await existing_task # Allow cancellation to propagate
            except asyncio.CancelledError:
                logger.info(f"Previous task for {request.url} successfully cancelled.")
            except Exception as e:
                logger.error(f"Error awaiting cancellation of previous task for {request.url}: {e}")
        del running_tasks[request.url] # Remove from tracking

    # --- Start Background Task ---
    # Pass new parameters to the periodic task
    task = asyncio.create_task(
        periodic_crawl_task(
            request.url,
            request.frequency,
            request.instruction,
            request.use_llm
        )
    )
    running_tasks[request.url] = task # Track the new task

    logger.info(f"Background task created for {request.url}")

    # Updated response message
    return {"message": f"Ingestion task started for {request.url} with frequency {request.frequency} (use_llm={request.use_llm})"}

@app.get("/status")
async def get_status():
    """Returns the status of running ingestion tasks."""
    active_tasks = {url: not task.done() for url, task in running_tasks.items() if not task.done()}
    return {"running_tasks": active_tasks, "total_tracked": len(running_tasks)}

# --- Main Execution (for running with uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server with Uvicorn...")
    # Note: Uvicorn should ideally be run from the command line:
    # uvicorn your_filename:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
