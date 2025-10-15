from typing import List, Dict
import os

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI


def _to_lc_messages(messages: List[Dict]):
    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        # ignore unknown roles for workshop simplicity
    return out


def _llm():
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # ChatOpenAI will read OPENAI_API_KEY from env
    return ChatOpenAI(model=model, temperature=0)


def basic_agent(messages: List[Dict]) -> str:
    """LangChain basic agent using ChatOpenAI with provided messages."""
    lc_messages = _to_lc_messages(messages)
    llm = _llm()
    resp = llm.invoke(lc_messages)
    return resp.content


def custom_system_prompt_agent(messages: List[Dict], system_prompt: str) -> str:
    """LangChain agent with an injected system prompt."""
    lc_messages = [SystemMessage(content=system_prompt)] + _to_lc_messages(messages)
    llm = _llm()
    resp = llm.invoke(lc_messages)
    return resp.content


def single_tool_agent(messages: List[Dict], tool) -> str:
    """
    LangChain agent demonstrating a single external tool (search).
    Strategy: run a web search on the last user message and prepend the results
    as additional system guidance.
    """
    query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            query = m.get("content", "")
            break

    results = tool.search(query) if query else []
    context = "\n".join(results) if results else "No results."
    sys = f"You can use the following optional web search results as context:\n{context}"
    return custom_system_prompt_agent(messages, sys)
