"""
utils/ids.py — ObjectId parsing and Mongo document serialisation helpers.
"""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def parse_object_id(value: str, what: str = "id") -> ObjectId:
    """Convert a path/query id to ObjectId, returning a clean 400 instead of a 500."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {what}: {value!r}")


def serialize(doc: dict) -> dict:
    """Move Mongo's `_id` to a string `id` field."""
    if doc is None:
        return doc
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
