from redis.asyncio import Redis


def create_valkey_client(valkey_url: str) -> Redis:
    return Redis.from_url(valkey_url, decode_responses=True)
