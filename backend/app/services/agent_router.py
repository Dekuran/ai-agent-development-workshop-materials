from typing import List, Optional, Any
import json

from ..agents import openai_agent, anthropic_agent, google_gemini_agent, ollama_agent, google_gemini_agent
from ..agents import deepseek_agent, langchain_agent, langgraph_agent, smolagent_agent, langgraph_full_agent
from ..tools.search_tool import SearchTool
from ..tools.registry import ToolSpec, registry
from ..tools.file_reader import FileReader
from ..tools.sqlite_tool import SQLiteTool
from ..tools.file_finder import FileFinder


def _validate_messages(messages: List[dict]) -> List[dict]:
    # Ensure each message has a string 'content'
    return [
        {**m, "content": str(m.get("content", ""))}
        for m in messages
        if "content" in m and isinstance(m["content"], (str, int, float))
    ]


async def dispatch_agent(
    provider: str,
    variant: str,
    messages: List[dict],
    system_prompt: Optional[str] = None,
    tools: Optional[List[Any]] = None,
    model: Optional[str] = None,
    framework_provider: Optional[str] = None,
):
    """
    Dispatch to the selected provider/framework agent.

    Params:
    - tools: Optional[List[ToolSpec]] from tools.registry.get([...])
    - model: Optional[str] model override (provider-specific). Currently ignored by legacy agents.
    - framework_provider: Optional[str] for framework backends (e.g., langgraph "gemini"). Currently ignored by stubs.
    """

    # Map provider/framework to module
    modules = {
        "openai": openai_agent,
        "anthropic": anthropic_agent,
        "google": google_gemini_agent,
        "gemini": google_gemini_agent,
        "gemini_mlg": google_gemini_agent,
        "ollama": ollama_agent,
        "deepseek": deepseek_agent,
        "langchain": langchain_agent,
        "langgraph": langgraph_agent,
        "langgraph_full": langgraph_full_agent,
        "smolagent": smolagent_agent,
    }

    if provider not in modules:
        raise ValueError(f"Unknown provider/framework: {provider}")

    mod = modules[provider]
    messages = _validate_messages(messages)

    # NOTE: Until provider-native tool-calling is implemented in each agent,
    # we keep a backward-compatible shim for "tool" variant that only enables web_search.
    # New ToolRegistry-based execution will be wired in provider modules next.
    def _select_legacy_search_tool(selected: Optional[List[Any]]):
        # If web_search is selected, provide a real SearchTool; else return a no-op shim
        if not selected:
            return None
        for t in selected:
            if getattr(t, "name", None) == "web_search":
                return SearchTool()

        class _NoopSearchTool:
            def search(self, query: str, max_results: int = 3):
                return f"[tool disabled] web_search not selected query={query!r}"

        return _NoopSearchTool()

    if variant == "basic":
        fn = _maybe_async(mod.basic_agent)
        if _accepts_param(mod.basic_agent, "model"):
            return await fn(messages, model=model)
        return await fn(messages)

    elif variant == "custom":
        if not system_prompt:
            system_prompt = "You are a helpful assistant."
        fn = _maybe_async(mod.custom_system_prompt_agent)
        if _accepts_param(mod.custom_system_prompt_agent, "model"):
            return await fn(messages, system_prompt, model=model)
        return await fn(messages, system_prompt)

    # Native tool-calling for OpenAI/Anthropic/Gemini when tools are provided;
    # otherwise fallback to legacy tool_agent

    def tool_usage_instructions(tools: List[ToolSpec]) -> str:
        def example_args_from_schema(schema):
            try:
                props = (schema or {}).get("properties", {}) if isinstance(schema, dict) else {}
                required = set((schema or {}).get("required", [])) if isinstance(schema, dict) else set()
                keys = list(required) + [k for k in props.keys() if k not in required]
                ex = {}
                for k in keys:
                    spec = props.get(k, {})
                    t = spec.get("type", "string")
                    if "default" in spec:
                        ex[k] = spec["default"]
                    elif t == "integer":
                        ex[k] = 3 if k.lower() in ("max_results", "limit", "top_k") else 1
                    elif t == "number":
                        ex[k] = 1.0
                    elif t == "boolean":
                        ex[k] = True
                    else:
                        ex[k] = spec.get("description", "value")
                return json.dumps(ex, ensure_ascii=False)
            except Exception:
                return "{}"

        preface = (
            "Tool use policy:\n"
            "- You have access to external tools listed below.\n"
            "- Call a tool only when necessary (e.g., to fetch current info, read files, or query/modify the DB). If the question can be answered directly, do not call a tool.\n- Do not use web_search for greetings or general chit-chat; answer directly.\n"
            "- Always pass JSON arguments exactly matching the parameter schema. Do not invent fields.\n"
            "- Use file_finder to discover valid filenames before file_read.\n"
            "- Use sqlite_query only for SELECT/PRAGMA. Use sqlite_execute only with explicit user permission for writes.\n"
            "- After using a tool, summarize results before answering."
        )

        sections = [preface]
        for t in tools or []:
            params = t.parameters if isinstance(t.parameters, dict) else {}
            example_args = example_args_from_schema(params)
            sections.append(
                f"Tool: {t.name}\nDescription: {t.description}\nCall pattern: {t.name}({example_args})"
            )
        return "\n\n".join(sections)

    usage_block = tool_usage_instructions(tools) if tools else ""
    if system_prompt:
        system_prompt = usage_block + "\n\n" + system_prompt
    else:
        system_prompt = usage_block

    if provider in ("openai", "anthropic", "google", "gemini", "langgraph", "langgraph_mlg") and tools:
        return await _maybe_async(mod.tool_agent)(
            messages, system_prompt, tools, model
        )

    legacy_specs = registry.get(["web_search"])
    return await _maybe_async(mod.tool_agent)(
        messages, system_prompt, legacy_specs, model
    )

    # [Note: any additional branches should be inserted above this return]


def _maybe_async(fn):
    import inspect, asyncio
    if inspect.iscoroutinefunction(fn):
        return fn

    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    return wrapper


def _accepts_param(fn, name: str) -> bool:
    import inspect
    try:
        return name in inspect.signature(fn).parameters
    except Exception:
        return False
