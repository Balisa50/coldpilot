"""
Groq API client for LLaMA 3 email generation.
Free tier: generous rate limits. We fall back across a few models because
llama-3.3-70b-versatile has been flaky lately (returning truncated/garbage
responses like '8\\ufffd'' with finish_reason=length on short outputs).

Strategy: try the most reliable model first (8b-instant), fall back to
alternatives only if it fails. This avoids burning 8b-instant's RPM
budget on retries when 70b returns garbage.
"""
from __future__ import annotations

import asyncio
import os
import re

import httpx

GROQ_BASE = "https://api.groq.com/openai/v1"

# Ordered by reliability: 8b is rock-solid, gemma is a solid alt,
# 70b gives nicer prose but has been returning corrupt output lately.
MODELS = [
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "llama-3.3-70b-versatile",
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


class GroqRateLimitError(RuntimeError):
    """Raised on 429 responses. Carries the retry-after hint in seconds."""
    def __init__(self, message: str, retry_after: float):
        super().__init__(message)
        self.retry_after = retry_after


def _extract_retry_after(err_msg: str, header_val: str | None) -> float:
    """Pull retry delay from Retry-After header or 'try again in 1.234s' text."""
    if header_val:
        try:
            return max(0.0, float(header_val))
        except ValueError:
            pass
    # Groq's error body often says "Please try again in 1.234s"
    m = re.search(r"try again in ([\d.]+)s", err_msg, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 0.0


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
        if resp.status_code == 429:
            retry_after = _extract_retry_after(
                err_msg, resp.headers.get("Retry-After")
            )
            raise GroqRateLimitError(
                f"Groq API 429 ({model}): {err_msg}", retry_after
            )
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

    Tries multiple models in order. Rejects garbage responses (truncated/
    corrupt) and waits out rate limits briefly before moving to the next
    model. Each model gets at most one rate-limit retry to avoid chains
    burning the whole quota.
    """
    last_error = ""
    last_content = ""
    last_finish = ""
    last_model = ""

    async with httpx.AsyncClient(timeout=60) as client:
        for model in MODELS:
            # Each model gets up to 2 attempts: one fresh, one after a
            # short wait if we get 429.
            for attempt in (1, 2):
                try:
                    content, finish, _data = await _call_once(
                        client, model, system, user, temperature, max_tokens
                    )
                except GroqRateLimitError as exc:
                    last_error = str(exc)[:300]
                    last_model = model
                    if attempt == 1 and exc.retry_after > 0 and exc.retry_after <= 5:
                        # Short wait — retry same model once
                        await asyncio.sleep(exc.retry_after + 0.2)
                        continue
                    # Long wait or second failure — move to next model
                    break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                    last_model = model
                    break  # non-429 error — try next model

                if not _looks_like_garbage(content):
                    return content

                # Remember garbage response and try the next model (no retry)
                last_content = content
                last_finish = finish
                last_model = model
                last_error = (
                    f"{model} returned garbage "
                    f"(finish_reason={finish}, preview={content[:60]!r})"
                )
                break  # don't retry same model on garbage — try next

    # All models exhausted — raise with detail
    if last_content:
        raise RuntimeError(
            f"All Groq models returned garbage. Last: {last_model} "
            f"finish={last_finish} content={last_content[:200]!r}"
        )
    raise RuntimeError(f"Groq request failed after trying all models: {last_error}")
