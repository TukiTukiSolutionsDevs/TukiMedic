from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


# ---------------------------------------------------------------------------
# Subscription tier gating (hard blocker #1, matrix decided 2026-05-01).
#
# Naming note: do NOT call this `require_tier` — the name `tier` is already
# overloaded for LLM provider tiers (PROVIDER_MODELS fast/smart). Using
# `require_subscription_tier` keeps the two domains distinct in code review
# and grep results.
# ---------------------------------------------------------------------------

TIER_RANK: dict[str, int] = {"free": 0, "paid": 1}


def require_subscription_tier(min_tier: str):
    """FastAPI dependency factory that enforces a minimum subscription tier.

    Returns a dependency that resolves the current user via `get_current_user`
    and raises HTTP 403 with a stable machine-readable detail when the user's
    `subscription_tier` ranks below `min_tier`.

    Detail shape (frontend contract):
        {"code": "tier_required",
         "required_tier": <str>,
         "current_tier": <str>}

    Unknown tier strings (legacy values, manual DB edits) are treated as
    rank 0 — they NEVER silently pass a higher gate.
    """
    if min_tier not in TIER_RANK:
        raise ValueError(
            f"require_subscription_tier: unknown min_tier {min_tier!r}; "
            f"allowed: {sorted(TIER_RANK)}"
        )
    required_rank = TIER_RANK[min_tier]

    async def _dep(user: User = Depends(get_current_user)) -> User:
        current_tier = getattr(user, "subscription_tier", "free") or "free"
        current_rank = TIER_RANK.get(current_tier, 0)
        if current_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "tier_required",
                    "required_tier": min_tier,
                    "current_tier": current_tier,
                },
            )
        return user

    return _dep
