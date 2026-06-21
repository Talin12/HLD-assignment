# Search Typeahead System — HLD Assignment

A production-style search typeahead service built with **FastAPI**, **PostgreSQL**, and **3 Redis nodes**, containerised with **Docker Compose**. Implements consistent hashing, write-behind batching, and exponential-decay recency scoring.

---

## Quick Start

```bash
git clone <repo-url>
cd HLD-Assignment
docker compose up --build
```

Open **http://localhost:8000** in your browser.

First boot generates ~100 k synthetic queries and seeds PostgreSQL (takes ~30–60 s). Subsequent boots skip the seed step.

---

## Architecture

```
Browser
  │
  │  GET /suggest?q=<prefix>   (debounced, 300 ms)
  │  POST /search              (on Enter / click)
  ▼
FastAPI  (uvicorn, async)
  │
  ├─► Consistent Hash Ring ──► Redis Node 1 / 2 / 3  (cache)
  │        (150 virtual nodes per physical node)
  │
  └─► PostgreSQL   (source of truth)
        ▲
        │  bulk UPSERT every 5 s / 500 events
  Batch Writer (in-process asyncio task)
        ▲
        │  push()
  POST /search handler
```

### 1. Consistent Hashing

**File:** `app/services/consistent_hashing.py`

Each physical Redis node is assigned **150 virtual nodes** on a 32-bit ring (positions computed with MD5). When a prefix arrives:

1. MD5-hash the lowercased prefix → 32-bit integer position.
2. Walk clockwise on the sorted ring until the first vnode position ≥ hash.
3. The vnode's owning physical node is the target Redis instance.

Virtual nodes distribute load ~evenly even with only 3 physical nodes, and minimise key re-mapping when a node is added or removed (only 1/N of keys migrate per ring change).

### 2. Write-Behind Batch Writer

**File:** `app/services/batch_writer.py`

`POST /search` returns `{"message": "Searched"}` in microseconds. The actual DB write is deferred:

| Step | Detail |
|------|--------|
| Buffer | In-memory `dict[query → {count, last_ts}]` protected by `asyncio.Lock` |
| Flush trigger | Whichever comes first: 500 events accumulated **or** 5 seconds elapsed |
| DB write | Single SQL `INSERT … ON CONFLICT DO UPDATE` covering all buffered queries |
| On crash | Events still in the buffer are **lost** — acceptable for a ranking signal; recency scores will simply under-count those events |

**Trade-off**: write throughput is ~100× higher than per-event updates; rare small counts may be dropped on crash. For higher durability, the buffer could be mirrored to a Redis list (durable with AOF) before flushing to Postgres.

### 3. Recency + Popularity Scoring

**File:** `app/services/scoring.py`

Each row stores a running **recency accumulator** `R` updated on every flush:

```
R_new = R_old × e^(−λ × Δt)  +  event_count
```

Where:
- `λ = 0.0001` (configurable via `DECAY_LAMBDA` env var)
- `Δt` = seconds since the row's `last_searched_at`
- Half-life ≈ `ln(2) / λ ≈ 6931 s ≈ 1.9 hours`

The final combined ranking score used for suggestions and trending:

```
score(q) = frequency × 1.0  +  R × 50.0
```

The `×50` weight gives recency strong influence so a sudden surge
(e.g. a viral query searched 500 times in 10 minutes) rapidly floats to the
top even if its all-time `frequency` is low.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/suggest?q=<prefix>` | Returns up to 10 suggestions, hitting Redis first |
| `POST` | `/search` | Accepts `{"query": "…"}`, buffers it, returns `{"message": "Searched"}` |
| `GET`  | `/trending?limit=N` | Top N queries by recency score |
| `GET`  | `/cache/debug?prefix=<p>` | Which Redis node owns `p`, and HIT/MISS status |
| `GET`  | `/cache/node-health` | Ping all 3 Redis nodes |
| `GET`  | `/search/buffer-stats` | Current batch-writer buffer depth |
| `GET`  | `/health` | Overall service health |
| `GET`  | `/docs` | Swagger UI |

### Example: suggest

```bash
curl "http://localhost:8000/suggest?q=py"
```

```json
{
  "prefix": "py",
  "source": "db",
  "suggestions": [
    {"query": "python tutorial", "score": 4823.5, "frequency": 982},
    {"query": "python async await", "score": 3201.0, "frequency": 640}
  ]
}
```

`source` is `"cache"` on subsequent calls (within TTL=300 s).

### Example: cache debug

```bash
curl "http://localhost:8000/cache/debug?prefix=py"
```

```json
{
  "prefix": "py",
  "assigned_node": "redis-node-2:6379",
  "node_index": 2,
  "cache_status": "HIT",
  "cache_key": "suggest:py"
}
```

---

## Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `postgres` | PostgreSQL hostname |
| `REDIS_NODE_1/2/3` | `redis-node-N:6379` | Redis node addresses |
| `CACHE_TTL` | `300` | Suggestion cache TTL (seconds) |
| `BATCH_MAX_SIZE` | `500` | Flush at this many buffered events |
| `BATCH_FLUSH_INTERVAL` | `5` | Flush every N seconds |
| `DECAY_LAMBDA` | `0.0001` | Recency decay rate (λ) |

---

## Testing / Observability

### Generate load

```bash
# 200 rapid searches to see batch writer & recency in action
for i in $(seq 1 200); do
  curl -s -X POST http://localhost:8000/search \
    -H "Content-Type: application/json" \
    -d '{"query":"python tutorial"}' > /dev/null
done
```

### Check buffer depth (before flush)

```bash
curl http://localhost:8000/search/buffer-stats
```

### Debug cache routing

```bash
curl "http://localhost:8000/cache/debug?prefix=mac"
```

### Watch Redis nodes

```bash
docker exec typeahead-redis-1 redis-cli monitor
```

### PostgreSQL queries

```bash
docker exec -it typeahead-postgres psql -U typeahead -d typeahead -c \
  "SELECT query, frequency, recency_score FROM search_queries ORDER BY recency_score DESC LIMIT 10;"
```

---

## Project Structure

```
.
├── app/
│   ├── main.py                  # FastAPI app + lifespan hooks
│   ├── config.py                # Pydantic settings (env-driven)
│   ├── database.py              # Async SQLAlchemy engine + session
│   ├── models.py                # ORM model for search_queries table
│   ├── routers/
│   │   ├── suggest.py           # GET /suggest, GET /trending
│   │   ├── search.py            # POST /search, GET /search/buffer-stats
│   │   └── cache.py             # GET /cache/debug, GET /cache/node-health
│   ├── services/
│   │   ├── consistent_hashing.py  # Virtual-node ring from scratch
│   │   ├── redis_service.py       # Async Redis client pool + routing
│   │   ├── batch_writer.py        # Write-behind async buffer
│   │   └── scoring.py             # Recency + popularity formula
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── scripts/
│   ├── generate_dataset.py      # Generates 100k+ Zipf-distributed queries
│   ├── init_db.py               # Creates tables + indexes (sync, at boot)
│   └── seed_db.py               # Bulk COPY from generate_dataset.py stdout
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
└── requirements.txt
```
