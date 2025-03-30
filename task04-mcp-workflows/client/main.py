import json
import re
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession
import chainlit as cl

SYSTEM = """You are a helpful assistant. You can call tools to perform specific tasks."""

load_dotenv()

API_KEY = os.getenv("API_KEY")


client = AsyncOpenAI(
    api_key="AIzaSyDbfYYwjACy6B6ciVeT5rWQCupxv-XyBnc",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


def flatten(xss):
    return [x for xs in xss for x in xs]


def sanitize_description(description):
    """Sanitize tool descriptions to match the required pattern.
    Only allows alphanumeric characters, specific punctuation, and spaces."""
    # Replace any non-matching characters with spaces
    allowed_pattern = r'[^a-zA-Z0-9_\-\'".,?!:;{}\(\)\[\] ]'
    return re.sub(allowed_pattern, ' ', description)


@cl.on_mcp_connect
async def on_mcp(connection, session: ClientSession):
    result = await session.list_tools()
    tools = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": sanitize_description(t.description),
                "parameters": t.inputSchema,
            }
        }
        for t in result.tools
    ]

    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)


async def call_tool(tool_use):
    tool_name = tool_use["name"]
    tool_input = tool_use["input"]

    current_step = cl.context.current_step
    current_step.name = tool_name

    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_name = None

    for connection_name, tools in mcp_tools.items():
        if any(tool.get("function", {}).get("name") == tool_name for tool in tools):
            mcp_name = connection_name
            break

    if not mcp_name:
        current_step.output = json.dumps(
            {"error": f"Tool {tool_name} not found in any MCP connection"}
        )
        return current_step.output

    mcp_session, _ = cl.context.session.mcp_sessions.get(mcp_name)

    if not mcp_session:
        current_step.output = json.dumps(
            {"error": f"MCP {mcp_name} not found in any MCP connection"}
        )
        return current_step.output

    try:
        current_step.output = await mcp_session.call_tool(tool_name, tool_input)
    except Exception as e:
        current_step.output = json.dumps({"error": str(e)})

    return current_step.output


async def call_openai(chat_messages):
    mcp_tools = cl.user_session.get("mcp_tools", {})
    tools = flatten([tools for _, tools in mcp_tools.items()])

    openai_messages = [{"role": "system", "content": SYSTEM}]
    openai_messages.extend(chat_messages)

    try:
        response = await client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=openai_messages,
            max_tokens=1024,
            temperature=0.7,
            tools=tools if tools else None,
        )
        return response
    except Exception as e:
        await cl.Message(content=f"Error: {str(e)}").send()
        return None


@cl.on_chat_start
async def start_chat():
    cl.user_session.set("chat_messages", [])


@cl.on_message
async def on_message(msg: cl.Message):
    chat_messages = cl.user_session.get("chat_messages")
    chat_messages.append({"role": "user", "content": msg.content})

    response = await call_openai(chat_messages)
    if not response:
        return

    assistant_message = response.choices[0].message
    if assistant_message.tool_calls:
        chat_messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                        "type": "function",
                    }
                    for tool_call in assistant_message.tool_calls
                ],
            }
        )

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            tool_input = json.loads(tool_call.function.arguments)
            tool_id = tool_call.id
            await cl.Message(
                content=f"Calling tool: {tool_name}", author="System"
            ).send()

            tool_result = await call_tool({"name": tool_name, "input": tool_input})
            chat_messages.append(
                {"role": "tool", "tool_call_id": tool_id, "content": str(tool_result)}
            )

        follow_up_response = await call_openai(chat_messages)
        if follow_up_response:
            final_content = follow_up_response.choices[0].message.content
            final_message = cl.Message(content=final_content)
            await final_message.send()

            chat_messages.append({"role": "assistant", "content": final_content})
    else:
        final_message = cl.Message(content=assistant_message.content)
        await final_message.send()

        chat_messages.append(
            {"role": "assistant", "content": assistant_message.content}
        )

    cl.user_session.set("chat_messages", chat_messages)