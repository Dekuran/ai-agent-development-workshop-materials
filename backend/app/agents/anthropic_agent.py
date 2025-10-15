import os
from typing import List, Dict, Optional, Any
import anthropic
from ..tools.registry import registry

def _client():
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def _to_messages(messages: List[Dict]):
    """
    Convert generic messages into Anthropic format.
    - system: list[{"type":"text","text": "..."}] or None
    - messages: list of turns with content as list of blocks
    """
    system_texts = []
    turns = []
    for m in messages:
        if m["role"] == "system":
            system_texts.append(m["content"])
        else:
            turns.append({
                "role": m["role"],
                "content": [{"type": "text", "text": m["content"]}],
            })
    system_blocks = [{"type": "text", "text": "\n".join(system_texts)}] if system_texts else None
    return system_blocks, turns

def basic_agent(messages: List[Dict], model: Optional[str] = None) -> str:
    client = _client()
    mdl = model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    system, turns = _to_messages(messages)
    # Only include the 'system' param when present to avoid server-side type validation issues
    create_kwargs = {"model": mdl, "messages": turns, "max_tokens": 512}
    if system:
        create_kwargs["system"] = system
    resp = client.messages.create(**create_kwargs)
    return resp.content[0].text

def custom_system_prompt_agent(messages: List[Dict], system_prompt: str, model: Optional[str] = None) -> str:
    client = _client()
    mdl = model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    _, turns = _to_messages(messages)
    system_blocks = [{"type": "text", "text": system_prompt}]
    resp = client.messages.create(model=mdl, system=system_blocks, messages=turns, max_tokens=512)
    return resp.content[0].text

def single_tool_agent(messages: List[Dict], tool) -> str:
    query = ""
    for m in reversed(messages):
        if m["role"] == "user":
            query = m["content"]
            break
    results = tool.search(query) if query else []
    sys = "Use these web results as optional context:\\n" + "\\n".join(results)
    return custom_system_prompt_agent(messages, sys)


def tool_agent(
    messages: List[Dict],
    system_prompt: Optional[str],
    tools: Optional[List[Any]],
    model: Optional[str] = None
) -> str:
    """
    Provider-native tool calling for Anthropic Messages API.

    - Accepts ToolSpec list from tools.registry.get([...])
    - Preserves custom system prompt in tool mode
    - Supports model override
    - Follows Anthropic tool_use -> tool_result turn-taking pattern
    """
    client = _client()
    mdl = model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

    # Extract existing system blocks and turns from prior convo
    system_blocks, turns = _to_messages(messages)

    # Merge custom system_prompt if provided
    if system_prompt:
        merged_texts = []
        if system_blocks:
            for b in system_blocks:
                if isinstance(b, dict) and b.get("type") == "text":
                    merged_texts.append(b.get("text", ""))
        merged_texts.append(system_prompt)
        system_blocks = [{"type": "text", "text": "\n".join([t for t in merged_texts if t])}]

    # Build Anthropic tool schemas
    try:
        tool_defs = registry.to_anthropic_tools(tools or [])
    except Exception:
        tool_defs = []

    # Working transcript (Anthropic wire format)
    working_messages: List[Dict[str, Any]] = list(turns)

    # Iterative tool loop with a small cap to prevent infinite loops
    last_text: str = ""
    for _ in range(4):
        create_kwargs: Dict[str, Any] = {
            "model": mdl,
            "messages": working_messages,
            "max_tokens": 512,
        }
        if system_blocks:
            create_kwargs["system"] = system_blocks
        if tool_defs:
            create_kwargs["tools"] = tool_defs

        resp = client.messages.create(**create_kwargs)

        # Helpers to normalize SDK blocks/dicts
        def _block_type(b):
            return getattr(b, "type", None) if not isinstance(b, dict) else b.get("type")

        def _block_text(b):
            if isinstance(b, dict):
                return b.get("text")
            return getattr(b, "text", None)

        # Gather any text emitted by the assistant this turn
        text_parts = [_block_text(b) for b in resp.content if _block_type(b) == "text"]
        emitted_text = "\n".join([t for t in text_parts if t]) if text_parts else ""
        if emitted_text:
            last_text = emitted_text

        # Collect tool_use blocks, if any
        tool_uses = [b for b in resp.content if _block_type(b) == "tool_use"]

        if tool_uses:
            # Append the assistant turn with its blocks (including tool_use)
            assistant_turn: Dict[str, Any] = {"role": "assistant", "content": []}
            for b in resp.content:
                if isinstance(b, dict):
                    assistant_turn["content"].append(b)
                else:
                    bt = getattr(b, "type", None)
                    entry: Dict[str, Any] = {"type": bt}
                    if bt == "tool_use":
                        entry["id"] = getattr(b, "id", None)
                        entry["name"] = getattr(b, "name", None)
                        entry["input"] = getattr(b, "input", None) or {}
                    elif bt == "text":
                        entry["text"] = getattr(b, "text", "")
                    assistant_turn["content"].append(entry)
            working_messages.append(assistant_turn)

            # Execute tools and respond with tool_result blocks in a user turn
            results_content: List[Dict[str, Any]] = []
            for tu in tool_uses:
                # SDK object or dict
                tu_id = getattr(tu, "id", None) if not isinstance(tu, dict) else tu.get("id")
                name = getattr(tu, "name", None) if not isinstance(tu, dict) else tu.get("name")
                input_obj = getattr(tu, "input", None) if not isinstance(tu, dict) else tu.get("input", {})
                try:
                    tool_name = name if isinstance(name, str) and name else "_unknown_tool_"
                    result_str = registry.runtime_execute(tool_name, input_obj or {})
                except Exception as e:
                    result_str = f"[tool error] {type(e).__name__}: {e}"
                results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tu_id,
                    "content": result_str
                })
            working_messages.append({"role": "user", "content": results_content})
            # Continue loop to let the model observe tool results
            continue

        # No tool calls; return accumulated/last text
        return emitted_text or last_text

    # Fallback if loop cap reached
    return last_text or ""
