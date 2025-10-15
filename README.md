<<<<<<< HEAD
# Multi-Agent AI Workshop Scaffold

Hands-on workshop comparing multiple LLM providers and orchestration frameworks with a FastAPI backend and two frontends (Streamlit prototype-first, Next.js optional).

## Structure

- backend – FastAPI API with modular agents, tools, and services
- frontend-streamlit – Rapid prototype UI (primary)
- frontend-nextjs – Modern React UI (secondary, optional)
- uploaded_files – Shared file drop for tools
- backend/data – SQLite database

## Quickstart

1) Copy sample.env to .env and fill keys
   cp sample.env .env

2) Backend setup (uses uv; falls back gracefully)
   ./backend/setup.sh

3) Initialize DB (optional, setup runs this too)
   uv run -C backend python backend/scripts/init_db.py

4) Run backend
   ./backend/run_backend.sh
   API: http://localhost:8000
   Docs: http://localhost:8000/docs

5) Streamlit UI (primary)
   cd frontend-streamlit
   ./run_frontend.sh
   UI: http://localhost:8501

6) Next.js UI (secondary, optional)
   cd frontend-nextjs
   ./run_frontend.sh
   UI: http://localhost:3000

## Providers and Frameworks

Providers: OpenAI, Anthropic, Google Gemini, Ollama (local). DeepSeek is included as a placeholder.
Frameworks: LangChain, LangGraph, SmolAgent (stubs for workshop-friendly install times).

Each agent file exposes three functions: basic_agent(), custom_system_prompt_agent(), single_tool_agent().

## Endpoints

- POST /chat/{provider}
- POST /upload
- POST /db/query
- GET  /health

See backend/README.md for details.

## Frontend Guidance

- Streamlit is ideal for workshops and rapid prototyping.
- Next.js is better for product-grade UX and deployment (e.g., Vercel).

=======
# ai-agent-development-workshop-materials
Materials for a code-along workshop on AI agent development. To be further developed with additional models and functions.
>>>>>>> d016bc1725f965d73c13f8e12750c4c8cdcc1961
