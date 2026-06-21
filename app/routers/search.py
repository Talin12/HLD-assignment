from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.services.batch_writer import batch_writer

router = APIRouter()


class SearchRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        if len(v) > 255:
            raise ValueError("query too long (max 255 characters)")
        return v


@router.post("/search")
async def search(body: SearchRequest):
    """
    Low-latency search submission endpoint.
    Pushes the query into the async batch-writer buffer and returns
    immediately — no DB writes on this path.
    """
    await batch_writer.push(body.query)
    return {"message": "Searched"}


@router.get("/search/buffer-stats")
async def buffer_stats():
    """Debug: show how many events are currently buffered."""
    return await batch_writer.get_buffer_stats()
