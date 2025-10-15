from typing import List, Dict

def basic_agent(messages: List[Dict]) -> str:
    return "[SmolAgent stub] This is a placeholder response."

def custom_system_prompt_agent(messages: List[Dict], system_prompt: str) -> str:
    return f"[SmolAgent stub] System prompt: {system_prompt[:80]}..."

def single_tool_agent(messages: List[Dict], tool) -> str:
    return "[SmolAgent stub] Tool-assisted response placeholder."
