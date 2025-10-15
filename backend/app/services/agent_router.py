from typing import List, Optional, Any

from ..agents import openai_agent, anthropic_agent, google_gemini_agent, ollama_agent
from ..agents import deepseek_agent, langchain_agent, langgraph_agent, smolagent_agent
from ..tools.search_tool import SearchTool


async def dispatch_agent(
    provider: str,
    variant: str,
    messages: List[dict],
    system_prompt: Optional[str],
    tools: Optional[List[Any]] = None,
    model: Optional[str] = None,
    framework_provider: Optional[str] = None,
):
    """
    Dispatch to the selected provider/framework agent.

    Params:
      - tools: Optional[List[ToolSpec]] from tools.registry.get([...)]
      - model: Optional[str] model override (provider-specific). Currently ignored by legacy agents.
      - framework_provider: Optional[str] for framework backends (e.g., langgraph: "gemini"). Currently ignored by stubs.
    """
    # Map provider/framework to module
    modules = {
        "openai": openai_agent,
        "anthropic": anthropic_agent,
        "google": google_gemini_agent,
        "gemini": google_gemini_agent,
        "ollama": ollama_agent,
        "deepseek": deepseek_agent,
        "langchain": langchain_agent,
        "langgraph": langgraph_agent,
        "smolagent": smolagent_agent,
    }
    if provider not in modules:
        raise ValueError(f"Unknown provider/framework: {provider}")

    mod = modules[provider]

    # NOTE: Until provider-native tool-calling is implemented in each agent,
    # we keep a backward-compatible shim for "tool" variant that only enables web_search.
    # New ToolRegistry-based execution will be wired in provider modules next.
    def _select_legacy_search_tool(selected: Optional[List[Any]]):
        # If web_search is selected, provide a real SearchTool; else return a no-op shim
        if selected:
            for t in selected:
                if getattr(t, "name", None) == "web_search":
                    return SearchTool()
        class _NoopSearchTool:
            def search(self, query: str, max_results: int = 3):
                return [f"[tool disabled] web_search not selected; query='{query}'"]
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
    elif variant == "tool":
        # Native tool-calling for OpenAI/Anthropic/Gemini when tools are provided; otherwise fallback to legacy single_tool_agent
        if provider in ("openai", "anthropic", "google", "gemini") and tools:
            return await _maybe_async(mod.tool_agent)(messages, system_prompt, tools, model)
        legacy_tool = _select_legacy_search_tool(tools)
        return await _maybe_async(mod.single_tool_agent)(messages, legacy_tool)
    else:
        raise ValueError(f"Unknown agent variant: {variant}")


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
