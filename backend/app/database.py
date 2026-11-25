"""
database.py — Async MongoDB (motor) + optional Redis connections.
Call connect_db() on startup and close_db() on shutdown.
"""

import logging

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app.config import settings

log = logging.getLogger("tripwire.db")

# ── MongoDB ────────────────────────────────────────────────
_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    if _mongo_client is None:
        raise RuntimeError("MongoDB client not initialized. Call connect_db() first.")
    return _mongo_client


def get_db():
    return get_mongo_client()[settings.DB_NAME]


# Collections
def agents_col():
    return get_db()["agents"]


def scenarios_col():
    return get_db()["scenarios"]


def runs_col():
    return get_db()["runs"]


def reports_col():
    return get_db()["reports"]


def jobs_col():
    return get_db()["jobs"]


async def ensure_indexes():
    """Every list/aggregate query filters by agent_id — index it."""
    await scenarios_col().create_index([("agent_id", ASCENDING)])
    await runs_col().create_index([("agent_id", ASCENDING), ("created_at", DESCENDING)])
    await runs_col().create_index([("agent_id", ASCENDING), ("agent_version", ASCENDING)])
    await runs_col().create_index([("job_id", ASCENDING)])
    await reports_col().create_index([("agent_id", ASCENDING), ("type", ASCENDING), ("generated_at", DESCENDING)])
    await jobs_col().create_index([("agent_id", ASCENDING), ("created_at", DESCENDING)])


# ── Redis (optional — nothing breaks if it is down) ───────
_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    return _redis_client


# ── Lifecycle ──────────────────────────────────────────────
async def connect_db():
    global _mongo_client, _redis_client
    # tz_aware=True: datetimes come back as UTC-aware, so the API emits "+00:00"
    # and browsers stop showing UTC times as if they were local.
    # Atlas (mongodb+srv://) needs a CA bundle; a local mongod speaks no TLS.
    if settings.MONGODB_URI.startswith("mongodb+srv://"):
        import certifi
        _mongo_client = AsyncIOMotorClient(settings.MONGODB_URI, tlsCAFile=certifi.where(), tz_aware=True)
    else:
        _mongo_client = AsyncIOMotorClient(settings.MONGODB_URI, tz_aware=True)

    try:
        await ensure_indexes()
    except Exception as e:  # don't block startup on index creation
        log.warning("Could not create MongoDB indexes: %s", e)

    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await client.ping()
        _redis_client = client
    except Exception as e:
        _redis_client = None
        log.warning("Redis unavailable (%s) — continuing without it.", e)

    print(f"Connected to MongoDB{' and Redis' if _redis_client else ''}")


async def close_db():
    global _mongo_client, _redis_client
    if _mongo_client:
        _mongo_client.close()
    if _redis_client:
        await _redis_client.aclose()
    print("Database connections closed")
