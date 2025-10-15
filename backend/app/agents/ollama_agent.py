import os
from typing import List, Dict
import ollama

def _model():
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b")

def _to_messages(messages: List[Dict]):
    # Ollama chat expects {role, content}
    return messages

def basic_agent(messages: List[Dict]) -> str:
    resp = ollama.chat(model=_model(), messages=_to_messages(messages))
    return resp["message"]["content"]

def custom_system_prompt_agent(messages: List[Dict], system_prompt: str) -> str:
    msgs = [{"role":"system","content":system_prompt}] + _to_messages(messages)
    resp = ollama.chat(model=_model(), messages=msgs)
    return resp["message"]["content"]

def single_tool_agent(messages: List[Dict], tool) -> str:
    query = ""
    for m in reversed(messages):
        if m["role"] == "user":
            query = m["content"]
            break
    results = tool.search(query) if query else []
    sys = "Use these optional search results as context:\\n" + "\\n".join(results)
    return custom_system_prompt_agent(messages, sys)
