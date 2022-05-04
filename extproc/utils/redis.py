from datetime import timedelta as td
from logging import getLogger
from os import environ
from typing import Optional

from redis import Redis

logger = getLogger(__name__)

"""
Wrappers for redis commands.

The format followed is _<redis-command>
"""

REDIS_CACHE_HOST = environ.get("REDIS_CACHE_HOST", "redis")
REDIS_CACHE_PORT = int(environ.get("REDIS_CACHE_PORT", "6379"))
REDIS_CACHE_URL = (f"redis://{REDIS_CACHE_HOST}:{REDIS_CACHE_PORT}",)


class RedisCache:
    def __init__(self):
        self.client = Redis(REDIS_CACHE_HOST, REDIS_CACHE_PORT, db=0, decode_responses=True)

    def setex(self, key: str, value: str = "", expiry: td = td(hours=24)) -> bool:
        try:
            self.client.setex(key, expiry, value)
            return True

        except Exception as e:
            logger.error(f"RedisCacheError: setex failed with {e}")
            return False

    def exists(self, key: str) -> bool:
        try:
            return self.client.exists(key) == 1

        except Exception as e:
            logger.error(f"RedisCacheError: exists failed with {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        try:
            return self.client.get(key)

        except Exception as e:
            logger.error(f"RedisCacheError: get failed with {e}")
            return None

    def set(self, key: str, value: str) -> bool:
        try:
            return self.client.set(key) == 1

        except Exception as e:
            logger.error(f"RedisCacheError: set failed with {e}")
            return False

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)

        except Exception as e:
            logger.error(f"RedisCacheError: delete failed with {e}")
