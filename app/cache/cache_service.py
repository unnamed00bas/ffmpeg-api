"""
Redis-backed cache service and specialized caches for metadata and operation results.
"""
import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from redis import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


class CacheService:
    """Сервис кэширования на Redis (sync Redis, вызовы в executor)."""

    def __init__(self) -> None:
        self._redis = Redis.from_url(_settings.REDIS_URL)
        self.default_ttl = 3600  # 1 hour

    def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return asyncio.get_event_loop().run_in_executor(
            None, lambda: fn(*args, **kwargs)
        )

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша."""
        try:
            value = await self._run(self._redis.get, key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("Cache get error key=%s: %s", key, e)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Установка значения в кэш."""
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value)
            await self._run(self._redis.setex, key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning("Cache set error key=%s: %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        """Удаление значения из кэша."""
        try:
            await self._run(self._redis.delete, key)
            return True
        except Exception as e:
            logger.warning("Cache delete error key=%s: %s", key, e)
            return False

    async def clear(self) -> bool:
        """Очистка текущей БД Redis."""
        try:
            await self._run(self._redis.flushdb)
            return True
        except Exception as e:
            logger.warning("Cache clear error: %s", e)
            return False

    async def exists(self, key: str) -> bool:
        """Проверка существования ключа."""
        try:
            n = await self._run(self._redis.exists, key)
            return bool(n)
        except Exception as e:
            logger.warning("Cache exists error key=%s: %s", key, e)
            return False

    @staticmethod
    def generate_key(prefix: str, **kwargs: Any) -> str:
        """Детерминированный ключ по префиксу и параметрам."""
        params = sorted(kwargs.items())
        params_str = "&".join(f"{k}={v}" for k, v in params)
        hash_str = hashlib.md5(params_str.encode()).hexdigest()
        return f"{prefix}:{hash_str}"


class VideoMetadataCache:
    """Кэш метаданных видео (ffprobe)."""

    def __init__(self, cache_service: CacheService) -> None:
        self.cache = cache_service
        self.ttl = 86400  # 24 hours

    def _key(self, file_id: int, file_path: str) -> str:
        path_hash = hashlib.md5(file_path.encode()).hexdigest()
        return f"video:info:{file_id}:{path_hash}"

    async def get_video_info(
        self,
        file_id: int,
        file_path: str,
    ) -> Optional[Dict[str, Any]]:
        """Получение метаданных видео из кэша."""
        key = self._key(file_id, file_path)
        return await self.cache.get(key)

    async def set_video_info(
        self,
        file_id: int,
        file_path: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """Сохранение метаданных в кэш."""
        key = self._key(file_id, file_path)
        return await self.cache.set(key, metadata, self.ttl)

    async def invalidate(self, file_id: int, file_path: str) -> bool:
        """Инвалидация кэша для файла."""
        key = self._key(file_id, file_path)
        return await self.cache.delete(key)


class OperationResultCache:
    """Кэш результатов операций (например, join)."""

    def __init__(self, cache_service: CacheService) -> None:
        self.cache = cache_service
        self.ttl = 604800  # 7 days

    def _key(
        self,
        operation_type: str,
        input_file_ids: List[int],
        config: Dict[str, Any],
    ) -> str:
        return CacheService.generate_key(
            "operation:result",
            type=operation_type,
            files=",".join(str(f) for f in sorted(input_file_ids)),
            config=json.dumps(config, sort_keys=True),
        )

    async def get_result(
        self,
        operation_type: str,
        input_file_ids: List[int],
        config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Получение результата операции из кэша."""
        key = self._key(operation_type, input_file_ids, config)
        return await self.cache.get(key)

    async def set_result(
        self,
        operation_type: str,
        input_file_ids: List[int],
        config: Dict[str, Any],
        result: Dict[str, Any],
    ) -> bool:
        """Сохранение результата в кэш."""
        key = self._key(operation_type, input_file_ids, config)
        return await self.cache.set(key, result, self.ttl)
