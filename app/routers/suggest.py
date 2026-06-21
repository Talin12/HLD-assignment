from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict

from app.database import get_db
from app.services.redis_service import redis_service
from app.services.scoring import compute_score
from app.config import settings

router = APIRouter()

MAX_SUGGESTIONS = 10


@router.get("/suggest")
async def suggest(
    q: str = Query(default="", description="Search prefix"),
    db: AsyncSession = Depends(get_db),
):
    prefix = q.strip().lower()

    if not prefix:
        return {"prefix": prefix, "source": "empty", "suggestions": []}

    # ── Cache Lookup ─────────────────────────────────────────────────────────
    cached = await redis_service.get_suggestions(prefix)
    if cached is not None:
        return {"prefix": prefix, "source": "cache", "suggestions": cached}

    # ── Cache Miss: query PostgreSQL ──────────────────────────────────────────
    rows = await db.execute(
        text("""
            SELECT query, frequency, recency_score
            FROM search_queries
            WHERE query LIKE :pattern
            ORDER BY (frequency * :wf + recency_score * :wr) DESC
            LIMIT :limit
        """),
        {
            "pattern": f"{prefix}%",
            "wf": 1.0,
            "wr": 50.0,
            "limit": MAX_SUGGESTIONS,
        },
    )
    results = rows.fetchall()

    suggestions = [
        {
            "query": row.query,
            "score": round(compute_score(row.frequency, row.recency_score), 4),
            "frequency": row.frequency,
        }
        for row in results
    ]

    # ── Populate cache ────────────────────────────────────────────────────────
    if suggestions:
        await redis_service.set_suggestions(prefix, suggestions)

    return {"prefix": prefix, "source": "db", "suggestions": suggestions}


@router.get("/trending")
async def trending(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return top queries ordered by recency_score (trending right now)."""
    rows = await db.execute(
        text("""
            SELECT query, frequency, recency_score,
                   (frequency * 1.0 + recency_score * 50.0) AS score
            FROM search_queries
            ORDER BY recency_score DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return {
        "trending": [
            {
                "query": r.query,
                "score": round(r.score, 4),
                "frequency": r.frequency,
                "recency_score": round(r.recency_score, 4),
            }
            for r in rows.fetchall()
        ]
    }
