"""
Groq API client for LLaMA 3 email generation.
Free tier: generous rate limits. We fall back across a few models because
llama-3.3-70b-versatile has been flaky lately (returning truncated/garbage
responses with finish_reason=length on short outputs).
"""
from __future__ import annotations

import os

import httpx

GROQ_BASE = "https://api.groq.com/openai/v1"

# Try these models in order. The first one that returns a non-garbage
# response wins. 8b-instant is rock-solid; 70b-versatile gives nicer prose
# when it works.
MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


def _api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return key


def _looks_like_garbage(text: str) -> bool:
    """A response is garbage if it's too short to be a real email or mostly
    non-printable bytes. Guards against Groq returning things like '8\\ufffd'.
    """
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < 20:
        return True
    # If > 10% of chars are replacement characters or control bytes, it's garbage
    bad = sum(1 for c in stripped if c == "\ufffd" or (ord(c) < 32 and c not in "\n\r\t"))
    if bad > len(stripped) * 0.1:
        return True
    return False


async def _call_once(
    client: httpx.AsyncClient,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, str, dict]:
    """Make a single Groq call. Returns (content, finish_reason, full_data)."""
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = await client.post(
        f"{GROQ_BASE}/chat/completions",
        headers=headers,
        json=payload,
    )
    if resp.status_code != 200:
        try:
            err_body = resp.json()
            err_msg = err_body.get("error", {}).get("message", resp.text[:300])
        except Exception:
            err_msg = resp.text[:300]
        raise RuntimeError(f"Groq API {resp.status_code} ({model}): {err_msg}")

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"Groq ({model}) returned no choices: {str(data)[:300]}")

    content = (choices[0].get("message") or {}).get("content") or ""
    finish = choices[0].get("finish_reason", "")
    return content, finish, data


async def chat(
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Send a chat completion request to Groq. Returns the assistant message.

    Tries multiple models and rejects garbage responses (truncated/corrupt).
    """
    last_error = ""
    last_content = ""
    last_finish = ""
    last_model = ""

    async with httpx.AsyncClient(timeout=60) as client:
        for model in MODELS:
            try:
                content, finish, _data = await _call_once(
                    client, model, system, user, temperature, max_tokens
                )
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                last_model = model
                continue

            if not _looks_like_garbage(content):
                return content

            # Remember the failure and try the next model
            last_content = content
            last_finish = finish
            last_model = model
            last_error = (
                f"{model} returned garbage "
                f"(finish_reason={finish}, preview={content[:60]!r})"
            )

    # All models exhausted — raise with detail
    if last_content:
        raise RuntimeError(
            f"All Groq models returned garbage. Last: {last_model} "
            f"finish={last_finish} content={last_content[:200]!r}"
        )
    raise RuntimeError(f"Groq request failed: {last_error}")
