"""Test tool contracts — registry, schemas, availability."""

import pytest
from tools.base import Tool, ToolResult, ToolRegistry


class TestToolRegistry:
    def test_auto_discover_finds_tools(self):
        registry = ToolRegistry()
        registry.auto_discover()
        tools = registry.list_tools()
        names = {t.name for t in tools}

        # All expected tools should be registered
        expected = {"read_file", "write_file", "read_url", "knowledge_search",
                    "ingest_documents", "get_current_time", "local_search"}
        for name in expected:
            assert name in names, f"Tool '{name}' not found in registry"

    def test_web_search_registered(self):
        """web_search uses OpenAI Responses API — should register if API key is set."""
        registry = ToolRegistry()
        registry.auto_discover()
        tool = registry.get("web_search")
        assert tool is not None
        assert tool.name == "web_search"

    def test_get_tools_schema_valid_openai_format(self):
        registry = ToolRegistry()
        registry.auto_discover()
        schemas = registry.get_tools_schema()

        assert len(schemas) > 0
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_get_nonexistent_tool(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent_tool_xyz") is None

    def test_register_and_retrieve(self):
        registry = ToolRegistry()
        from tools.time_tool import GetCurrentTimeTool
        tool = GetCurrentTimeTool()
        registry.register(tool)
        assert registry.get("get_current_time") is tool


class TestToolResult:
    def test_success_result(self):
        result = ToolResult(success=True, data="found 5 results", metadata={"count": 5})
        assert result.success
        assert "5 results" in result.data

    def test_failure_result(self):
        result = ToolResult(success=False, data="No results found", metadata={})
        assert not result.success

    def test_metadata_default(self):
        result = ToolResult(success=True, data="ok")
        assert result.metadata == {}


class TestTimeTool:
    @pytest.mark.asyncio
    async def test_returns_current_time(self):
        from tools.time_tool import GetCurrentTimeTool
        tool = GetCurrentTimeTool()
        result = await tool.execute()
        assert result.success
        assert "Current date" in result.data
        assert "Current time" in result.data
        assert "iso" in result.metadata


class TestLocalSearch:
    @pytest.mark.asyncio
    async def test_search_no_matches(self):
        from tools.local_search import LocalSearchTool
        tool = LocalSearchTool()
        result = await tool.execute(pattern="xyznonexistent123", path="/tmp")
        assert not result.success
        assert "No matches" in result.data

    @pytest.mark.asyncio
    async def test_search_finds_matches(self, tmp_path):
        # Create a file with searchable content
        test_file = tmp_path / "test.txt"
        test_file.write_text("GEPA is an optimization framework\nIt uses evolutionary algorithms")

        from tools.local_search import LocalSearchTool
        tool = LocalSearchTool()
        result = await tool.execute(pattern="GEPA", path=str(tmp_path))
        assert result.success
        assert "GEPA" in result.data
