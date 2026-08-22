"""
database.py — Async MongoDB (motor) + Redis connections.
Call connect_db() on startup and close_db() on shutdown.
"""

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

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


# ── Redis ──────────────────────────────────────────────────
_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call connect_db() first.")
    return _redis_client


# ── Lifecycle ──────────────────────────────────────────────
async def connect_db():
    global _mongo_client, _redis_client
    import certifi
    _mongo_client = AsyncIOMotorClient(settings.MONGODB_URI, tlsCAFile=certifi.where())
    _redis_client = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    print("Connected to MongoDB and Redis")


async def close_db():
    global _mongo_client, _redis_client
    if _mongo_client:
        _mongo_client.close()
    if _redis_client:
        await _redis_client.aclose()
    print("🔌 Database connections closed")
