"""
Batch Writer (Write-Behind Cache)
-----------------------------------
Accepts individual search events, buffers them in memory, and periodically
flushes aggregated counts to PostgreSQL via a bulk UPSERT.

Trade-offs:
  PRO  — dramatically reduces write pressure on Postgres (one UPSERT per batch
          vs. one UPDATE per search event).
  CON  — if the process crashes between flushes, buffered events are lost.
         Acceptable for analytics / ranking data where slight under-counting
         is preferable to blocking the hot search path.

The flush triggers when EITHER:
  - buffer size reaches BATCH_MAX_SIZE, OR
  - BATCH_FLUSH_INTERVAL seconds have elapsed since the last flush.
"""

import asyncio
import time
import logging
from collections import defaultdict
from typing import Dict

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.config import settings
from app.services.scoring import decay_recency

logger = logging.getLogger(__name__)


class BatchWriter:
    def __init__(self):
        # Maps query -> {"count": int, "last_ts": float}
        self._buffer: Dict[str, dict] = defaultdict(lambda: {"count": 0, "last_ts": 0.0})
        self._lock = asyncio.Lock()
        self._task: asyncio.Task = None

    def start(self):
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("BatchWriter started (interval=%ds, max_size=%d)",
                    settings.batch_flush_interval, settings.batch_max_size)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.flush()  # drain remaining buffer on shutdown

    async def push(self, query: str):
        """Record a single search event. Thread-safe via asyncio lock."""
        q = query.strip().lower()
        if not q:
            return
        async with self._lock:
            self._buffer[q]["count"] += 1
            self._buffer[q]["last_ts"] = time.time()
            current_size = len(self._buffer)

        if current_size >= settings.batch_max_size:
            asyncio.create_task(self.flush())

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(settings.batch_flush_interval)
            await self.flush()

    async def flush(self):
        async with self._lock:
            if not self._buffer:
                return
            snapshot = dict(self._buffer)
            self._buffer.clear()

        try:
            await self._write_to_db(snapshot)
            logger.debug("BatchWriter flushed %d unique queries", len(snapshot))
        except Exception as exc:
            logger.error("BatchWriter flush failed: %s", exc)
            # Re-merge failed events back so they aren't silently dropped
            async with self._lock:
                for q, data in snapshot.items():
                    self._buffer[q]["count"] += data["count"]
                    self._buffer[q]["last_ts"] = max(
                        self._buffer[q]["last_ts"], data["last_ts"]
                    )

    async def _write_to_db(self, snapshot: Dict[str, dict]):
        """
        Bulk UPSERT using PostgreSQL's ON CONFLICT DO UPDATE.
        Recency score is decayed from existing value then incremented by the
        new event count using the exponential decay formula.
        """
        now = time.time()
        rows = [
            {
                "query": q,
                "count": data["count"],
                "last_ts": data["last_ts"],
            }
            for q, data in snapshot.items()
        ]

        upsert_sql = text("""
            INSERT INTO search_queries (query, frequency, last_searched_at, recency_score)
            VALUES (:query, :count, :last_ts,
                    :count * exp(-:lambda * GREATEST(0, :last_ts - 0)))
            ON CONFLICT (query) DO UPDATE SET
                frequency         = search_queries.frequency + EXCLUDED.frequency,
                last_searched_at  = EXCLUDED.last_searched_at,
                recency_score     = (
                    search_queries.recency_score
                    * exp(-:lambda * GREATEST(0, EXCLUDED.last_searched_at
                                              - search_queries.last_searched_at))
                ) + EXCLUDED.frequency,
                updated_at        = now()
        """)

        async with AsyncSessionLocal() as session:
            for row in rows:
                await session.execute(
                    upsert_sql,
                    {**row, "lambda": settings.decay_lambda},
                )
            await session.commit()

    async def get_buffer_stats(self) -> dict:
        async with self._lock:
            return {
                "buffered_unique_queries": len(self._buffer),
                "total_buffered_events": sum(v["count"] for v in self._buffer.values()),
            }


batch_writer = BatchWriter()
