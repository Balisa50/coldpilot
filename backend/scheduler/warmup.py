"""
Daily send limit warm-up. Starts conservative and ramps up over 3 weeks
to protect the sender's email reputation.
"""
from __future__ import annotations

from datetime import date

from backend import db


# Warm-up schedule: days_active -> max_sends_per_day
WARMUP_TIERS = [
    (3, 5),      # Day 1-3:   5 emails/day
    (7, 10),     # Day 4-7:   10 emails/day
    (14, 20),    # Day 8-14:  20 emails/day
    (21, 35),    # Day 15-21: 35 emails/day
]
MAX_DAILY = 50   # Day 22+:  50 emails/day (cap)


def calculate_daily_limit(first_send_date: date | None, today: date | None = None) -> int:
    """Calculate today's send limit based on warm-up schedule."""
    today = today or date.today()
    if first_send_date is None:
        return WARMUP_TIERS[0][1]  # First day: 5

    days_active = (today - first_send_date).days
    for threshold, limit in WARMUP_TIERS:
        if days_active < threshold:
            return limit
    return MAX_DAILY


async def update_daily_limit() -> int:
    """Calculate and set today's limit based on send history."""
    d = await db.get_db()
    try:
        rows = await d.execute_fetchall(
            "SELECT MIN(date) as first_date FROM daily_send_log WHERE count > 0"
        )
        first_date_str = rows[0]["first_date"] if rows else None
        first_date = date.fromisoformat(first_date_str) if first_date_str else None
    finally:
        await d.close()

    limit = calculate_daily_limit(first_date)
    await db.set_daily_limit(limit)
    return limit
