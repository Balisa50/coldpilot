"""Extract the calling user's id from a Supabase-issued JWT."""
from __future__ import annotations
from fastapi import Header, HTTPException
import jwt as _jwt


async def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency — returns the authenticated user's Supabase UUID."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = _jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["HS256", "RS256"],
        )
        uid: str = payload.get("sub", "")
        if not uid:
            raise ValueError("Missing sub claim")
        return uid
    except Exception as exc:
        raise HTTPException(401, f"Invalid token: {exc}")
