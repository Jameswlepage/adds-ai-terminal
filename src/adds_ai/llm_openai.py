from dataclasses import dataclass, field
from typing import Generator, Iterable, List, Mapping, Optional

from openai import OpenAI

# Pricing per 1M tokens (as of late 2024)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


@dataclass
class StreamResult:
    text: str = ""
    citations: List[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class OpenAIClient:
    def __init__(self):
        self.client = OpenAI()
        self.session_tokens = 0
        self.session_cost = 0.0

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("gpt-4o-mini"))
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def stream(
        self,
        model: str,
        input_payload: Iterable[Mapping[str, str]],
        web_search: bool = False,
    ) -> Generator[str | StreamResult, None, None]:
        tools = [{"type": "web_search_preview"}] if web_search else []

        stream = self.client.responses.create(
            model=model,
            input=list(input_payload),
            tools=tools if tools else None,
            stream=True,
        )

        result = StreamResult()
        citations = []

        for event in stream:
            event_type = getattr(event, "type", None)

            if event_type == "response.output_text.delta":
                result.text += event.delta
                yield event.delta

            # Collect citations from web search
            elif event_type == "response.output_text.annotation.added":
                ann = getattr(event, "annotation", None)
                if ann and getattr(ann, "type", None) == "url_citation":
                    url = getattr(ann, "url", "")
                    title = getattr(ann, "title", url)
                    if url and url not in [c.split(" - ")[0] for c in citations]:
                        citations.append(f"{url} - {title}")

            # Capture usage stats at the end
            elif event_type == "response.completed":
                resp = getattr(event, "response", None)
                if resp:
                    usage = getattr(resp, "usage", None)
                    if usage:
                        result.input_tokens = getattr(usage, "input_tokens", 0)
                        result.output_tokens = getattr(usage, "output_tokens", 0)
                        result.total_tokens = getattr(usage, "total_tokens", 0)
                        result.cost_usd = self._calculate_cost(
                            model, result.input_tokens, result.output_tokens
                        )
                        self.session_tokens += result.total_tokens
                        self.session_cost += result.cost_usd

        result.citations = citations
        yield result
