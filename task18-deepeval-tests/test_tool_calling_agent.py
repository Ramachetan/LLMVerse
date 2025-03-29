# from deepeval.test_case import LLMTestCase, ToolCall


# # class ToolCall(BaseModel):
# #     name: str
# #     description: Optional[str] = None
# #     reasoning: Optional[str] = None
# #     output: Optional[Any] = None
# #     input_parameters: Optional[Dict[str, Any]] = None




# test_case = LLMTestCase(
#     input="Why did the chicken cross the road?",
#     actual_output=chatbot.run(input),
#     # Replace this with the tools that were actually used
#     tools_called=[
#         ToolCall(
#             name="Calculator Tool"
#             description="A tool that calculates mathematical equations or expressions.",
#             input={"user_input": "2+3"}
#             output=5
#         ),
#         ToolCall(
#             name="WebSearch Tool"
#             reasoning="Knowledge base does not detail why the chicken crossed the road."
#             input={"search_query": "Why did the chicken crossed the road?"}
#             output="Because it wanted to, duh."
#         )
#     ],
#     expected_tools=[
#         ToolCall(
#             name="Calculator Tool",
#             description="A tool that calculates mathematical equations or expressions.",
#             input={"user_input": "2+3"},
#             output=5
#         ),
#         ToolCall(
#             name="WebSearch Tool",
#             reasoning="Knowledge base does not detail why the chicken crossed the road.",
#             input={"search_query": "Why did the chicken crossed the road?"},
#             output="Because it wanted to, duh."
#         )
#     ],
# )

from deepeval import evaluate
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import ToolCorrectnessMetric

test_case = LLMTestCase(
    input="What if these shoes don't fit?",
    actual_output="We offer a 30-day full refund at no extra cost.",
    # Replace this with the tools that was actually used by your LLM agent
    tools_called=[ToolCall(name="WebSearch"), ToolCall(name="ToolQuery")],
    expected_tools=[ToolCall(name="WebSearch")],
)
metric = ToolCorrectnessMetric()

# To run metric as a standalone
# metric.measure(test_case)
# print(metric.score, metric.reason)

evaluate(test_cases=[test_case], metrics=[metric])