"""
Redis service — manages connections to all 3 nodes and routes via
the ConsistentHashRing. Results are stored as JSON-serialised lists
of {query, score} dicts keyed by the lowercased prefix.
"""

import json
import asyncio
from typing import List, Dict, Optional, Tuple
import redis.asyncio as aioredis

from app.config import settings
from app.services.consistent_hashing import ConsistentHashRing


class RedisService:
    def __init__(self):
        self._clients: List[aioredis.Redis] = []
        self._nodes: List[str] = settings.redis_nodes
        self._ring: Optional[ConsistentHashRing] = None

    async def connect(self):
        self._clients = []
        for node in self._nodes:
            host, port = node.rsplit(":", 1)
            client = aioredis.Redis(
                host=host,
                port=int(port),
                decode_responses=True,
                socket_connect_timeout=2,
            )
            self._clients.append(client)
        self._ring = ConsistentHashRing(self._nodes)

    async def close(self):
        for client in self._clients:
            await client.aclose()

    def _get_client(self, prefix: str) -> Tuple[aioredis.Redis, str]:
        """Return (redis_client, node_label) for the given prefix."""
        node_label = self._ring.get_node(prefix.lower())
        idx = self._nodes.index(node_label)
        return self._clients[idx], node_label

    def get_node_for_prefix(self, prefix: str) -> str:
        return self._ring.get_node(prefix.lower())

    async def get_suggestions(self, prefix: str) -> Optional[List[Dict]]:
        client, _ = self._get_client(prefix)
        raw = await client.get(f"suggest:{prefix.lower()}")
        if raw is None:
            return None
        return json.loads(raw)

    async def set_suggestions(self, prefix: str, suggestions: List[Dict], ttl: int = None):
        client, _ = self._get_client(prefix)
        if ttl is None:
            ttl = settings.cache_ttl
        await client.setex(
            f"suggest:{prefix.lower()}",
            ttl,
            json.dumps(suggestions),
        )

    async def invalidate_prefix(self, prefix: str):
        """Delete a cached prefix — called after batch writes update scores."""
        client, _ = self._get_client(prefix)
        await client.delete(f"suggest:{prefix.lower()}")

    async def exists(self, prefix: str) -> bool:
        client, _ = self._get_client(prefix)
        return bool(await client.exists(f"suggest:{prefix.lower()}"))

    async def ping_all(self) -> Dict[str, bool]:
        results = {}
        for i, client in enumerate(self._clients):
            try:
                await client.ping()
                results[self._nodes[i]] = True
            except Exception:
                results[self._nodes[i]] = False
        return results


redis_service = RedisService()
