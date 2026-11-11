"""The LLM gateway: the only module that talks to the `openai` SDK."""
import os
from functools import lru_cache
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMGateway:
    """Call the model, get a Pydantic object back."""

    def __init__(self):
        self.model = os.environ.get("OPENAI_MODEL", "google/gemma-4-e4b")
        self._client = OpenAI(
            base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1"),
            api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"),
        )

    def analyze(self, system: str, user: str, schema: type[T]) -> T:
        completion = self._client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=schema,
        )
        if completion.output_parsed is None:
            raise ValueError(
                f"LLM did not return a parsed {schema.__name__} (refused or malformed response)"
            )
        return completion.output_parsed


@lru_cache(maxsize=1)
def get_llm() -> LLMGateway:
    return LLMGateway()
