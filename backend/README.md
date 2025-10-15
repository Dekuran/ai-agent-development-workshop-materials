# Backend (FastAPI)

Modular FastAPI backend with providers and frameworks organized under app/agents, and cross-cutting tools under app/tools.

## Endpoints

- POST /chat/{provider} – Chat with selected provider and agent variant
- POST /upload – Uploads a file into repository-level uploaded_files/ directory
- POST /db/query – Executes read-only SQL (SELECT) against SQLite db
- GET /health – Health check

## Providers

- openai
- anthropic
- google
- ollama
- deepseek (placeholder)

## Frameworks

- langchain (stub)
- langgraph (stub)
- smolagent (stub)

Each agent module exposes:
- basic_agent(messages)
- custom_system_prompt_agent(messages, system_prompt)
- single_tool_agent(messages, tool)

## Dev

- Setup: ./setup.sh
- Run:   ./run_backend.sh

