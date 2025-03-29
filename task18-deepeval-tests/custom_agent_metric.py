from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

# Custom metric to evaluate the performance of an agent wrt tool use and answer correctness
class CustomMetric(BaseMetric):
    def __init__(
            self,
            threshold: float = 0.5,
            # Optional
            # evaluation_model: str,
            include_reason: bool = True,
            strict_mode: bool = True,
            async_mode: bool = True
    ):
        self.threshold = threshold
        # self.evaluation_model = evaluation_model
        self.include_reason = include_reason
        self.strict_mode = strict_mode
        self.async_mode = async_mode

    @property
    def __name__(self):
        return "Agent tool calling metric"

    # measure and a_measure methods where the evaluation logic will be implemented
    def measure(self, test_case: LLMTestCase) -> float:
        # Implement the logic to measure the performance of the agent
        # based on the provided test_case.
        # This is where you would call the evaluation model and get the score.
        
        try:
            self.score = generate_hypothetical_score(test_case)
            if self.include_reason:
                self.reason = generate_hypothetical_reason(test_case)
            self.success = self.score >= self.threshold
            return self.score
        except Exception as e:
            # set metric error and re-raise it
            self.error = str(e)
            raise

    # async def a_measure(self, test_case: LLMTestCase) -> float:
    #     # Although not required, we recommend catching errors
    #     # in a try block
    #     try:
    #         self.score = await async_generate_hypothetical_score(test_case)
    #         if self.include_reason:
    #             self.reason = await async_generate_hypothetical_reason(test_case)
    #         self.success = self.score >= self.threshold
    #         return self.score
    #     except Exception as e:
    #         # set metric error and re-raise it
    #         self.error = str(e)
    #         raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)
    
    def is_successful(self) -> bool:
        if self.error is not None:
            self.success = False
        else:
            return self.success
        

#####################
### Example Usage ###
#####################
test_case = LLMTestCase(input="...", actual_output="...", expected_output="...")
metric = CustomMetric()

metric.measure(test_case)
print(metric.is_successful())