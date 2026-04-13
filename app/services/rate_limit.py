"""
Rate limiting: per-user daily/monthly message limits + global circuit breaker.

Uses Redis counters with day/month TTL keys.
"""
from datetime import datetime, timezone, timedelta
from app.db.redis_client import get_redis
from app.core.config import settings


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def check_and_increment_user_limit(user_id: int, daily_limit: int | None = None, monthly_limit: int | None = None) -> tuple[bool, int, str | None]:
    """
    Check if user is under rate limit. If yes, increment counter.
    Returns (allowed, remaining_today, reason_if_denied).
    """
    r = get_redis()
    daily = daily_limit if daily_limit and daily_limit > 0 else settings.USER_DAILY_MESSAGE_LIMIT
    monthly = monthly_limit if monthly_limit and monthly_limit > 0 else settings.USER_MONTHLY_MESSAGE_LIMIT

    day_k = f"ratelimit:user:{user_id}:day:{_today_key()}"
    month_k = f"ratelimit:user:{user_id}:month:{_month_key()}"

    day_count = int(r.get(day_k) or 0)
    month_count = int(r.get(month_k) or 0)

    if day_count >= daily:
        return False, 0, f"Daily message limit reached ({daily}/day). Resets at UTC midnight."
    if month_count >= monthly:
        return False, 0, f"Monthly message limit reached ({monthly}/month)."

    # Increment with TTL
    pipe = r.pipeline()
    pipe.incr(day_k)
    pipe.expire(day_k, 86400 * 2)  # safety margin
    pipe.incr(month_k)
    pipe.expire(month_k, 86400 * 32)
    pipe.execute()

    return True, daily - day_count - 1, None


def get_user_usage_today(user_id: int) -> dict:
    r = get_redis()
    day_k = f"ratelimit:user:{user_id}:day:{_today_key()}"
    month_k = f"ratelimit:user:{user_id}:month:{_month_key()}"
    return {
        "today": int(r.get(day_k) or 0),
        "this_month": int(r.get(month_k) or 0),
        "daily_limit": settings.USER_DAILY_MESSAGE_LIMIT,
        "monthly_limit": settings.USER_MONTHLY_MESSAGE_LIMIT,
    }


# ===== Global circuit breaker =====

def check_global_spend() -> tuple[bool, float, str | None]:
    """
    Returns (allowed, spent_today_usd, reason_if_denied).
    Circuit breaker trips if daily spend exceeds cap.
    """
    r = get_redis()
    key = f"global:spend:day:{_today_key()}"
    spent = float(r.get(key) or 0)
    if spent >= settings.GLOBAL_DAILY_SPEND_CAP_USD:
        return False, spent, f"Global daily spend cap reached (${settings.GLOBAL_DAILY_SPEND_CAP_USD}). Service paused until UTC midnight for cost safety."
    return True, spent, None


def record_spend(usd: float) -> None:
    r = get_redis()
    key = f"global:spend:day:{_today_key()}"
    pipe = r.pipeline()
    pipe.incrbyfloat(key, usd)
    pipe.expire(key, 86400 * 2)
    pipe.execute()


def get_global_usage() -> dict:
    r = get_redis()
    key = f"global:spend:day:{_today_key()}"
    spent = float(r.get(key) or 0)
    return {
        "spent_today_usd": round(spent, 4),
        "daily_cap_usd": settings.GLOBAL_DAILY_SPEND_CAP_USD,
        "remaining_usd": max(0, settings.GLOBAL_DAILY_SPEND_CAP_USD - spent),
        "percent_used": round(spent / settings.GLOBAL_DAILY_SPEND_CAP_USD * 100, 1) if settings.GLOBAL_DAILY_SPEND_CAP_USD > 0 else 0,
    }
