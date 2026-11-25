"""
utils/gemini_client.py — Shared LLM wrapper.
All AI services use these functions — never call the SDK directly elsewhere.

- Uses the *async* google-genai API so concurrent runs really run concurrently
  (the old sync call blocked the event loop and serialised every request).
- A process-wide semaphore bounds simultaneous requests.
- 429 / 5xx responses are retried with exponential backoff + jitter, then an
  optional fallback model is tried once.
- JSON calls use Gemini's native JSON mode, with a tolerant parser as backup.
- MOCK_LLM=1 swaps in a deterministic offline model (see mock_llm.py).
"""

import asyncio
import json
import random
import re

from fastapi import HTTPException

from app.config import settings

MODEL = settings.GEMINI_MODEL

_client = None
_semaphore: asyncio.Semaphore | None = None

# Usage counters — exposed on /health so you can see what a run cost.
stats = {"requests": 0, "retries": 0, "failures": 0, "mock": settings.MOCK_LLM}

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Timestamps of recent 429s, so the UI can warn that results may contain errored runs.
_rate_limit_events: list[float] = []


def _record_rate_limit() -> None:
    import time
    now = time.time()
    _rate_limit_events.append(now)
    # keep the list short
    while _rate_limit_events and _rate_limit_events[0] < now - 3600:
        _rate_limit_events.pop(0)


def recent_rate_limits(window_s: int = 900) -> int:
    """How many 429 responses were seen in the last `window_s` seconds."""
    import time
    cutoff = time.time() - window_s
    return sum(1 for t in _rate_limit_events if t >= cutoff)


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(max(1, settings.LLM_MAX_CONCURRENCY))
    return _semaphore


def _status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


async def _call_model(model: str, prompt: str, json_mode: bool, temperature: float | None) -> str:
    from google.genai import types

    config_kwargs: dict = {}
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    if temperature is not None:
        config_kwargs["temperature"] = temperature
    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    response = await _get_client().aio.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return (response.text or "").strip()


async def _generate(prompt: str, json_mode: bool = False, temperature: float | None = None) -> str:
    if settings.MOCK_LLM:
        from app.utils.mock_llm import mock_generate, should_fail
        stats["requests"] += 1
        if should_fail(settings.MOCK_LLM_ERROR_RATE):
            stats["failures"] += 1
            _record_rate_limit()
            raise HTTPException(status_code=429, detail="AI rate limit exceeded after retries (simulated by MOCK_LLM_ERROR_RATE).")
        return mock_generate(prompt, json_mode)

    models = [MODEL]
    if settings.GEMINI_FALLBACK_MODEL and settings.GEMINI_FALLBACK_MODEL != MODEL:
        models.append(settings.GEMINI_FALLBACK_MODEL)

    last_exc: Exception | None = None
    async with _get_semaphore():
        for model in models:
            for attempt in range(settings.LLM_MAX_RETRIES + 1):
                try:
                    stats["requests"] += 1
                    return await _call_model(model, prompt, json_mode, temperature)
                except Exception as exc:  # SDK raises ClientError / ServerError / network errors
                    last_exc = exc
                    code = _status_code(exc)
                    if code == 429:
                        _record_rate_limit()
                    retryable = code in RETRYABLE_STATUS or code is None
                    if not retryable or attempt == settings.LLM_MAX_RETRIES:
                        break
                    stats["retries"] += 1
                    delay = min(20.0, (2 ** attempt) + random.uniform(0, 1))
                    await asyncio.sleep(delay)

    stats["failures"] += 1
    code = _status_code(last_exc) if last_exc else None
    if code == 429:
        raise HTTPException(status_code=429, detail="AI rate limit exceeded after retries. Wait ~30s and try again.")
    raise HTTPException(status_code=502, detail=f"AI API error: {last_exc}")


async def generate_text(prompt: str, temperature: float | None = None) -> str:
    """Send a plain text prompt and return the response string."""
    return await _generate(prompt, json_mode=False, temperature=temperature)


def parse_json_loose(raw: str) -> dict | list:
    """Parse JSON that may be wrapped in markdown fences or surrounded by prose."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        decoder = json.JSONDecoder()
        for i, ch in enumerate(raw):
            if ch in "[{":
                try:
                    value, _ = decoder.raw_decode(raw[i:])
                    return value
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw output:\n{raw[:500]}")


async def generate_json(prompt: str) -> dict | list:
    """Send a prompt that expects JSON output and return the parsed value."""
    full_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
    raw = await _generate(full_prompt, json_mode=True)
    return parse_json_loose(raw)
