"""Backend tool catalog and invoke APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_ecommerce_user_id, get_db, get_read_db, get_redis
from app.tools.runtime_tools import ToolContext, registry

router = APIRouter()


class ToolDefinitionResponse(BaseModel):
    name: str
    summary: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_summary: str = ""
    tags: list[str] = Field(default_factory=list)


class ToolInvokeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    args: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    name: str
    result: Any


@router.get("", response_model=list[ToolDefinitionResponse])
async def list_tools() -> list[ToolDefinitionResponse]:
    """List callable backend tools for skill/agent integration."""
    return [
        ToolDefinitionResponse(
            name=item.name,
            summary=item.summary,
            input_schema=item.input_schema,
            output_summary=item.output_summary,
            tags=item.tags,
        )
        for item in registry.list_tools()
    ]


@router.post("/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(
    payload: ToolInvokeRequest,
    redis: Any = Depends(get_redis),
    db=Depends(get_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
) -> ToolInvokeResponse:
    """Invoke one backend tool through a unified contract."""
    try:
        result = await registry.invoke(
            payload.name,
            context=ToolContext(user_id=user_id, redis=redis, db=db),
            args=payload.args,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ToolInvokeResponse(name=payload.name, result=result)
