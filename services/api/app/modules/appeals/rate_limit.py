from typing import Literal

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.crypto.hmac import rate_limit_digest
from app.core.errors import InfrastructureError, RateLimitError

RateLimitKind = Literal["track-access", "submission"]


class PublicAppealRateLimiter:
    """Expiring Valkey counters containing only HMAC-pseudonymized network keys."""

    def __init__(self, valkey: Redis, settings: Settings) -> None:
        secret = settings.rate_limit_hmac_secret
        if secret is None or not secret.get_secret_value():
            raise InfrastructureError("Public appeal rate limiting is not configured.")
        self._valkey = valkey
        self._secret = secret.get_secret_value()
        self._policies = {
            "track-access": (
                settings.track_access_rate_limit_attempts,
                settings.track_access_rate_limit_window_seconds,
            ),
            "submission": (
                settings.appeal_submission_rate_limit_attempts,
                settings.appeal_submission_rate_limit_window_seconds,
            ),
        }

    async def check(self, kind: RateLimitKind, *, transient_ip: str) -> None:
        limit, window = self._policies[kind]
        network_digest = rate_limit_digest(self._secret, transient_ip).hex()
        key = f"public:{kind}:network:{network_digest}"
        pipeline = self._valkey.pipeline(transaction=True)
        pipeline.incr(key)
        pipeline.expire(key, window, nx=True)
        try:
            results = await pipeline.execute()
        except RedisError as exc:
            raise InfrastructureError("Public appeal rate limiting is unavailable.") from exc
        if int(results[0]) > limit:
            raise RateLimitError(
                "Too many attempts. Please try again later.",
                headers={"Retry-After": str(window)},
            )
