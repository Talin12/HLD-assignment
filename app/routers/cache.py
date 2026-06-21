from fastapi import APIRouter, Query
from app.services.redis_service import redis_service
from app.config import settings

router = APIRouter()


@router.get("/cache/debug")
async def cache_debug(prefix: str = Query(..., description="Prefix to inspect")):
    """
    Debugging endpoint: shows which Redis node owns this prefix
    (via consistent hashing) and whether a cached entry exists.
    """
    prefix_lower = prefix.strip().lower()
    if not prefix_lower:
        return {"error": "prefix must not be empty"}

    node_label = redis_service.get_node_for_prefix(prefix_lower)
    hit = await redis_service.exists(prefix_lower)

    node_index = settings.redis_nodes.index(node_label) + 1

    return {
        "prefix": prefix_lower,
        "assigned_node": node_label,
        "node_index": node_index,
        "cache_status": "HIT" if hit else "MISS",
        "cache_key": f"suggest:{prefix_lower}",
    }


@router.get("/cache/node-health")
async def node_health():
    """Ping all 3 Redis nodes and report connectivity."""
    status = await redis_service.ping_all()
    return {
        "nodes": [
            {"node": node, "healthy": ok} for node, ok in status.items()
        ]
    }
