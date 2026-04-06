"""Tool base class, result type, and registry."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    data: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Base class for all agent tools."""

    name: str
    description: str
    parameters: dict  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult: ...

    def openai_schema(self) -> dict:
        """Return Responses API tool schema (flat format)."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Discovers and manages available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tools_schema(self) -> list[dict]:
        """Return all tools as OpenAI function-calling schemas."""
        return [t.openai_schema() for t in self._tools.values()]

    def get_tools_description(self) -> str:
        """Human-readable summary of available tools for prompts."""
        lines = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)

    def auto_discover(self) -> None:
        """Import all modules in the tools package and register Tool subclasses."""
        import tools as pkg

        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            if module_name == "base" or module_name.startswith("_"):
                continue
            mod = importlib.import_module(f"tools.{module_name}")
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, Tool) and obj is not Tool:
                    try:
                        self.register(obj())
                    except Exception as e:
                        import sys
                        print(f"[planex] Warning: Tool {obj.__name__} failed to init: {e}", file=sys.stderr)
