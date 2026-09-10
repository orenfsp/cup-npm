from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.crypto.hmac import rate_limit_digest
from app.core.errors import InfrastructureError, RateLimitError


class LoginRateLimiter:
    """Short-lived Valkey counter using only HMAC-pseudonymized identifiers."""

    def __init__(self, valkey: Redis, settings: Settings) -> None:
        secret = settings.rate_limit_hmac_secret
        if secret is None or not secret.get_secret_value():
            raise InfrastructureError("Login rate limiting is not configured.")
        self._valkey = valkey
        self._secret = secret.get_secret_value()
        self._limit = settings.login_rate_limit_attempts
        self._window = settings.login_rate_limit_window_seconds

    async def check(self, *, transient_ip: str, normalized_login: str) -> None:
        ip_digest = rate_limit_digest(self._secret, transient_ip).hex()
        login_digest = rate_limit_digest(self._secret, normalized_login).hex()
        keys = (f"auth:login:ip:{ip_digest}", f"auth:login:account:{login_digest}")
        pipeline = self._valkey.pipeline(transaction=True)
        for key in keys:
            pipeline.incr(key)
            pipeline.expire(key, self._window, nx=True)
        try:
            results = await pipeline.execute()
        except RedisError as exc:
            raise InfrastructureError("Login rate limiting is unavailable.") from exc
        attempts = (int(results[0]), int(results[2]))
        if any(count > self._limit for count in attempts):
            raise RateLimitError(
                "Too many login attempts. Try again later.",
                headers={"Retry-After": str(self._window)},
            )
