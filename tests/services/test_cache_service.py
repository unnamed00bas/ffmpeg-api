"""
Тесты кэш-сервиса (Redis): CacheService, VideoMetadataCache, OperationResultCache.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.cache.cache_service import CacheService, VideoMetadataCache, OperationResultCache


@pytest.fixture
def mock_redis():
    """Мок Redis."""
    redis = MagicMock()
    redis.get.return_value = None
    return redis


@pytest.fixture
def cache_service(mock_redis):
    """Экземпляр CacheService с мокнутым Redis."""
    with patch("app.cache.cache_service.Redis.from_url", return_value=mock_redis):
        return CacheService()


class TestCacheService:
    """Unit тесты CacheService."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_key_missing(self, cache_service, mock_redis):
        """get возвращает None для несуществующего ключа."""
        mock_redis.get.return_value = None
        result = await cache_service.get("missing_key")
        assert result is None
        mock_redis.get.assert_called_once_with("missing_key")

    @pytest.mark.asyncio
    async def test_get_deserializes_json(self, cache_service, mock_redis):
        """get десериализует JSON."""
        mock_redis.get.return_value = b'{"value": 123}'
        result = await cache_service.get("key")
        assert result == {"value": 123}

    @pytest.mark.asyncio
    async def test_set_serializes_and_stores_with_ttl(self, cache_service, mock_redis):
        """set сериализует и сохраняет с TTL."""
        mock_redis.setex.return_value = None
        await cache_service.set("key", {"data": "test"}, ttl=3600)
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == "key"
        assert b'{"data": "test"}' in call_args[2]

    @pytest.mark.asyncio
    async def test_set_uses_default_ttl_if_not_provided(self, cache_service, mock_redis):
        """set использует default TTL."""
        mock_redis.setex.return_value = None
        await cache_service.set("key", "value")
        args = mock_redis.setex.call_args[0]
        assert args[1] == cache_service.default_ttl

    @pytest.mark.asyncio
    async def test_delete_calls_redis_delete(self, cache_service, mock_redis):
        """delete вызывает Redis.delete."""
        await cache_service.delete("key")
        mock_redis.delete.assert_called_once_with("key")

    @pytest.mark.asyncio
    async def test_clear_calls_flushdb(self, cache_service, mock_redis):
        """clear вызывает flushdb."""
        await cache_service.clear()
        mock_redis.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_returns_bool(self, cache_service, mock_redis):
        """exists возвращает True/False."""
        mock_redis.exists.return_value = 1
        assert await cache_service.exists("key")
        mock_redis.exists.return_value = 0
        assert not await cache_service.exists("key")

    @pytest.mark.unit
    def test_generate_key_deterministic(self):
        """generate_key возвращает детерминированный результат."""
        key1 = CacheService.generate_key("test", a=1, b="x")
        key2 = CacheService.generate_key("test", b="x", a=1)
        assert key1 == key2
        assert key1.startswith("test:")

    @pytest.mark.unit
    def test_generate_key_different_for_different_params(self):
        """generate_key возвращает разные ключи для разных параметров."""
        key1 = CacheService.generate_key("test", a=1)
        key2 = CacheService.generate_key("test", a=2)
        assert key1 != key2


class TestVideoMetadataCache:
    """Unit тесты VideoMetadataCache."""

    @pytest.fixture
    def metadata_cache(self, cache_service):
        return VideoMetadataCache(cache_service)

    @pytest.mark.asyncio
    async def test_get_video_info_calls_cache(self, metadata_cache, cache_service):
        """get_video_info обращается к CacheService с правильным ключом."""
        await metadata_cache.get_video_info(5, "/path/to/file.mp4")
        cache_service.get.assert_called_once()
        key = cache_service.get.call_args[0][0]
        assert "video:info:5:" in key

    @pytest.mark.asyncio
    async def test_set_video_info_uses_ttl(self, metadata_cache, cache_service):
        """set_video_info сохраняет с TTL."""
        await metadata_cache.set_video_info(1, "/path", {"duration": 10.5})
        cache_service.set.assert_called_once()
        ttl = cache_service.set.call_args[0][2]
        assert ttl == metadata_cache.ttl

    @pytest.mark.asyncio
    async def test_invalidate_deletes_key(self, metadata_cache, cache_service):
        """invalidate вызывает delete."""
        await metadata_cache.invalidate(3, "/path")
        cache_service.delete.assert_called_once()


class TestOperationResultCache:
    """Unit тесты OperationResultCache."""

    @pytest.fixture
    def result_cache(self, cache_service):
        return OperationResultCache(cache_service)

    @pytest.mark.asyncio
    async def test_get_result_calls_cache_with_correct_key(self, result_cache, cache_service):
        """get_result формирует ключ по типу, file_ids, config."""
        await result_cache.get_result("join", [1, 2], {"preset": "fast"})
        cache_service.get.assert_called_once()
        key = cache_service.get.call_args[0][0]
        assert "operation:result:" in key
        assert "type=join" in key
        assert "files=1,2" in key

    @pytest.mark.asyncio
    async def test_set_result_uses_ttl(self, result_cache, cache_service):
        """set_result сохраняет с TTL."""
        await result_cache.set_result("overlay", [3], {}, {"output": "test.mp4"})
        cache_service.set.assert_called_once()
        ttl = cache_service.set.call_args[0][2]
        assert ttl == result_cache.ttl

    @pytest.mark.asyncio
    async def test_set_result_sorts_file_ids_for_determinism(self, result_cache, cache_service):
        """set_result сортирует file_ids для детерминизма ключа."""
        await result_cache.set_result("type", [2, 1, 3], {}, {})
        key = cache_service.set.call_args[0][0]
        assert "files=1,2,3" in key  # отсортировано
