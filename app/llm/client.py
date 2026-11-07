"""Groq LLM client with retries, structured output, and cost tracking."""
from __future__ import annotations

import json
import time
from typing import Type, TypeVar

import structlog
from groq import Groq
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.monitoring import metrics as prom_metrics

logger = structlog.get_logger("llm.client")

T = TypeVar("T", bound=BaseModel)

# Approximate Groq pricing (USD per 1M tokens). Adjust as needed.
GROQ_PRICING = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},  # may be deprecated
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.75},
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "meta-llama/llama-4-maverick-17b-128e-instruct": {"input": 0.20, "output": 0.60},
}


class LLMError(Exception):
    """Raised when the LLM call fails after all retries."""


class LLMClient:
    """Thin wrapper around Groq with structured output + observability."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.max_retries = settings.llm_max_retries
        self.timeout = settings.llm_timeout_seconds
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete_structured(
        self,
        *,
        prompt: str,
        schema: Type[T],
        system_prompt: str | None = None,
        prompt_version: str = "v1",
    ) -> tuple[T, dict]:
        """
        Call LLM, parse JSON into `schema`, retry on failure.
        Returns (parsed_output, usage_info). Raises LLMError on persistent failure.
        """
        if not self.is_available:
            raise LLMError("GROQ_API_KEY not configured")

        client = Groq(api_key=self.api_key, timeout=self.timeout)
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            start = time.perf_counter()
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )
                elapsed = time.perf_counter() - start

                content = resp.choices[0].message.content
                if not content:
                    raise LLMError("empty response body")

                parsed_dict = json.loads(content)
                parsed = schema.model_validate(parsed_dict)

                usage = self._record_usage(resp, elapsed, prompt_version)
                logger.info("llm_complete", attempt=attempt, **usage)
                return parsed, usage

            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                logger.warning("llm_parse_failed", attempt=attempt, error=str(e)[:200])
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("llm_call_failed", attempt=attempt, error=str(e)[:200])
                prom_metrics.llm_errors_total.labels(
                    model=self.model, error_type=type(e).__name__
                ).inc()

            if attempt < self.max_retries:
                time.sleep(0.5 * (2 ** (attempt - 1)))

        raise LLMError(f"LLM failed after {self.max_retries} attempts: {last_error}")

    def _record_usage(self, resp, elapsed: float, prompt_version: str) -> dict:
        usage = resp.usage
        in_tokens = usage.prompt_tokens
        out_tokens = usage.completion_tokens
        total = usage.total_tokens

        pricing = GROQ_PRICING.get(self.model, {"input": 1.0, "output": 2.0})
        cost = (in_tokens * pricing["input"] + out_tokens * pricing["output"]) / 1_000_000

        prom_metrics.llm_tokens_total.labels(model=self.model, type="input").inc(in_tokens)
        prom_metrics.llm_tokens_total.labels(model=self.model, type="output").inc(out_tokens)
        prom_metrics.llm_cost_usd_total.labels(model=self.model).inc(cost)
        prom_metrics.llm_request_duration_seconds.labels(model=self.model).observe(elapsed)

        return {
            "model": self.model,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": total,
            "cost_usd": round(cost, 6),
            "latency_s": round(elapsed, 3),
            "prompt_version": prompt_version,
        }