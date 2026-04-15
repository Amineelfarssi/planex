"""Bedrock Anthropic LLM provider — drop-in replacement for OpenAIProvider.

Uses the Anthropic Python SDK's AsyncAnthropicBedrock client, which handles
AWS Sig-v4 auth automatically from IAM role / env credentials.

Tiers (defaults — override via PLANEX_FAST_MODEL / PLANEX_SMART_MODEL / PLANEX_STRATEGIC_MODEL):
  - FAST:      Claude Haiku 4.5  (cheap, fast parsing/extraction — no 4.6 Haiku yet)
  - SMART:     Claude Sonnet 4.6 (tool dispatch, synthesis, chat)
  - STRATEGIC: Claude Opus 4.6   (planning, reasoning — with extended thinking)

Model IDs must be inference profile IDs (e.g. eu.anthropic.claude-sonnet-4-5-20250929-v1:0).
Embeddings use Amazon Titan via boto3 (Anthropic has no embedding model).

Usage:
  PLANEX_PROVIDER=bedrock  — set in .env or environment to activate this provider.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator

import aioboto3
from anthropic import AsyncAnthropicBedrock

from core.llm import LLMProvider, LLMResponse, ToolCall, TokenUsage, Tier

# ---------------------------------------------------------------------------
# Tier → Bedrock model ID mapping
# ---------------------------------------------------------------------------

_TIER_ENV = {
    "fast": "PLANEX_FAST_MODEL",
    "smart": "PLANEX_SMART_MODEL",
    "strategic": "PLANEX_STRATEGIC_MODEL",
}

# Region prefix for cross-region inference profiles.
# eu-* → "eu.", us-* → "us.", ap-* → "apac.", sa-* → "sa.", etc.
# Falls back to "us." if region is unset.
def _region_prefix() -> str:
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", ""))
    if region.startswith("eu-"):
        return "eu"
    if region.startswith("us-"):
        return "us"
    if region.startswith("ap-"):
        return "apac"
    if region.startswith("sa-"):
        return "sa"
    # Fallback: use global profiles (work in any region)
    return "global"

_TIER_DEFAULT_SUFFIX = {
    "fast": "anthropic.claude-haiku-4-5-20251001-v1:0",
    "smart": "anthropic.claude-sonnet-4-6",
    "strategic": "anthropic.claude-opus-4-6-v1",
}

def _tier_default(tier: str) -> str:
    prefix = _region_prefix()
    return f"{prefix}.{_TIER_DEFAULT_SUFFIX[tier]}"

# Strategic tier gets extended thinking
_TIER_THINKING_BUDGET = {
    "fast": 0,
    "smart": 0,
    "strategic": 5000,
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


class BedrockAnthropicProvider(LLMProvider):
    """LLMProvider backed by Anthropic models on AWS Bedrock."""

    def __init__(self) -> None:
        self._client = AsyncAnthropicBedrock(
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION")),
        )
        self._embed_model = os.getenv(
            "PLANEX_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"
        )
        self._embed_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
        self.total_usage: dict[str, TokenUsage] = {}

    def _model(self, tier: Tier) -> str:
        return os.getenv(_TIER_ENV.get(tier, ""), "") or _tier_default(tier)

    def _track(self, tier: Tier, usage: TokenUsage) -> None:
        if tier not in self.total_usage:
            self.total_usage[tier] = TokenUsage()
        self.total_usage[tier].prompt_tokens += usage.prompt_tokens
        self.total_usage[tier].completion_tokens += usage.completion_tokens

    def _extract_usage(self, resp) -> TokenUsage:
        if hasattr(resp, "usage") and resp.usage:
            return TokenUsage(
                prompt_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
                completion_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
            )
        return TokenUsage()

    # ------------------------------------------------------------------
    # Message format helpers — Anthropic native format
    # ------------------------------------------------------------------

    def format_tool_call(self, call_id: str, name: str, arguments: dict) -> dict:
        return {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": call_id, "name": name, "input": arguments}],
        }

    def format_tool_result(self, call_id: str, output: str) -> dict:
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": call_id, "content": output}],
        }

    # ------------------------------------------------------------------
    # Internal: convert incoming messages to Anthropic format
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """Split system prompt and merge consecutive same-role messages.

        Input messages use generic role-based format:
          {"role": "system"|"user"|"assistant", "content": ...}
        Plus provider-native tool messages from format_tool_call/format_tool_result.

        Returns (system_prompt, anthropic_messages).
        """
        system_parts: list[str] = []
        out: list[dict] = []

        for msg in messages:
            role = msg.get("role")

            if role == "system":
                system_parts.append(msg["content"])
                continue

            # Tool call/result messages already have the right Anthropic structure
            # (role + content list with tool_use / tool_result blocks)
            content = msg.get("content", "")

            if out and out[-1]["role"] == role:
                # Merge consecutive same-role messages
                prev = out[-1]["content"]
                if isinstance(prev, list) and isinstance(content, list):
                    out[-1]["content"] = prev + content
                elif isinstance(prev, str) and isinstance(content, str):
                    out[-1]["content"] = prev + "\n\n" + content
                elif isinstance(prev, list) and isinstance(content, str):
                    out[-1]["content"] = prev + [{"type": "text", "text": content}]
                elif isinstance(prev, str) and isinstance(content, list):
                    out[-1]["content"] = [{"type": "text", "text": prev}] + content
            else:
                out.append({"role": role, "content": content})

        return "\n\n".join(system_parts), out

    @staticmethod
    def _convert_tools(tools: list[dict] | None) -> list[dict]:
        """Convert tool schemas to Anthropic format.

        Input (generic/OpenAI):  {"type": "function", "name": ..., "description": ..., "parameters": {...}}
        Output (Anthropic):      {"name": ..., "description": ..., "input_schema": {...}}
        """
        if not tools:
            return []
        out = []
        for t in tools:
            if t.get("type") == "web_search":
                continue  # OpenAI-native, skip — Planex has ddg_search instead
            out.append({
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    # ------------------------------------------------------------------
    # chat()
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        tier: Tier = "smart",
        web_search: bool = True,
    ) -> LLMResponse:
        model = self._model(tier)
        system, anthropic_msgs = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": anthropic_msgs,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        thinking_budget = _TIER_THINKING_BUDGET.get(tier, 0)
        if thinking_budget > 0:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.messages.create(**kwargs)
                break
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))

        usage = self._extract_usage(resp)
        self._track(tier, usage)

        content = None
        tool_calls: list[ToolCall] = []

        for block in resp.content:
            if block.type == "text":
                content = (content or "") + block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    # ------------------------------------------------------------------
    # chat_parse() — structured output via tool_use workaround
    #
    # Bedrock doesn't support messages.parse() with output_format yet.
    # Instead, we define the Pydantic model as a tool and force the model
    # to call it, then parse the tool input as the structured output.
    # ------------------------------------------------------------------

    async def chat_parse(
        self,
        messages: list[dict],
        response_model: type,
        tier: Tier = "smart",
    ) -> Any:
        model = self._model(tier)
        system, anthropic_msgs = self._convert_messages(messages)

        # Build a tool from the Pydantic model's JSON schema
        schema = response_model.model_json_schema()
        # Inline $defs to produce a flat schema (small models handle this better)
        if "$defs" in schema:
            defs = schema.pop("$defs")
            schema_str = json.dumps(schema)
            for def_name, def_schema in defs.items():
                ref = f'{{"$ref": "#/$defs/{def_name}"}}'
                schema_str = schema_str.replace(ref, json.dumps(def_schema))
            schema = json.loads(schema_str)

        tool_name = f"return_{response_model.__name__}"
        tool_def = {
            "name": tool_name,
            "description": (
                f"Return the structured result. "
                f"You MUST provide ALL required fields: {list(schema.get('required', []))}"
            ),
            "input_schema": schema,
        }

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": anthropic_msgs,
            "tools": [tool_def],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        if system:
            kwargs["system"] = system

        # No extended thinking when forcing tool_choice (Anthropic doesn't allow it)

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.messages.create(**kwargs)
                break
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))

        usage = self._extract_usage(resp)
        self._track(tier, usage)

        # Extract the tool_use block and parse it into the Pydantic model
        for block in resp.content:
            if block.type == "tool_use" and block.name == tool_name:
                return response_model.model_validate(block.input)

        raise ValueError(f"No structured output for {response_model.__name__}")

    # ------------------------------------------------------------------
    # chat_stream()
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Tier = "smart",
        web_search: bool = True,
    ) -> AsyncIterator[str]:
        model = self._model(tier)
        system, anthropic_msgs = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": anthropic_msgs,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    # ------------------------------------------------------------------
    # embed() — Amazon Titan via boto3
    # ------------------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        session = aioboto3.Session()

        async with session.client(
            "bedrock-runtime",
            region_name=self._embed_region,
        ) as client:
            for text in texts:
                body = json.dumps({"inputText": text})
                resp = await client.invoke_model(
                    modelId=self._embed_model,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                resp_body = json.loads(await resp["body"].read())
                all_embeddings.append(resp_body["embedding"])

        return all_embeddings
