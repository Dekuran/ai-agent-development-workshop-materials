import os
import json
from typing import List, Dict, Optional, Any
import google.generativeai as genai
from ..tools.registry import registry

def _model():
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    configured = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
    # Map legacy/default names to current supported IDs
    aliases = {
        "gemini-1.5-flash": "gemini-1.5-flash-002",
        "gemini-1.5-pro": "gemini-1.5-pro-002",
        "gemini-pro": "gemini-1.5-pro-002",
        "gemini-pro-1.5": "gemini-1.5-pro-002",
        "gemini-1.5-flash-latest": "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest": "gemini-1.5-pro-latest",
    }
    base = aliases.get(configured, configured)

    # Prefer a model from ListModels that supports generateContent and matches the requested family.
    try:
        models = list(genai.list_models())
        def supports_generate(m):
            try:
                methods = getattr(m, "supported_generation_methods", None) or getattr(m, "generation_methods", None)
                return methods and ("generateContent" in methods or "generate_content" in methods)
            except Exception:
                return False

        preferred = [m for m in models if supports_generate(m) and base in m.name]
        if not preferred and "flash" in base:
            preferred = [m for m in models if supports_generate(m) and "flash" in m.name]
        if not preferred and "pro" in base:
            preferred = [m for m in models if supports_generate(m) and "pro" in m.name]
        selected = preferred[0] if preferred else next((m for m in models if supports_generate(m)), None)
        if selected:
            return genai.GenerativeModel(selected.name)
    except Exception:
        # Fall through to static candidate list
        pass

    # Static fallbacks if ListModels is unavailable or empty
    candidates = [base, "gemini-1.5-flash-002", "gemini-1.5-flash-latest", "gemini-1.5-pro-002", "gemini-1.5-pro-latest"]
    last_err = None
    for m in candidates:
        try:
            return genai.GenerativeModel(m)
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("No valid Gemini model found. Set GOOGLE_MODEL to a supported model id (e.g., gemini-1.5-flash-002 or gemini-1.5-pro-002).")

def basic_agent(messages: List[Dict], model: Optional[str] = None) -> str:
    mdl = genai.GenerativeModel(model) if model else _model()
    prompt = "\\n".join([f"{m['role']}: {m['content']}" for m in messages])
    resp = mdl.generate_content(prompt)
    return resp.text

def custom_system_prompt_agent(messages: List[Dict], system_prompt: str, model: Optional[str] = None) -> str:
    mdl = genai.GenerativeModel(model) if model else _model()
    prompt = system_prompt + "\\n\\n" + "\\n".join([f"{m['role']}: {m['content']}" for m in messages])
    resp = mdl.generate_content(prompt)
    return resp.text

def single_tool_agent(messages: List[Dict], tool) -> str:
    query = ""
    for m in reversed(messages):
        if m["role"] == "user":
            query = m["content"]
            break
    results = tool.search(query) if query else []
    system_prompt = "You may use these search results as optional context:\\n" + "\\n".join(results)
    return custom_system_prompt_agent(messages, system_prompt)
