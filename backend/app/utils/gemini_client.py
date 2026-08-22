"""
utils/gemini_client.py — Shared Gemini API wrapper.
All AI services use these functions — never call the SDK directly elsewhere.
"""

import json
import re
import google.generativeai as genai
from app.config import settings

# Configure once on import
genai.configure(api_key=settings.GEMINI_API_KEY)

_model = genai.GenerativeModel("gemini-2.0-flash")


async def generate_text(prompt: str) -> str:
    """Send a plain text prompt and return the response string."""
    response = _model.generate_content(prompt)
    return response.text.strip()


async def generate_json(prompt: str) -> dict | list:
    """
    Send a prompt that expects JSON output.
    Automatically strips markdown code fences and parses the result.
    """
    full_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
    response = _model.generate_content(full_prompt)
    raw = response.text.strip()

    # Strip ```json ... ``` fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw output:\n{raw}")
