from uuid import UUID

from redis.asyncio import Redis

from app.core.errors import ConflictError

_RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class ComposerLockService:
    """Short-lived Valkey ownership containing appeal/staff identifiers only."""

    def __init__(self, valkey: Redis, *, ttl_seconds: int) -> None:
        self._valkey = valkey
        self._ttl = ttl_seconds

    async def acquire(self, appeal_id: UUID, expert_id: UUID) -> int:
        key = self._key(appeal_id)
        owner = str(expert_id)
        acquired = await self._valkey.set(key, owner, ex=self._ttl, nx=True)
        if acquired:
            return self._ttl
        renewed = await self._valkey.eval(_RENEW_SCRIPT, 1, key, owner, self._ttl)
        if not renewed:
            raise ConflictError("Another specialist is currently composing a response.")
        return self._ttl

    async def heartbeat(self, appeal_id: UUID, expert_id: UUID) -> int:
        renewed = await self._valkey.eval(
            _RENEW_SCRIPT,
            1,
            self._key(appeal_id),
            str(expert_id),
            self._ttl,
        )
        if not renewed:
            raise ConflictError("The composer lock is no longer owned by this specialist.")
        return self._ttl

    async def require_owner(self, appeal_id: UUID, expert_id: UUID) -> None:
        """Require and renew ownership immediately before an applicant-facing reply."""

        await self.heartbeat(appeal_id, expert_id)

    async def release(self, appeal_id: UUID, expert_id: UUID) -> None:
        await self._valkey.eval(
            _RELEASE_SCRIPT,
            1,
            self._key(appeal_id),
            str(expert_id),
        )

    @staticmethod
    def _key(appeal_id: UUID) -> str:
        return f"expert:composer:{appeal_id}"
