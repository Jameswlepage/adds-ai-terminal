from typing import Generator, Iterable, List, Mapping

from openai import OpenAI


class OpenAIClient:
    def __init__(self):
        self.client = OpenAI()

    def stream(self, model: str, input_payload: Iterable[Mapping[str, str]]) -> Generator[str, None, None]:
        stream = self.client.responses.create(model=model, input=list(input_payload), stream=True)
        for event in stream:
            if getattr(event, "type", None) == "response.output_text.delta":
                yield event.delta
