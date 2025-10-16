import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(".env")

BACKEND_URL = os.getenv("NEXT_PUBLIC_BACKEND_URL", "http://localhost:8051")

st.set_page_config(page_title="Multi-Agent Workshop", page_icon="🤖", layout="centered")

st.title("🤖 Multi-Agent Workshop (Streamlit)")
st.caption(f"Backend: {BACKEND_URL}")

with st.sidebar:
    st.header("⚙️ Agent Settings")
    provider = st.selectbox("Provider / Framework",
                            [
                                "gemini", "openai", "anthropic", "google",
                                "ollama", "langchain", "langgraph", "smolagent", "deepseek"
                            ]
                            )
    variant = st.selectbox("Agent Variant", ["basic", "custom","tool"])

    # System prompt visible for custom and tool variants
    system_prompt = ""
    if variant in ("custom", "tool"):
        system_prompt = st.text_area("System Prompt", "You are a helpful assistant.", height=120)

    # Tool selection (available across providers; used when variant == "tool")
    tools_available = ["web_search", "file_finder", "file_read", "sqlite_query", "sqlite_execute"]
    selected_tools = st.multiselect("Tools", tools_available, default=["web_search"] if variant == "tool" else [])

    # Model override
    model_override = st.text_input("Model override (optional): ", value="")

    # Framework backend (for frameworks like LangGraph)
    framework_provider = None
    if provider == "langgraph":
        framework_provider = st.selectbox("Framework backend", ["gemini"], index=0)

    st.divider()
    st.subheader("📎 Upload file")
    uploaded = st.file_uploader("Upload file", type=None)
    if uploaded:
        files = {"file": (uploaded.name, uploaded.getvalue())}
        r = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=60)
        if r.ok:
            st.success(f"Uploaded: {uploaded.name}")
        else:
            st.error(r.text)


if "chat" not in st.session_state:
    st.session_state.chat = []

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_input = st.chat_input("Type your message")
if user_input:
    st.session_state.chat.append({"role":"user","content":user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    body = {
        "agent_variant": variant,
        "messages": st.session_state.chat,
        "system_prompt": system_prompt if variant in ("custom","tool") else None,
        "tools": selected_tools or None,
        "model": model_override or None,
        "framework_provider": framework_provider if provider == "langgraph" else None,
    }

    with st.spinner("Thinking..."):
        r = requests.post(f"{BACKEND_URL}/chat/{provider}", json=body, timeout=120)
    if r.ok:
        content = r.json().get("content","")
        st.session_state.chat.append({"role":"assistant","content":content})
        with st.chat_message("assistant"):
            st.markdown(content)
    else:
        st.error(r.text)
