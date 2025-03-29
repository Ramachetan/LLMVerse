import google.generativeai as genai
from deepeval import evaluate
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import ToolCorrectnessMetric

# Configure Gemini Flash model
genai.configure(api_key="AIzaSyBuU0xrw9W5DyP1V0nwP2aj5--GCjuebUU")
model = genai.GenerativeModel("gemini-2.5-pro-exp-03-25")

# Define tools
def web_search(query):
    return f"Search results for: {query}"

def return_policy():
    return "We offer a 30-day full refund at no extra cost."

def get_weather(location):
    weather_data = {
        "New York": "Sunny, 75°F",
        "San Francisco": "Cloudy, 60°F",
        "Chicago": "Rainy, 65°F"
    }
    return weather_data.get(location, "Weather data unavailable.")

def get_tesla_stock():
    return "Tesla's current stock price is $670.42."

TOOLS = {
    "WebSearch": web_search,
    "ReturnPolicy": return_policy,
    "GetWeather": get_weather,
    "GetTeslaStock": get_tesla_stock,
}

# Agent function
def agent(input_text):
    response = model.generate_content(input_text)
    used_tools = []
    tool_results = []
    
    if "refund" in response.text.lower():
        used_tools.append("ReturnPolicy")
        tool_results.append(TOOLS["ReturnPolicy"]())
    if "weather" in response.text.lower():
        used_tools.append("GetWeather")
        tool_results.append(TOOLS["GetWeather"]("San Francisco"))
    if "tesla stock" in response.text.lower():
        used_tools.append("GetTeslaStock")
        tool_results.append(TOOLS["GetTeslaStock"]())
    if not used_tools:
        used_tools.append("WebSearch")
        tool_results.append(TOOLS["WebSearch"](input_text))
    
    return response.text, used_tools, tool_results

# Generate and evaluate test cases
test_cases = [
    LLMTestCase(
        input="What if these shoes don't fit?",
        actual_output="We offer a 30-day full refund at no extra cost.",
        tools_called=[ToolCall(name="ReturnPolicy")],
        expected_tools=[ToolCall(name="ReturnPolicy")],
    ),
    LLMTestCase(
        input="Find the best running shoes for marathon training.",
        actual_output="Here are some recommendations from online sources.",
        tools_called=[ToolCall(name="WebSearch")],
        expected_tools=[ToolCall(name="WebSearch")],
    ),
    LLMTestCase(
        input="Where can I buy Nike shoes online?",
        actual_output="You can find Nike shoes on Amazon, Nike's website, and other stores.",
        tools_called=[ToolCall(name="WebSearch")],
        expected_tools=[ToolCall(name="WebSearch")],
    ),
    LLMTestCase(
        input="What's the current weather in San Francisco and Tesla's stock price?",
        actual_output="San Francisco weather is Cloudy, 60°F. Tesla's stock price is $670.42.",
        tools_called=[ToolCall(name="GetWeather"), ToolCall(name="GetTeslaStock")],
        expected_tools=[ToolCall(name="GetWeather"), ToolCall(name="GetTeslaStock")],
    ),
    LLMTestCase(
        input="I need a refund for my order and also today's Tesla stock price.",
        actual_output="We offer a 30-day full refund at no extra cost. Tesla's stock price is $670.42.",
        tools_called=[ToolCall(name="ReturnPolicy"), ToolCall(name="GetTeslaStock")],
        expected_tools=[ToolCall(name="ReturnPolicy"), ToolCall(name="GetTeslaStock")],
    ),
]

metric = ToolCorrectnessMetric()
evaluate(test_cases=test_cases, metrics=[metric])