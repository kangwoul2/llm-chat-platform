import secrets

from redis.asyncio import Redis


_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class RedisDistributedLock:
    """Minimal educational distributed lock.

    Production systems must additionally reason about lease renewal, fencing tokens,
    clock/partition failures, and whether a DB constraint or idempotency is safer.
    """

    def __init__(self, redis: Redis, key: str, ttl_ms: int = 30_000):
        self.redis = redis
        self.key = key
        self.ttl_ms = ttl_ms
        self.token = secrets.token_urlsafe(16)

    async def acquire(self) -> bool:
        return bool(await self.redis.set(self.key, self.token, nx=True, px=self.ttl_ms))

    async def release(self) -> bool:
        result = await self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
        return result == 1
