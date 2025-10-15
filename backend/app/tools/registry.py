from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import json

from .search_tool import SearchTool
from .file_reader import FileReader
from .sqlite_tool import SQLiteTool


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for arguments
    executor: Callable[[Dict[str, Any]], Any]


class ToolRegistry:
    """
    Provider-agnostic tool registry with:
      - Model-agnostic definitions (name, description, JSON-schema parameters)
      - Unified runtime executor dispatch
      - Provider adapters to convert tool specs to each provider's function/tool schema
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    # -------- Public API

    def list_names(self) -> List[str]:
        return sorted(self._tools.keys())

    def get(self, names: Optional[List[str]]) -> List[ToolSpec]:
        if not names:
            return []
        out: List[ToolSpec] = []
        for n in names:
            spec = self._tools.get(n)
            if spec:
                out.append(spec)
        return out

    def runtime_execute(self, name: str, args: Dict[str, Any]) -> str:
        """
        Execute a tool and return a stringified result suitable for tool_result/functionResponse payloads.
        """
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        spec = self._tools[name]
        try:
            result = spec.executor(args or {})
        except Exception as e:
            # Normalize errors into a readable string for the model
            return json.dumps({"ok": False, "error": str(e)})
        # Stringify consistently
        if isinstance(result, (dict, list)):
            return json.dumps(result)
        return str(result)

    # -------- Provider adapters

    def to_openai_tools(self, specs: List[ToolSpec]) -> List[Dict[str, Any]]:
        """
        OpenAI Chat Completions functions
        https://platform.openai.com/docs/guides/function-calling
        """
        tools = []
        for s in specs:
            tools.append({
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                }
            })
        return tools

    def to_anthropic_tools(self, specs: List[ToolSpec]) -> List[Dict[str, Any]]:
        """
        Anthropic Messages API tools
        https://docs.anthropic.com/en/docs/build-with-claude/tool-use
        """
        tools = []
        for s in specs:
            tools.append({
                "name": s.name,
                "description": s.description,
                "input_schema": s.parameters,
            })
        return tools

    def to_gemini_function_decls(self, specs: List[ToolSpec]) -> List[Dict[str, Any]]:
        """
        Google Gemini function_declarations (Tools)
        https://ai.google.dev/gemini-api/docs/function-calling
        Note: Agent should pass as tools={ "function_declarations": [...here...] }
        """
        fns = []
        for s in specs:
            fns.append({
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            })
        return fns

    # -------- Defaults

    def _register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def _register_defaults(self) -> None:
        # web_search
        self._register(ToolSpec(
            name="web_search",
            description="Search the web for up-to-date information using DuckDuckGo.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3,
                        "description": "Maximum number of results to return (1-10)"
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            executor=lambda args: "\n".join(
                SearchTool().search(
                    args.get("query", ""),
                    int(args.get("max_results", 3))
                )
            )
        ))

        # file_read
        self._register(ToolSpec(
            name="file_read",
            description="Read the contents of a file previously uploaded to the uploaded_files/ directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path/filename within uploaded_files/"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            executor=lambda args: FileReader().read(args.get("path", ""))
        ))

        # sqlite_query
        self._register(ToolSpec(
            name="sqlite_query",
            description="Execute a read-only SQL SELECT query against the workshop SQLite database.",
            parameters={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "A SELECT ... query"},
                },
                "required": ["sql"],
                "additionalProperties": False,
            },
            executor=lambda args: SQLiteTool().query(args.get("sql", "SELECT 1"))
        ))


# Convenience module-level singleton
registry = ToolRegistry()