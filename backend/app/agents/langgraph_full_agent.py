from typing import List, Dict, TypedDict
import os
import google.generativeai as genai

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END


class GeminiLLMAdapter:
    def __init__(self, model_id: str) -> None:
        self.model = genai.GenerativeModel(model_id)

    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        # Flatten messages to a simple transcript for Gemini
        parts = []
        for m in messages:
            role = "user"
            content = ""
            try:
                if isinstance(m, SystemMessage):
                    role = "system"
                    content = m.content
                elif isinstance(m, HumanMessage):
                    role = "user"
                    content = m.content
                elif isinstance(m, AIMessage):
                    role = "assistant"
                    content = m.content
                else:
                    content = getattr(m, "content", "")
            except Exception:
                content = str(m)
            parts.append(f"{role}: {content}")
        prompt = "\n".join(parts)
        resp = self.model.generate_content(prompt)
        text = getattr(resp, "text", None)
        if not text:
            # Fallback for safety
            text = str(getattr(resp, "candidates", "") or "")
        return AIMessage(content=text)


def _to_lc_messages(messages: List[Dict]) -> List[BaseMessage]:
    out: List[BaseMessage] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out


def _llm():
    backend = os.getenv("LANGGRAPH_PROVIDER", "gemini").lower()
    if backend == "gemini":
        # Configure Gemini backend
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set for LangGraph Gemini backend")
        genai.configure(api_key=api_key)
        model_id = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash-002")
        return GeminiLLMAdapter(model_id)
    else:
        # Fallback: OpenAI via LangChain wrapper (requires langchain_openai)
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return ChatOpenAI(model=model, temperature=0)


class ChatState(TypedDict):
    messages: List[BaseMessage]


def _build_app():
    graph = StateGraph(ChatState)

    def llm_node(state: ChatState) -> ChatState:
        llm = _llm()
        response = llm.invoke(state["messages"])
        return {"messages": state["messages"] + [response]}

    graph.add_node("llm", llm_node)
    graph.set_entry_point("llm")
    graph.add_edge("llm", END)
    return graph.compile()


_app = None
def _get_app():
    global _app
    if _app is None:
        _app = _build_app()
    return _app


def _extract_text(msgs: List[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return m.content if isinstance(m.content, str) else str(m.content)
    return msgs[-1].content if msgs else ""


def basic_agent(messages: List[Dict]) -> str:
    """LangGraph basic agent: single-node graph that calls ChatOpenAI."""
    lc_messages = _to_lc_messages(messages)
    app = _get_app()
    result = app.invoke({"messages": lc_messages})
    return _extract_text(result["messages"])


def custom_system_prompt_agent(messages: List[Dict], system_prompt: str) -> str:
    """LangGraph agent with injected system prompt."""
    lc_messages = [SystemMessage(content=system_prompt)] + _to_lc_messages(messages)
    app = _get_app()
    result = app.invoke({"messages": lc_messages})
    return _extract_text(result["messages"])


def single_tool_agent(messages: List[Dict], tool) -> str:
    """
    LangGraph agent demonstrating a single external tool (search).
    Strategy: run a web search on the last user message and inject results as
    a system message before invoking the graph.
    """
    query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            query = m.get("content", "")
            break
    results = tool.search(query) if query else []
    context = "\n".join(results) if results else "No results."
    sys = f"You can use the following optional web search results as context:\n{context}"

    lc_messages = [SystemMessage(content=sys)] + _to_lc_messages(messages)
    app = _get_app()
    result = app.invoke({"messages": lc_messages})
    return _extract_text(result["messages"])
