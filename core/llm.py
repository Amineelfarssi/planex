"""Three-tier LLM provider — fully on the Responses API.

Tiers:
  - FAST:      parsing, extraction, chunk summaries
  - SMART:     tool dispatch, synthesis, follow-up chat
  - STRATEGIC: planning, query decomposition (reasoning=high)

Uses:
  - client.responses.create()  for chat + tool calling
  - client.responses.parse()   for structured output (Pydantic)
  - client.responses.create(stream=True) for streaming
"""

from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

# Auto-instrument via Traceloop/OpenLLMetry (silent no-op if not configured)
try:
    from traceloop.sdk import Traceloop
    Traceloop.init(
        disable_batch=True,
        api_key=os.getenv("TRACELOOP_API_KEY", "no-op"),
        api_endpoint=os.getenv("TRACELOOP_API_ENDPOINT", ""),
        exporter=None if os.getenv("TRACELOOP_API_KEY") else "none",
    )
except Exception:
    pass


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
    ) -> Any: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# OpenAI Responses API implementation
# ---------------------------------------------------------------------------

_TIER_ENV = {
    "fast": "PLANEX_FAST_MODEL",
    "smart": "PLANEX_SMART_MODEL",
    "strategic": "PLANEX_STRATEGIC_MODEL",
}

_TIER_DEFAULT = {
    "fast": "gpt-5-nano-2025-08-07",
    "smart": "gpt-5-mini",
    "strategic": "gpt-5.1",
}

# gpt-5.1 defaults to reasoning_effort: none — must be explicit
_TIER_REASONING = {
    "fast": None,
    "smart": None,
    "strategic": "medium",
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


class OpenAIProvider(LLMProvider):

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._embed_model = os.getenv("PLANEX_EMBEDDING_MODEL", "text-embedding-3-small")
        self.total_usage: dict[str, TokenUsage] = {}

    def _model(self, tier: Tier) -> str:
        return os.getenv(_TIER_ENV.get(tier, ""), _TIER_DEFAULT.get(tier, "gpt-5-mini"))

    def _track(self, tier: Tier, usage: TokenUsage) -> None:
        if tier not in self.total_usage:
            self.total_usage[tier] = TokenUsage()
        self.total_usage[tier].prompt_tokens += usage.prompt_tokens
        self.total_usage[tier].completion_tokens += usage.completion_tokens

    def _extract_usage(self, resp) -> TokenUsage:
        if hasattr(resp, 'usage') and resp.usage:
            return TokenUsage(
                prompt_tokens=getattr(resp.usage, 'input_tokens', 0) or 0,
                completion_tokens=getattr(resp.usage, 'output_tokens', 0) or 0,
            )
        return TokenUsage()

    # ---- chat via Responses API ----------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        tier: Tier = "smart",
        web_search: bool = True,
    ) -> LLMResponse:
        """Call LLM via Responses API. Returns text and/or tool calls.

        web_search: inject OpenAI's native web_search tool so the model
        can search the internet server-side when it decides to. This is
        transparent — results appear as inline text with citation annotations.
        """
        model = self._model(tier)
        kwargs: dict[str, Any] = {"model": model, "input": messages}

        # Merge custom tools + native web_search
        all_tools = list(tools) if tools else []
        if web_search:
            all_tools.append({"type": "web_search"})
        if all_tools:
            kwargs["tools"] = all_tools

        if response_format:
            kwargs["text"] = {"format": response_format}

        reasoning = _TIER_REASONING.get(tier)
        if reasoning:
            kwargs["reasoning"] = {"effort": reasoning}

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.responses.create(**kwargs)
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        usage = self._extract_usage(resp)
        self._track(tier, usage)

        # Parse output items
        content = None
        tool_calls: list[ToolCall] = []

        for item in resp.output:
            if item.type == "message":
                # Text response (may include citation annotations from native web search)
                for block in item.content:
                    if hasattr(block, 'text'):
                        content = (content or "") + block.text
            elif item.type == "function_call":
                # Custom tool call (our tools like ddg_search, read_url, etc.)
                try:
                    args = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ToolCall(
                    id=item.call_id or item.id,
                    name=item.name,
                    arguments=args,
                ))
            elif item.type == "web_search_call":
                # Native web search — results are folded into the text message
                # with citation annotations. Nothing to dispatch — just let
                # the text content (with citations) flow through.
                pass

        # Fallback: try output_text for simple responses
        if content is None and hasattr(resp, 'output_text') and resp.output_text:
            content = resp.output_text

        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    # ---- structured output via responses.parse() -----------------------------

    async def chat_parse(
        self,
        messages: list[dict],
        response_model: type,
        tier: Tier = "smart",
    ) -> Any:
        """Parse response into a Pydantic model via responses.parse() (GA).

        Uses text_format for structured output.
        Handles refusals explicitly.
        """
        model = self._model(tier)
        kwargs: dict[str, Any] = {"model": model, "input": messages, "text_format": response_model}

        reasoning = _TIER_REASONING.get(tier)
        if reasoning:
            kwargs["reasoning"] = {"effort": reasoning}

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.responses.parse(**kwargs)
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        usage = self._extract_usage(resp)
        self._track(tier, usage)

        # Check refusal
        if hasattr(resp, 'refusal') and resp.refusal:
            raise ValueError(f"Model refused: {resp.refusal}")

        if hasattr(resp, 'output_parsed') and resp.output_parsed:
            return resp.output_parsed

        raise ValueError(f"No parsed output for {response_model.__name__}")

    # ---- streaming via Responses API -----------------------------------------

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Tier = "smart",
        web_search: bool = True,
    ) -> AsyncIterator[str]:
        """Stream text tokens via Responses API."""
        model = self._model(tier)
        kwargs: dict[str, Any] = {"model": model, "input": messages, "stream": True}

        all_tools = list(tools) if tools else []
        if web_search:
            all_tools.append({"type": "web_search"})
        if all_tools:
            kwargs["tools"] = all_tools

        stream = await self._client.responses.create(**kwargs)
        async for event in stream:
            # Responses API streams different event types
            if hasattr(event, 'type'):
                if event.type == "response.output_text.delta":
                    yield event.delta
                elif event.type == "response.content_part.delta":
                    if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                        yield event.delta.text

    # ---- embeddings ----------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = 512
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._client.embeddings.create(model=self._embed_model, input=batch)
            all_embeddings.extend([d.embedding for d in resp.data])
        return all_embeddings
