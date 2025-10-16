from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import json

from .search_tool import SearchTool
from .file_reader import FileReader
from .sqlite_tool import SQLiteTool
from .file_finder import FileFinder


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
            description=("Use this tool to search the public web (DuckDuckGo) for fresh, up-to-date information. "
                         "When to use: when the user asks for current events, facts you are unsure about, or external links. "
                         "How to call: web_search({\"query\": \"concise search terms\", \"max_results\": 3}). "
                         "Arguments: query (required): short keywords; you may add operators like site:example.com. "
                         "max_results (optional int 1–10, default 3). "
                         "Return: a list of strings in the form 'Title — URL — Snippet'."),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Required. Concise search query (you may include operators like site:example.com)."},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3,
                        "description": "Optional. Number of results to return (1–10). Default is 3."
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            executor=lambda args: SearchTool().search(
                args.get("query", ""),
                int(args.get("max_results", 3))
            )
        ))

        # file_read
        self._register(ToolSpec(
            name="file_read",
            description=("Read the contents of a user-uploaded file from uploaded_files/. "
                         "Recommended flow: 1) Call file_finder({}) to list valid filenames; "
                         "2) Choose one filename; 3) Call file_read({\"path\": \"<filename>\"}). "
                         "Arguments: path (required): the exact filename as listed by file_finder (no directories). "
                         "Return: the text content of the file; large/binary documents may be extracted to text."),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Required. Exact filename within uploaded_files/, e.g. 'report.pdf' (no directories)."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            executor=lambda args: FileReader().read(args.get("path", ""))
        ))

        # sqlite_query
        self._register(ToolSpec(
            name="sqlite_query",
            description=("Execute a read-only SQL SELECT (or PRAGMA) query against the workshop SQLite database. "
                         "Do not modify data with this tool. "
                         "How to call: sqlite_query({\"sql\": \"SELECT ...\"}). "
                         "Return: the query results serialized to text/JSON."),
            parameters={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "Required. Single-statement SQL starting with SELECT or PRAGMA."},
                },
                "required": ["sql"],
                "additionalProperties": False,
            },
            executor=lambda args: SQLiteTool().query(args.get("sql", "SELECT 1"))
        ))

        # file_finder
        self._register(ToolSpec(
            name="file_finder",
            description=("List the available filenames in uploaded_files/. "
                         "Use this before file_read to discover valid filenames. "
                         "How to call: file_finder({}). "
                         "Return: a list of filenames (strings)."),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            executor=lambda args: FileFinder().search()
        ))

        # sqlite_execute
        self._register(ToolSpec(
            name="sqlite_execute",
            description=("Execute a write operation (INSERT/UPDATE/DELETE/etc.) against the SQLite database. "
                         "Only call this with explicit user permission and after validating the SQL. "
                         "How to call: sqlite_execute({\"sql\": \"UPDATE ...\"}). "
                         "Return: affected row count or last inserted row id."),
            parameters={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "Required. Single-statement non-SELECT SQL (e.g., INSERT, UPDATE, DELETE)."},
                },
                "required": ["sql"],
                "additionalProperties": False,
            },
            # Note: SQLiteTool currently exposes exeucte(); we call that for compatibility.
            executor=lambda args: SQLiteTool().exeucte(args.get("sql", ""))
        ))


# Convenience module-level singleton
registry = ToolRegistry()