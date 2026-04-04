"""Three-tier LLM provider abstraction.

Tiers:
  - FAST:      parsing, extraction, chunk summaries (default: gpt-4o-mini)
  - SMART:     tool dispatch, synthesis, report generation (default: gpt-4o)
  - STRATEGIC: planning, query decomposition, re-ranking (default: gpt-4o)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from openai import AsyncOpenAI


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

Tier = str  # "fast" | "smart" | "strategic"


class LLMProvider(ABC):

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        tier: Tier = "smart",
    ) -> LLMResponse: ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Tier = "smart",
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    async def chat_parse(
        self,
        messages: list[dict],
        response_model: type,
        tier: Tier = "smart",
    ) -> Any:
        """Parse response into a Pydantic model using structured output."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------

_TIER_ENV = {
    "fast": "PLANEX_FAST_MODEL",
    "smart": "PLANEX_SMART_MODEL",
    "strategic": "PLANEX_STRATEGIC_MODEL",
}

_TIER_DEFAULT = {
    "fast": "gpt-5-nano-2025-08-07",  # cheapest, good for parsing/summaries
    "smart": "gpt-5-mini",            # balanced quality for tool dispatch + synthesis
    "strategic": "gpt-5.1",           # best available for planning + decomposition
}

# Reasoning effort per tier (gpt-5.1 defaults to "none" so we MUST set it)
_TIER_REASONING = {
    "fast": None,        # gpt-5-nano: let model decide (defaults to medium)
    "smart": None,       # gpt-5-mini: let model decide (defaults to medium)
    "strategic": "high", # gpt-5.1: defaults to NONE — must explicitly enable
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


class OpenAIProvider(LLMProvider):

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._embed_model = os.getenv("PLANEX_EMBEDDING_MODEL", "text-embedding-3-small")
        self.total_usage: dict[str, TokenUsage] = {}

    def _model(self, tier: Tier) -> str:
        return os.getenv(_TIER_ENV.get(tier, ""), _TIER_DEFAULT.get(tier, "gpt-4o"))

    def _track(self, tier: Tier, usage: TokenUsage) -> None:
        if tier not in self.total_usage:
            self.total_usage[tier] = TokenUsage()
        self.total_usage[tier].prompt_tokens += usage.prompt_tokens
        self.total_usage[tier].completion_tokens += usage.completion_tokens

    # ---- chat (with retry) ------------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        tier: Tier = "smart",
    ) -> LLMResponse:
        model = self._model(tier)
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format

        # Set reasoning effort for models that need it (gpt-5.1 defaults to "none")
        reasoning = _TIER_REASONING.get(tier)
        if reasoning:
            kwargs["reasoning_effort"] = reasoning

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        msg = resp.choices[0].message
        usage = TokenUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )
        self._track(tier, usage)

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return LLMResponse(content=msg.content, tool_calls=tool_calls, usage=usage)

    # ---- structured output (parse into Pydantic model) --------------------

    async def chat_parse(
        self,
        messages: list[dict],
        response_model: type,
        tier: Tier = "smart",
    ) -> Any:
        """Parse response into a Pydantic model using OpenAI structured output."""
        model = self._model(tier)
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "response_format": response_model}

        reasoning = _TIER_REASONING.get(tier)
        if reasoning:
            kwargs["reasoning_effort"] = reasoning

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.beta.chat.completions.parse(**kwargs)
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        msg = resp.choices[0].message
        usage = TokenUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )
        self._track(tier, usage)

        if msg.parsed:
            return msg.parsed
        # Fallback: try manual parse
        if msg.content:
            import json as _json
            return response_model.model_validate_json(msg.content)
        raise ValueError(f"Failed to parse response into {response_model.__name__}")

    # ---- streaming chat ---------------------------------------------------

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Tier = "smart",
    ) -> AsyncIterator[str]:
        model = self._model(tier)
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    # ---- embeddings -------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # OpenAI supports up to 2048 texts per call; batch in groups of 512
        all_embeddings: list[list[float]] = []
        batch_size = 512
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._client.embeddings.create(model=self._embed_model, input=batch)
            all_embeddings.extend([d.embedding for d in resp.data])
        return all_embeddings
