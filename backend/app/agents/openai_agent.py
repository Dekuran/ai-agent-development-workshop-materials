import os
import json
from typing import List, Dict, Optional, Any
from openai import OpenAI
from ..tools.registry import registry
from pathlib import Path
from dotenv import load_dotenv
import logging

# Ensure env vars load even when importing this module directly (pytest, REPL, etc.)
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
logger = logging.getLogger(__name__)

def _to_openai_messages(messages: List[Dict]):
    # Already in {role, content} format
    return messages

def _client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        # Fallback: read the repo .env directly in case another environment value was set earlier
        try:
            from dotenv import dotenv_values
            key = dotenv_values(Path(__file__).resolve().parents[2] / ".env").get("OPENAI_API_KEY")
        except Exception:
            key = key  # leave as-is
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set. Create a .env at the repo root and set OPENAI_API_KEY=...")
    # Masked debug to help diagnose which source is used without leaking the secret
    try:
        masked = (key[:4] + "..." + key[-4:]) if isinstance(key, str) and len(key) >= 8 else "set"
        logger.debug("OPENAI_API_KEY detected (%s)", masked)
    except Exception:
        pass
    return OpenAI(api_key=key)

def basic_agent(messages: List[Dict], model: Optional[str] = None) -> str:
    client = _client()
    mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(model=mdl, messages=_to_openai_messages(messages))
    return resp.choices[0].message.content

def custom_system_prompt_agent(messages: List[Dict], system_prompt: str, model: Optional[str] = None) -> str:
    client = _client()
    mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    msgs = [{"role":"system","content":system_prompt}] + _to_openai_messages(messages)
    resp = client.chat.completions.create(model=mdl, messages=msgs)
    return resp.choices[0].message.content

def single_tool_agent(messages: List[Dict], tool) -> str:
    # Simple pattern: search on last user message and provide results as context
    query = ""
    for m in reversed(messages):
        if m["role"] == "user":
            query = m["content"]
            break
    results = tool.search(query) if query else []
    context = "\\n".join(results)
    sys = f"You can use the following web results as optional context:\\n{context}"
    return custom_system_prompt_agent(messages, sys)


def tool_agent(
    messages: List[Dict],
    system_prompt: Optional[str],
    tools: Optional[List[Any]],
    model: Optional[str] = None
) -> str:
    """
    Provider-native tool calling for OpenAI Chat Completions.

    - Accepts ToolSpec list from tools.registry.get([...])
    - Preserves custom system prompt in tool mode
    - Supports model override
    """
    client = _client()
    mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    working_msgs: List[Dict[str, Any]] = []
    if system_prompt:
        working_msgs.append({"role": "system", "content": system_prompt})
    # Append prior conversation
    working_msgs.extend(_to_openai_messages(messages))

    # Build OpenAI tool schemas
    tool_defs = registry.to_openai_tools(tools or [])
    tool_choice = "auto" if tool_defs else "none"

    # Iterative tool loop with a small cap to prevent infinite loops
    last_msg_content: Optional[str] = None
    for _ in range(4):
        resp = client.chat.completions.create(
            model=mdl,
            messages=working_msgs,
            tools=tool_defs or None,
            tool_choice=tool_choice
        )
        msg = resp.choices[0].message
        last_msg_content = msg.content or last_msg_content

        # If the model responded with tool calls, execute them and continue
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            # Add the assistant message with tool_calls for traceability
            assistant_record: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            # Normalize tool_calls into dicts for the wire format
            normalized_calls = []
            for tc in tool_calls:
                normalized_calls.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
            assistant_record["tool_calls"] = normalized_calls
            working_msgs.append(assistant_record)

            # Execute each call and append a tool message with the result
            for tc in tool_calls:
                name = tc.function.name
                args_str = tc.function.arguments or "{}"
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}
                result = registry.runtime_execute(name, args)
                working_msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": result,
                })
            # Continue the loop to let the model observe tool results
            continue

        # No tool calls, return final content
        return msg.content or ""

    # Fallback if loop cap reached (return last content if available)
    return last_msg_content or ""
