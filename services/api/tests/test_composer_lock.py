from uuid import uuid4

import pytest

from app.core.errors import ConflictError
from app.modules.expert.composer_lock import ComposerLockService


class FakeValkey:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key, value, *, ex, nx):
        assert ex > 0 and nx
        if key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script, _keys, key, owner, *args):
        if self.values.get(key) != owner:
            return 0
        if "expire" in script:
            assert args[0] > 0
            return 1
        del self.values[key]
        return 1


async def test_composer_lock_acquire_block_heartbeat_and_release() -> None:
    valkey = FakeValkey()
    service = ComposerLockService(valkey, ttl_seconds=30)  # type: ignore[arg-type]
    appeal_id = uuid4()
    first = uuid4()
    second = uuid4()

    assert await service.acquire(appeal_id, first) == 30
    with pytest.raises(ConflictError):
        await service.acquire(appeal_id, second)
    assert await service.heartbeat(appeal_id, first) == 30
    with pytest.raises(ConflictError):
        await service.heartbeat(appeal_id, second)
    await service.release(appeal_id, second)
    with pytest.raises(ConflictError):
        await service.acquire(appeal_id, second)
    await service.release(appeal_id, first)
    assert await service.acquire(appeal_id, second) == 30


async def test_expired_composer_lock_can_be_reacquired() -> None:
    valkey = FakeValkey()
    service = ComposerLockService(valkey, ttl_seconds=30)  # type: ignore[arg-type]
    appeal_id = uuid4()
    first = uuid4()
    second = uuid4()
    await service.acquire(appeal_id, first)

    valkey.values.clear()  # models Valkey TTL expiry

    assert await service.acquire(appeal_id, second) == 30
    assert all("body" not in value and "message" not in value for value in valkey.values.values())
