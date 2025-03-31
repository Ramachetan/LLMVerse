import json
import os
from dotenv import load_dotenv

# Use AsyncOpenAI for compatibility with Chainlit's async nature
from openai import AsyncOpenAI

from mcp import ClientSession
import chainlit as cl

# --- Configuration ---
load_dotenv() # Load environment variables from .env file if it exists

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

# Initialize OpenAI client pointing to Gemini endpoint
client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta" # Updated Base URL as per Gemini docs
)

# Select your desired Gemini model compatible with the API endpoint
# Example: gemini-1.5-flash-latest or gemini-pro
MODEL_NAME = "gemini-2.0-flash" # Or "gemini-pro" etc.

SYSTEM_PROMPT = "You are a helpful assistant that can use tools."
# ---------------

# Helper to flatten lists (remains the same)
def flatten(xss):
    return [x for xs in xss for x in xs]

@cl.on_mcp_connect
async def on_mcp_connect(connection, session: ClientSession):
    """
    Called when a user connects to an MCP server.
    Discover tools and store their metadata (name, description, input_schema).
    """
    print(f"Attempting to connect to MCP: {connection.name}")
    try:
        result = await session.list_tools()
        # Store the original MCP tool metadata. We'll format it for OpenAI later.
        tools_metadata = [{
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema, # Keep the original schema here
            "mcp_connection_name": connection.name # Store which connection owns this tool
        } for t in result.tools]

        mcp_tools = cl.user_session.get("mcp_tools", {})
        mcp_tools[connection.name] = tools_metadata # Store by connection name
        cl.user_session.set("mcp_tools", mcp_tools)

        tool_names = [t['name'] for t in tools_metadata]
        print(f"Successfully connected to MCP '{connection.name}' and found tools: {tool_names}")
        await cl.Message(content=f"Connected to MCP server '{connection.name}' and found tools: {', '.join(tool_names)}").send()

    except Exception as e:
        print(f"Error connecting to or listing tools for MCP '{connection.name}': {e}")
        await cl.ErrorMessage(f"Failed to list tools from MCP server '{connection.name}': {e}").send()


@cl.on_mcp_disconnect
async def on_mcp_disconnect(name: str, session: ClientSession):
    """
    OPTIONAL: Called when an MCP connection is closed. Clean up stored tools.
    """
    print(f"MCP Connection '{name}' disconnected.")
    mcp_tools = cl.user_session.get("mcp_tools", {})
    if name in mcp_tools:
        del mcp_tools[name]
        cl.user_session.set("mcp_tools", mcp_tools)
    # Optional: Send a message to the user
    # await cl.Message(f"Disconnected from MCP server '{name}'.").send()


@cl.step(type="tool")
async def call_mcp_tool(tool_call):
    """
    Executes a tool call requested by the LLM using the appropriate MCP session.
    Accepts an OpenAI tool_call object.
    """
    tool_name = tool_call.function.name
    try:
        # Arguments are provided as a JSON string by OpenAI
        tool_input = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        error_msg = f"Error: Invalid JSON arguments received for tool {tool_name}: {tool_call.function.arguments}"
        print(error_msg)
        # Update the step directly if possible, otherwise return error
        cl.context.current_step.output = json.dumps({"error": error_msg})
        cl.context.current_step.is_error = True
        return json.dumps({"error": error_msg}) # Return error string for LLM

    current_step = cl.context.current_step
    current_step.name = tool_name # Set step name in UI
    current_step.input = tool_input # Show input arguments in UI

    print(f"Attempting to call MCP tool: {tool_name} with args: {tool_input}")

    # Find which MCP connection provides this tool
    mcp_tools_by_connection = cl.user_session.get("mcp_tools", {})
    mcp_connection_name = None
    for conn_name, tools_metadata in mcp_tools_by_connection.items():
        for tool_meta in tools_metadata:
            if tool_meta["name"] == tool_name:
                mcp_connection_name = conn_name
                break
        if mcp_connection_name:
            break

    if not mcp_connection_name:
        error_msg = f"Tool '{tool_name}' not found in any active MCP connection."
        print(error_msg)
        current_step.output = json.dumps({"error": error_msg})
        current_step.is_error = True
        return json.dumps({"error": error_msg})

    # Get the MCP session for the identified connection
    mcp_session_tuple = cl.context.session.mcp_sessions.get(mcp_connection_name) # Renamed in newer Chainlit? Check cl.context? yes, cl.context.session
    if not mcp_session_tuple:
        error_msg = f"Active MCP session for connection '{mcp_connection_name}' not found."
        print(error_msg)
        current_step.output = json.dumps({"error": error_msg})
        current_step.is_error = True
        return json.dumps({"error": error_msg})

    mcp_session: ClientSession = mcp_session_tuple[0] # Get the session object

    # Call the tool via MCP
    try:
        # Use ctx.info/report_progress within the MCP server tool for better feedback
        print(f"Calling MCP tool '{tool_name}' via session for '{mcp_connection_name}'...")
        result = await mcp_session.call_tool(tool_name, arguments=tool_input)
        print(f"MCP tool '{tool_name}' returned: {result}")
        # Store result (can be string, dict, etc.) in the step output for UI
        # Try to serialize complex results nicely for the step UI
        if isinstance(result, (dict, list)):
           current_step.output = json.dumps(result, indent=2)
        else:
           current_step.output = str(result)
        # Return the raw result for the LLM (needs to be a string for OpenAI content)
        return str(result) # Ensure result is a string for the OpenAI tool message content
    except Exception as e:
        error_msg = f"Error executing MCP tool '{tool_name}': {e}"
        print(error_msg)
        current_step.output = json.dumps({"error": error_msg})
        current_step.is_error = True
        # Return error details stringified for the LLM
        return json.dumps({"error": error_msg})


def format_mcp_tools_for_openai(mcp_tools_by_connection):
    """
    Converts the stored MCP tool metadata into the format expected
    by the OpenAI API's 'tools' parameter.
    """
    openai_tools = []
    all_mcp_tools = flatten(list(mcp_tools_by_connection.values())) # Get all tools from all connections

    for tool_meta in all_mcp_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool_meta["name"],
                "description": tool_meta["description"],
                "parameters": tool_meta["input_schema"] # Directly use the JSON schema
            }
        })
    return openai_tools


async def call_gemini(chat_messages):
    """
    Calls the Gemini model via the OpenAI SDK compatibility layer,
    handles streaming, and tool calls.
    """
    msg = cl.Message(content="")
    await msg.send() # Send message shell immediately

    mcp_tools_by_connection = cl.user_session.get("mcp_tools", {})
    # Format the discovered MCP tools for the OpenAI API call
    tools_for_openai = format_mcp_tools_for_openai(mcp_tools_by_connection)

    print("-" * 50)
    print(f"Calling Gemini ({MODEL_NAME}) with {len(chat_messages)} messages.")
    # print("Messages:", json.dumps(chat_messages, indent=2)) # Debug: Print messages sent
    if tools_for_openai:
        print(f"Providing {len(tools_for_openai)} tools to Gemini.")
        # print("Tools:", json.dumps(tools_for_openai, indent=2)) # Debug: Print tools sent
    else:
        print("No MCP tools available.")
    print("-" * 50)

    try:
        # Prepare arguments for the API call
        api_args = {
            "model": MODEL_NAME,
            "messages": chat_messages,
            "stream": True,
            "temperature": 0.5, # Adjust creativity as needed
            # "max_tokens": 1024 # Optional: set max response length
        }
        # Only include tools if there are any
        if tools_for_openai:
            api_args["tools"] = tools_for_openai
            api_args["tool_choice"] = "auto" # Let the model decide when to use tools

        # Make the streaming API call
        stream_resp = await client.chat.completions.create(**api_args)

        full_response_content = ""
        tool_calls_accumulated = [] # Store tool calls received during streaming

        # Process the stream
        async for chunk in stream_resp:
            delta = chunk.choices[0].delta
            # Stream text content
            if delta.content:
                # print(delta.content, end="", flush=True) # Debug: print stream in console
                await msg.stream_token(delta.content)
                full_response_content += delta.content

            # Accumulate tool calls - OpenAI SDK aggregates these in the delta
            if delta.tool_calls:
                # print(f"\nReceived tool call chunk: {delta.tool_calls}") # Debug
                # Need to handle potential multiple chunks for the same tool call (e.g., name then args)
                # The SDK might aggregate these, or we might need manual aggregation.
                # Let's assume the SDK gives complete tool_call objects eventually.
                # We'll process them *after* the stream ends from the final message object.
                # For now, just note that tool calls were initiated.
                pass # We'll get the full tool_calls list from the final response object

        # print("\nStream finished.") # Debug
        await msg.update() # Finalize the streamed message in UI

        # After streaming, assemble the final assistant message object
        # The OpenAI SDK (newer versions) should ideally provide a way to get the
        # final assembled message after streaming, but let's construct it manually
        # if needed based on observed stream behavior.
        # A common pattern is that the last chunk or the stream object itself
        # might contain the aggregated tool_calls. Let's rely on manually
        # constructing the assistant message for now.

        # HACK/Workaround: Make a non-streaming call to easily get the final message state
        # This avoids complexity in reconstructing the message from stream chunks,
        # especially for tool calls. This is less efficient but more reliable for parsing.
        # If efficiency is paramount, careful stream chunk aggregation is needed.
        print("Making non-streaming call to get final message object with tool calls...")
        final_response = await client.chat.completions.create(**{**api_args, "stream": False})
        assistant_message = final_response.choices[0].message
        print(f"Final Assistant Message: {assistant_message}") # Debug

        return assistant_message # Return the complete openai.types.chat.ChatCompletionMessage object

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        await msg.setError(f"Error communicating with Gemini: {e}")
        await msg.update()
        # Return None or raise to indicate failure
        return None


@cl.on_chat_start
async def start_chat():
    """Initializes chat history and MCP tools storage."""
    cl.user_session.set("chat_messages", [{"role": "system", "content": SYSTEM_PROMPT}])
    cl.user_session.set("mcp_tools", {}) # Initialize MCP tools dictionary
    print("Chat started. Initialized chat history and MCP tools.")
    await cl.Message(content="Hello! How can I help you today? Connect to MCP servers using the bolt icon (⚡️) to enable tools.").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handles incoming user messages, calls LLM, and manages tool execution loop."""
    chat_messages = cl.user_session.get("chat_messages")

    # Append user message
    chat_messages.append({"role": "user", "content": message.content})

    while True: # Loop to handle potential sequences of tool calls
        # Call the LLM (Gemini)
        assistant_response_message = await call_gemini(chat_messages)

        if not assistant_response_message:
            # Error occurred in call_gemini, stop processing
            await cl.ErrorMessage("Failed to get a response from the assistant.").send()
            # Restore messages in case of error? Maybe just stop.
            # chat_messages.pop() # Remove last user message if needed?
            return

        # Append the assistant's response (which might include tool calls)
        # We need to convert the Pydantic model to a dict for storing in session
        chat_messages.append(assistant_response_message.model_dump(exclude_unset=True)) # Use .model_dump() for OpenAI v1+

        # Check if the assistant requested tool calls
        if not assistant_response_message.tool_calls:
            # No tool calls, the conversation turn is complete.
            # The final text response was already streamed by call_gemini.
            print("Assistant response received (no tool calls).")
            break # Exit the tool loop

        # --- Tool Call Execution ---
        print(f"Assistant requested {len(assistant_response_message.tool_calls)} tool call(s).")
        tool_messages_for_llm = [] # To store results to send back

        # Execute each tool call sequentially
        for tool_call in assistant_response_message.tool_calls:
            if tool_call.type == "function":
                # Use the @cl.step decorated function
                tool_result_content = await call_mcp_tool(tool_call) # call_mcp_tool handles the step UI

                # Append the tool result message for the next LLM call
                tool_messages_for_llm.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id, # Crucial: Link result to the call
                    "content": tool_result_content, # Result from call_mcp_tool (stringified)
                })
            else:
                print(f"Warning: Received unsupported tool call type: {tool_call.type}")

        # Append all tool results to the chat history
        chat_messages.extend(tool_messages_for_llm)
        print("Appended tool results to history. Continuing conversation with LLM...")
        # Loop continues: call call_gemini again with the history including tool results

    # Update the session with the final chat history after the loop finishes
    cl.user_session.set("chat_messages", chat_messages)
    print("Conversation turn complete.")
