import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import create_tables
from app.services.redis_service import redis_service
from app.services.batch_writer import batch_writer
from app.routers import suggest, search, cache

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Creating database tables if needed...")
    await create_tables()

    logger.info("Connecting to Redis nodes...")
    await redis_service.connect()

    logger.info("Starting batch writer...")
    batch_writer.start()

    yield

    # Shutdown
    logger.info("Stopping batch writer (flushing remaining buffer)...")
    await batch_writer.stop()

    logger.info("Closing Redis connections...")
    await redis_service.close()


app = FastAPI(
    title="Search Typeahead System",
    description="HLD Assignment — Typeahead with consistent hashing, write-behind cache, and recency scoring",
    version="1.0.0",
    lifespan=lifespan,
)

# ── API Routers ────────────────────────────────────────────────────────────────
app.include_router(suggest.router, tags=["Suggest"])
app.include_router(search.router, tags=["Search"])
app.include_router(cache.router, tags=["Cache Debug"])

# ── Static frontend ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    redis_status = await redis_service.ping_all()
    return {
        "status": "ok",
        "redis_nodes": redis_status,
    }
