# Native Google Gemini agent with tool-calling
# Replaces prior ChatVertexAI/MLG-based implementation.
# Public API (kept compatible with your router):
#   - basic_agent(messages: List[Dict], model: Optional[str] = None) -> str
#   - custom_system_prompt_agent(messages: List[Dict], system_prompt: str, model: Optional[str] = None) -> str
#   - tool_agent(messages: List[Dict], system_prompt: Optional[str] = None,
#                tools: Optional[List[Dict]] = None, model: Optional[str] = None) -> str
#
# Notes:
# - Messages are expected as [{"role": "user"|"assistant"|"system", "content": str}, ...]
# - Tools: use your ToolSpec objects from tools.registry (name, description, parameters)
# - Tool execution delegates to registry.runtime_execute(name, mapped_args)

import os
import json
import logging
from typing import List, Dict, Optional, Any, Iterable

import google.generativeai as genai
from ..tools.registry import registry, ToolSpec  # ToolSpec is only used for type hints


# -----------------------------
# Model configuration & selection
# -----------------------------

def _configure():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")
    genai.configure(api_key=api_key)


def _model(model_id: Optional[str] = None) -> "genai.GenerativeModel":
    """
    Build a GenerativeModel with a resilient model-id selection strategy.
    """
    _configure()
    configured = model_id or os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")

    # Map legacy/common names to current IDs
    aliases = {
        "gemini-1.5-flash": "gemini-1.5-flash-002",
        "gemini-1.5-pro": "gemini-1.5-pro-002",
        "gemini-pro": "gemini-1.5-pro-002",
        "gemini-pro-1.5": "gemini-1.5-pro-002",
        "gemini-1.5-flash-latest": "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest": "gemini-1.5-pro-latest",
    }
    base = aliases.get(configured, configured)

    # Try to pick a model that supports generateContent and matches the family
    try:
        def supports_generate(m):
            methods = getattr(m, "supported_generation_methods", None) or getattr(m, "generation_methods", None)
            return methods and ("generateContent" in methods or "generate_content" in methods)

        models = list(genai.list_models())
        preferred = [m for m in models if supports_generate(m) and base in m.name]
        if not preferred and "flash" in base:
            preferred = [m for m in models if supports_generate(m) and "flash" in m.name]
        if not preferred and "pro" in base:
            preferred = [m for m in models if supports_generate(m) and "pro" in m.name]
        selected = preferred[0] if preferred else next((m for m in models if supports_generate(m)), None)
        if selected:
            return genai.GenerativeModel(selected.name)
    except Exception:
        pass  # fall through to static candidates

    # Static fallbacks
    for candidate in [base, "gemini-1.5-flash-002", "gemini-1.5-flash-latest", "gemini-1.5-pro-002", "gemini-1.5-pro-latest"]:
        try:
            return genai.GenerativeModel(candidate)
        except Exception:
            continue
    raise RuntimeError("No valid Gemini model found. Set GOOGLE_MODEL to a supported model id (e.g., gemini-1.5-flash-002).")


# -----------------------------
# Message helpers
# -----------------------------

_ALLOWED_ROLES = {"user": "user", "assistant": "model", "system": "user"}  # Gemini has 'user' and 'model'

def _normalize_messages(messages: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role", "")).lower().strip()
        content = m.get("content", "")
        if content is None:
            continue
        # Map roles to Gemini-friendly roles (system becomes user instruction)
        g_role = _ALLOWED_ROLES.get(role, "user")
        out.append({"role": g_role, "parts": [str(content)]})
    return out


def _concat_text(messages: List[Dict]) -> str:
    return "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages])


# -----------------------------
# Tool conversion (ToolSpec -> Gemini tool)
# -----------------------------

def _sanitize_jsonschema_for_gemini(schema: Any) -> Any:
    """
    Sanitize JSON Schema for Gemini function_declarations.
    Gemini supports a subset. We conservatively:
      - Strip validation/extension keywords (minimum/maximum/default/etc.) at all levels
      - Preserve and recursively sanitize 'properties' entries by property name
      - Keep only structural keys: type, properties, required, description, enum, items
    """
    try:
        from copy import deepcopy
        s = deepcopy(schema)
    except Exception:
        s = schema

    allowed = {"type", "properties", "required", "description", "enum", "items"}

    if isinstance(s, dict):
        # Work on a shallow copy
        s = dict(s)

        # Drop unsupported/commonly rejected keys at this level
        for k in [
            "additionalProperties", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
            "minLength", "maxLength", "pattern", "default", "format", "examples", "example",
            "title", "deprecated", "nullable", "readOnly", "writeOnly", "minItems", "maxItems",
            "const", "oneOf", "anyOf", "allOf", "$schema", "$id"
        ]:
            s.pop(k, None)

        # Coerce integer -> number for Gemini compatibility
        if isinstance(s.get("type"), str) and s.get("type") == "integer":
            s["type"] = "number"

        # Special-case: recursively sanitize each property schema while preserving property names
        if isinstance(s.get("properties"), dict):
            new_props: Dict[str, Any] = {}
            for prop_name, prop_schema in s["properties"].items():
                new_props[prop_name] = _sanitize_jsonschema_for_gemini(prop_schema)
            s["properties"] = new_props

        # Recurse into 'items' if present
        if "items" in s:
            s["items"] = _sanitize_jsonschema_for_gemini(s["items"])

        # Keep only allowed structural keys at this level
        out: Dict[str, Any] = {k: v for k, v in s.items() if k in allowed}

        # Normalize shapes
        if "properties" in out and not isinstance(out["properties"], dict):
            out["properties"] = {}
        if "required" in out and not isinstance(out["required"], list):
            out["required"] = []
        return out

    if isinstance(s, list):
        return [_sanitize_jsonschema_for_gemini(v) for v in s]
    return s


def _to_gemini_tools(tools: Optional[List[ToolSpec]]) -> Optional[List[Dict[str, Any]]]:
    """
    Convert our ToolSpec entries into the Gemini "tools=[{function_declarations:[...]}]" format.
    Strips unsupported JSON Schema fields (e.g., additionalProperties) for Gemini.
    """
    if not tools:
        return None
    fns = []
    for t in tools:
        base_params = t.parameters or {"type": "object", "properties": {}}
        params = _sanitize_jsonschema_for_gemini(base_params)
        fns.append({
            "name": t.name,
            "description": t.description or "",
            "parameters": params,
        })
    return [{"function_declarations": fns}] if fns else None


def _extract_function_calls(resp: Any) -> List[Dict[str, Any]]:
    """
    Extract function calls from a Gemini response in a robust way.
    Returns a list of {"name": str, "args": dict}.
    """
    calls: List[Dict[str, Any]] = []
    try:
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for p in parts or []:
                # Python client surfaces function calls as dict-like via .function_call or part.get("functionCall")
                fc = getattr(p, "function_call", None) or getattr(p, "functionCall", None) or None
                if not fc and isinstance(p, dict):
                    fc = p.get("functionCall") or p.get("function_call")
                if fc:
                    name = getattr(fc, "name", None) or (isinstance(fc, dict) and fc.get("name"))
                    args = getattr(fc, "args", None) or (isinstance(fc, dict) and fc.get("args")) or {}
                    # args may arrive as a JSON string in some cases
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            pass
                    calls.append({"name": name, "args": args or {}})
    except Exception:
        pass
    return calls


def _safe_text_from_response(resp: Any) -> Optional[str]:
    """
    Safely extract plain text from a Gemini response without coercing function_call parts.
    """
    # Try the SDK's text property first
    try:
        t = getattr(resp, "text", None)
        if isinstance(t, str) and t.strip():
            return t
    except Exception:
        pass
    # Manual extraction from candidates/parts
    try:
        chunks: List[str] = []
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for p in parts or []:
                try:
                    txt = getattr(p, "text", None) if hasattr(p, "text") else None
                    if isinstance(txt, str) and txt.strip():
                        chunks.append(txt)
                        continue
                    if isinstance(p, str) and p.strip():
                        chunks.append(p)
                        continue
                    if isinstance(p, dict):
                        t2 = p.get("text")
                        if isinstance(t2, str) and t2.strip():
                            chunks.append(t2)
                except Exception:
                    continue
        return "\n".join(chunks) if chunks else None
    except Exception:
        return None


def _should_enable_tools(messages: List[Dict], system_prompt: Optional[str], tools: Optional[List[ToolSpec]]) -> bool:
    """
    Gating for tool exposure.
    Be permissive to avoid disabling tools mid-workflow (e.g., when the user replies "ok").
    Disable only for obvious small-talk; otherwise expose tools and let AUTO decide to call.
    """
    if not tools:
        return False

    # Collect up to the last 5 user utterances
    user_msgs: List[str] = []
    for m in reversed(messages or []):
        try:
            if str(m.get("role", "")).lower() == "user":
                user_msgs.append(str(m.get("content", "")).strip().lower())
                if len(user_msgs) >= 5:
                    break
        except Exception:
            continue

    joined = " ".join([u for u in user_msgs if u]).strip()

    # If no clear signal, keep tools available and let model AUTO choose
    if not joined:
        return True

    # Keywords that indicate tool utility (web, files, db/sqlite, etc.)
    keywords = [
        "search", "find", "latest", "news", "current", "today", "web", "google", "duckduckgo",
        "http://", "https://", "url", "link",
        "file", "read file", "uploaded", "upload",
        "sqlite", "database", "db", "sql", "select", "insert", "update", "delete", "pragma",
        "table", "schema"
    ]
    if any(k in joined for k in keywords):
        return True

    # Small-talk/greetings should not expose tools, to reduce spurious calls
    smalltalk_exact = {"hi", "hello", "hey", "how are you", "what's up", "what up", "help", "how to help you",
                       "ok", "okay", "kk", "k", "thanks", "thank you", "cool"}
    last_user = user_msgs[0] if user_msgs else ""
    if last_user in smalltalk_exact:
        return False

    # Default: expose tools; model in AUTO mode decides whether to use them
    return True


def _tool_response_part(name: str, result: Any) -> Dict[str, Any]:
    """
    Build a Gemini-compatible ToolResponse part. The Python SDK accepts plain dicts.
    Ensure the function_response.response is a JSON object:
      - dict: pass through
      - list: wrap as {"results": [...]}
      - other: wrap as {"text": "..."}
    """
    # Gemini expects a 'tool' role message that includes a function_response part:
    # {"role": "tool", "parts": [{"function_response": {"name": name, "response": {...}}}]}
    if isinstance(result, dict):
        payload = result
    elif isinstance(result, list):
        payload = {"results": result}
    else:
        payload = {"text": str(result)}
    return {
        "role": "tool",
        "parts": [
            {
                "function_response": {
                    "name": name,
                    "response": payload,
                }
            }
        ],
    }


# -----------------------------
# Core agents
# -----------------------------

def basic_agent(messages: List[Dict], model: Optional[str] = None) -> str:
    """
    Returns a plain text answer with no system prompt and no tools.
    """
    mdl = _model(model)
    # For basic use, the simple string concatenation is fine
    prompt = _concat_text(messages)
    resp = mdl.generate_content(prompt)
    return _safe_text_from_response(resp) or str(resp)


def custom_system_prompt_agent(messages: List[Dict], system_prompt: str, model: Optional[str] = None) -> str:
    """
    Adds a system prompt (as system_instruction) and answers with no tools.
    """
    mdl = _model(model)
    # Prefer system_instruction for clean separation
    mdl = genai.GenerativeModel(mdl.model_name, system_instruction=str(system_prompt))
    resp = mdl.generate_content(_normalize_messages(messages))
    return _safe_text_from_response(resp) or str(resp)


def tool_agent(
    messages: List[Dict],
    system_prompt: Optional[str] = None,
    tools: Optional[List[ToolSpec]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Tool-enabled agent using Gemini's native function/tool calling.

    Flow:
      1) Build tool declarations from ToolSpec
      2) Send conversation (with optional system prompt)
      3) If Gemini returns function calls, execute them via registry.runtime_execute
      4) Send tool results back as a tool message; ask the model again
      5) Return the final text (fallback to last tool result if model returns empty)
    """
    mdl = _model(model)

    # Prepare tool declarations with gating to avoid unnecessary tool calls
    enable_tools = _should_enable_tools(messages, system_prompt, tools)
    tool_decls = _to_gemini_tools(tools) if enable_tools else None
    try:
        print("[gemini.tool_agent] enable_tools:", enable_tools)
        print("[gemini.tool_agent] tool_decls:", json.dumps(tool_decls, ensure_ascii=False))
    except Exception:
        print("[gemini.tool_agent] tool_decls: <non-serializable>")

    model_kwargs: Dict[str, Any] = {"tools": tool_decls} if tool_decls else {}
    # Allow function calling; let AUTO decide to call or not
    if tool_decls:
        model_kwargs["tool_config"] = {
            "function_calling_config": {
                "mode": "AUTO"
            }
        }
    if system_prompt:
        model_kwargs["system_instruction"] = str(system_prompt)
    try:
        # Avoid dumping the possibly large tools payload again here
        printable_kwargs = {k: v for k, v in model_kwargs.items() if k != "tools"}
        print("[gemini.tool_agent] model_kwargs:", json.dumps(printable_kwargs, ensure_ascii=False))
    except Exception:
        print("[gemini.tool_agent] model_kwargs: <non-serializable>")

    # Try to instantiate model; on schema error, rebuild with loosened schema; last resort: no tools
    try:
        mdl = genai.GenerativeModel(mdl.model_name, **model_kwargs)
    except Exception as e:
        print("[gemini.tool_agent] model init failed; retrying with loosened schemas. error:", str(e))
        try:
            if tools:
                loose_fns = []
                for t in tools or []:
                    # Build minimal string-typed schema per property, dropping 'required'
                    props = (t.parameters or {}).get("properties", {}) if isinstance(t.parameters, dict) else {}
                    loose_params = {"type": "object", "properties": {}}
                    for pname, pspec in props.items():
                        loose_params["properties"][pname] = {
                            "type": "string",
                            "description": str(pspec.get("description", "")) if isinstance(pspec, dict) else ""
                        }
                    loose_fns.append({
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": loose_params,
                    })
                loose_tool_decls = [{"function_declarations": loose_fns}] if loose_fns else None
                model_kwargs["tools"] = loose_tool_decls
                # tool_config can remain; allowed_function_names unchanged
                try:
                    printable_kwargs = {k: v for k, v in model_kwargs.items() if k != "tools"}
                    print("[gemini.tool_agent] retry model_kwargs (loose):", json.dumps(printable_kwargs, ensure_ascii=False))
                    print("[gemini.tool_agent] retry tool_decls (loose):", json.dumps(loose_tool_decls, ensure_ascii=False))
                except Exception:
                    print("[gemini.tool_agent] retry payloads (loose): <non-serializable>")
            mdl = genai.GenerativeModel(mdl.model_name, **model_kwargs)
        except Exception as e2:
            print("[gemini.tool_agent] loose schema also failed; falling back to no-tools. error:", str(e2))
            model_kwargs.pop("tools", None)
            model_kwargs.pop("tool_config", None)
            mdl = genai.GenerativeModel(mdl.model_name, **model_kwargs)

    try:
        logging.debug(f"[gemini.tool_agent] tools_enabled={bool(tool_decls)} tool_config={model_kwargs.get('tool_config')}")
    except Exception:
        pass

    # First turn
    lc_messages = _normalize_messages(messages)
    try:
        print("[gemini.tool_agent] request_messages:", json.dumps(lc_messages, ensure_ascii=False))
    except Exception:
        print("[gemini.tool_agent] request_messages: <non-serializable>")
    resp = mdl.generate_content(lc_messages)

    # Collect and execute function calls (if any)
    calls = _extract_function_calls(resp)
    try:
        logging.debug(f"[gemini.tool_agent] first_turn_function_calls={calls!r}")
    except Exception:
        pass
    try:
        print("[gemini.tool_agent] first_turn_calls:", json.dumps(calls, ensure_ascii=False))
    except Exception:
        print("[gemini.tool_agent] first_turn_calls:", calls)

    model_fc_msgs: List[Dict[str, Any]] = []

    tool_msgs: List[Dict[str, Any]] = []

    if calls:
        for call in calls:
            fname = (call.get("name") or "").strip()
            raw_args = call.get("args") or {}
            # Map arguments to the spec's parameter names if present; otherwise pass through
            spec = next((t for t in (tools or []) if t.name == fname), None)
            mapped_args = {}

            if spec and isinstance(spec.parameters, dict):
                # JSONSchema: {"type":"object", "properties": {...}}
                props = (spec.parameters or {}).get("properties", {})
                # Keep only known params (fallback: pass all)
                if props:
                    for k in props.keys():
                        if k in raw_args:
                            mapped_args[k] = raw_args[k]
                    # If nothing matched but exactly one arg was provided, keep it
                    if not mapped_args and len(raw_args) == 1:
                        mapped_args = {next(iter(raw_args.keys())): next(iter(raw_args.values()))}
                else:
                    mapped_args = dict(raw_args)
            else:
                mapped_args = dict(raw_args)

            # Execute the tool via the registry
            try:
                try:
                    print("[gemini.tool_agent] exec_tool:", fname, "args:", json.dumps(mapped_args, ensure_ascii=False))
                except Exception:
                    print("[gemini.tool_agent] exec_tool:", fname, "args:", mapped_args)
                result_str = registry.runtime_execute(fname, mapped_args)
            except Exception as e:
                result_str = f"[tool runtime error] {type(e).__name__}: {e}"

            # Gemini prefers JSON-like objects; try to load JSON if that's what the tool returned
            try:
                result_payload = json.loads(result_str)
            except Exception:
                result_payload = {"text": str(result_str)}

            tool_msgs.append(_tool_response_part(fname, result_payload))

        # Second turn: feed tool results back to the model
        try:
            print("[gemini.tool_agent] tool_messages:", json.dumps(tool_msgs, ensure_ascii=False))
        except Exception:
            print("[gemini.tool_agent] tool_messages: <non-serializable>")
        final = mdl.generate_content(lc_messages + tool_msgs)
        final_text = _safe_text_from_response(final)
        try:
            print("[gemini.tool_agent] final_text:", (final_text or "").strip())
        except Exception:
            print("[gemini.tool_agent] final_text: <unprintable>")
        if final_text and final_text.strip():
            return final_text.strip()
        try:
            logging.debug("[gemini.tool_agent] second_turn_empty_text; returning last tool payload fallback")
        except Exception:
            pass

        # Fallback to last tool result if model answer is blank
        if tool_msgs:
            last_payload = tool_msgs[-1]["parts"][0]["function_response"]["response"]
            return json.dumps(last_payload, ensure_ascii=False)

    # No tool calls; just return the first response text
    try:
        logging.debug("[gemini.tool_agent] no_function_calls_detected; returning model text")
    except Exception:
        pass
    try:
        safe_txt = _safe_text_from_response(resp) or ""
        print("[gemini.tool_agent] no_calls_returning_text:", safe_txt.strip())
    except Exception:
        print("[gemini.tool_agent] no_calls_returning_text: <unprintable>")
    return _safe_text_from_response(resp) or str(resp)
