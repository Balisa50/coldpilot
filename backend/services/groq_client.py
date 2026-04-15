"""
Groq API client for LLaMA 3 email generation.
Free tier: generous rate limits (30 req/min for llama3-70b).
"""
from __future__ import annotations

import os

import httpx

GROQ_BASE = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"


def _api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return key


async def chat(
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Send a chat completion request to Groq. Returns the assistant message."""
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GROQ_BASE}/chat/completions",
            headers=headers,
            json=payload,
        )
        if resp.status_code != 200:
            # Surface the actual error message from Groq
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text[:300])
            except Exception:
                err_msg = resp.text[:300]
            raise RuntimeError(f"Groq API {resp.status_code}: {err_msg}")
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"Groq returned no choices: {str(data)[:300]}")

    content = (choices[0].get("message") or {}).get("content") or ""
    if not content.strip():
        finish = choices[0].get("finish_reason", "")
        raise RuntimeError(f"Groq returned empty content (finish_reason={finish})")

    return content
