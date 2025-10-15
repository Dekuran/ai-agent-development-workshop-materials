from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from ..services.agent_router import dispatch_agent
from ..tools.registry import registry

router = APIRouter(tags=["chat"])

class ChatMessage(BaseModel):
    role: Literal["system","user","assistant"]
    content: str

class ChatRequest(BaseModel):
    agent_variant: Literal["basic","custom","tool"]
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None                # e.g., ["web_search","file_read"]
    model: Optional[str] = None                      # provider-specific model override
    framework_provider: Optional[str] = None         # for frameworks like langgraph (default: "gemini")

@router.post("/chat/{provider}")
async def chat(
    provider: str = Path(..., description="Provider or framework id"),
    body: Optional[ChatRequest] = None
):
    try:
        if body is None:
            raise HTTPException(status_code=400, detail="Missing request body")
        provider_lc = provider.lower()

        # Build selected tools from registry
        selected_tools = registry.get(body.tools)

        # Default framework provider for langgraph if not provided
        framework_provider = body.framework_provider or ("gemini" if provider_lc == "langgraph" else None)

        text = await dispatch_agent(
            provider=provider_lc,
            variant=body.agent_variant,
            messages=[m.model_dump() for m in body.messages],
            system_prompt=body.system_prompt,
            tools=selected_tools,
            model=body.model,
            framework_provider=framework_provider,
        )
        return {"content": text}
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
