import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv
from pathlib import Path

from . import core # Import core logic

# --- App Setup ---
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env') # Load .env from backend dir
core.configure_genai() # Configure Google AI SDK

app = FastAPI()

# --- In-Memory Storage (MVP) ---
# Replace with a database for non-MVP
kb_store = {} # kb_id -> {"file_path": "...", "index_path": "...", "chunks_path": "..."}
agent_mapping = {
    # Example: "+15551234567": "kb_id_abc" # Populate manually or via API
    # Make sure the number format matches Twilio's 'To' parameter format
    # e.g., "+1201XXXXXXX"
}

# --- API Endpoints ---

@app.post("/api/kbs/upload")
async def upload_kb(file: UploadFile = File(...)):
    """Uploads a .txt file to create a knowledge base."""
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are allowed")

    kb_id = str(uuid.uuid4())
    file_location = core.KBS_DIR / f"{kb_id}.txt"

    try:
        # Save the uploaded file
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())

        # Process the file (chunk, embed, index)
        index_path, chunks_path = core.process_kb_file(file_location, kb_id)

        if index_path and chunks_path:
            kb_store[kb_id] = {
                "file_path": str(file_location),
                "index_path": index_path,
                "chunks_path": chunks_path
            }
            print(f"KB {kb_id} created and processed successfully.")
            return {"kb_id": kb_id, "filename": file.filename}
        else:
             # Cleanup if processing failed
             if file_location.exists():
                 file_location.unlink()
             raise HTTPException(status_code=500, detail=f"Failed to process file {file.filename}")

    except Exception as e:
        # Basic error handling
        print(f"Error during upload/processing: {e}")
        # Cleanup partial artifacts
        if file_location.exists():
            try:
                file_location.unlink()
            except OSError:
                pass # Ignore error during cleanup
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


# Minimal Agent Association (for manual setup or future UI)
@app.post("/api/agents/associate")
async def associate_agent(twilio_number: str = Form(...), kb_id: str = Form(...)):
    """Associates a Twilio number with a KB ID."""
    if kb_id not in kb_store:
        raise HTTPException(status_code=404, detail=f"KB ID '{kb_id}' not found.")
    agent_mapping[twilio_number] = kb_id
    print(f"Associated Twilio number {twilio_number} with KB {kb_id}")
    return {"message": f"Associated {twilio_number} with {kb_id}"}

# Endpoint used internally by Twilio handler
@app.get("/api/agents/get_kb")
async def get_kb_for_number(twilio_number: str):
    """Retrieves the KB ID for a given Twilio number."""
    kb_id = agent_mapping.get(twilio_number)
    if not kb_id:
        raise HTTPException(status_code=404, detail=f"No KB associated with number {twilio_number}")
    return {"kb_id": kb_id}


# --- Twilio Webhook Handler ---
@app.post("/api/twilio/voice", response_class=PlainTextResponse)
async def handle_twilio_voice(request: Request):
    """Handles incoming Twilio voice calls."""
    response = VoiceResponse()
    form_data = await request.form()
    twilio_number_called = form_data.get('To')
    user_query = form_data.get('SpeechResult') # Result from <Gather>

    print(f"Incoming call/request to {twilio_number_called}")
    print(f"Form Data: {form_data}")

    # 1. Find the associated KB ID
    kb_id = agent_mapping.get(twilio_number_called)

    if not kb_id:
        print(f"Error: No KB mapping found for {twilio_number_called}")
        response.say("I'm sorry, I'm not configured for this number.")
        response.hangup()
        return response.to_xml()

    if kb_id not in kb_store:
        print(f"Error: KB data not found for mapped KB ID {kb_id}")
        response.say("I'm sorry, there's an issue accessing the knowledge base for this number.")
        response.hangup()
        return response.to_xml()

    # 2. Handle the conversation flow
    if user_query:
        # User provided speech input via Gather
        print(f"User query (SpeechResult): {user_query}")

        # 3. Perform RAG to get the answer
        answer = core.get_rag_response(user_query, kb_id)
        print(f"LLM Answer: {answer}")

        # 4. Respond with the answer and gather next question
        response.say(answer)
        gather = Gather(input='speech', action='/api/twilio/voice', method='POST', speechTimeout='auto')
        gather.say("Do you have any other questions?")
        response.append(gather)
        # Alternative: Hang up after one question
        # response.say(answer)
        # response.say("Thank you for calling. Goodbye.")
        # response.hangup()

    else:
        # Initial call or loop without input - prompt for the first question
        print("Initial call or loop - gathering first/next question.")
        gather = Gather(input='speech', action='/api/twilio/voice', method='POST', speechTimeout='auto')
        gather.say("Hello! How can I help you based on the provided knowledge?")
        response.append(gather)
        # Add a fallback if gather fails
        response.say("Sorry, I didn't catch that. Please call again.")
        response.hangup()


    return response.to_xml()

# Optional: Add a root endpoint for health check
@app.get("/")
def read_root():
    return {"message": "KB Agent Backend is running"}