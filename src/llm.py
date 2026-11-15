"""The LLM gateway: the only module that talks to the `openai` SDK."""
import os
from functools import lru_cache
import math
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def validate_llm_config():
    """Required settings never silently fall back to a local development model."""
    for name in ("OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        if not os.environ.get(name, "").strip():
            raise RuntimeError(f"{name} must be set")
    try:
        timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS") or "90")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError
    except ValueError:
        raise RuntimeError("OPENAI_TIMEOUT_SECONDS must be a positive number") from None



class LLMGateway:
    """Call the model, get a Pydantic object back."""

    def __init__(self):
        validate_llm_config()
        self.model = os.environ["OPENAI_MODEL"]
        self._client = OpenAI(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["OPENAI_API_KEY"],
            max_retries=0,
            timeout=float(os.environ.get("OPENAI_TIMEOUT_SECONDS") or "90"),
        )

    def analyze(self, system: str, user: str, schema: type[T]) -> T:
        completion = self._client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=schema,
            store=False,
        )
        if completion.output_parsed is None:
            raise ValueError(
                f"LLM did not return a parsed {schema.__name__} (refused or malformed response)"
            )
        return completion.output_parsed


@lru_cache(maxsize=1)
def get_llm() -> LLMGateway:
    return LLMGateway()
