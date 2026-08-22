"""
utils/gemini_client.py — Shared Gemini API wrapper.
All AI services use these functions — never call the SDK directly elsewhere.
Uses the new google.genai SDK (google-genai package).
"""

import json
import re
from google import genai
from app.config import settings

# Configure client once on import
_client = genai.Client(api_key=settings.GEMINI_API_KEY)
MODEL = "gemini-3.6-flash"


from fastapi import HTTPException
from google.genai import errors

async def generate_text(prompt: str) -> str:
    """Send a plain text prompt and return the response string."""
    try:
        response = _client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return (response.text or "").strip()
    except errors.ClientError as e:
        if getattr(e, 'status_code', None) == 429:
            raise HTTPException(status_code=429, detail="AI Rate Limit Exceeded: Please wait 30 seconds and try again.")
        raise HTTPException(status_code=502, detail=f"AI API Error: {str(e)}")

async def generate_json(prompt: str) -> dict | list:
    """
    Send a prompt that expects JSON output.
    Automatically strips markdown code fences and parses the result.
    """
    full_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
    try:
        response = _client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
        )
    except errors.ClientError as e:
        if getattr(e, 'status_code', None) == 429:
            raise HTTPException(status_code=429, detail="AI Rate Limit Exceeded: Please wait 30 seconds and try again.")
        raise HTTPException(status_code=502, detail=f"AI API Error: {str(e)}")

    raw = (response.text or "").strip()

    # Strip ```json ... ``` fences more robustly
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Fallback: try to find an array or object in the raw text
        match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw output:\n{raw}")
