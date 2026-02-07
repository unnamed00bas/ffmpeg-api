"""
Integration tests for Redis
"""
import pytest
import asyncio
from redis.asyncio import Redis


@pytest.mark.integration
class TestRedisIntegration:
    """Integration tests for Redis"""

    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing"""
        client = Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True
        )

        # Test connection
        await client.ping()

        yield client

        # Cleanup
        await client.close()

    @pytest.mark.asyncio
    async def test_connection(self, redis_client):
        """Test Redis connection"""
        result = await redis_client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_client):
        """Test setting and getting values"""
        await redis_client.set("test_key", "test_value")
        value = await redis_client.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_expiration(self, redis_client):
        """Test setting values with expiration"""
        await redis_client.setex("expire_key", 2, "expire_value")

        # Value should exist
        value = await redis_client.get("expire_key")
        assert value == "expire_value"

        # Wait for expiration
        await asyncio.sleep(3)

        # Value should be gone
        value = await redis_client.get("expire_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self, redis_client):
        """Test deleting keys"""
        await redis_client.set("delete_key", "delete_value")
        await redis_client.delete("delete_key")

        value = await redis_client.get("delete_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_exists(self, redis_client):
        """Test checking if key exists"""
        await redis_client.set("exists_key", "exists_value")

        exists = await redis_client.exists("exists_key")
        assert exists == 1

        not_exists = await redis_client.exists("not_exists_key")
        assert not_exists == 0

    @pytest.mark.asyncio
    async def test_increment(self, redis_client):
        """Test incrementing values"""
        await redis_client.set("counter", "0")

        result = await redis_client.incr("counter")
        assert result == 1

        result = await redis_client.incr("counter")
        assert result == 2

    @pytest.mark.asyncio
    async def test_decrement(self, redis_client):
        """Test decrementing values"""
        await redis_client.set("counter", "5")

        result = await redis_client.decr("counter")
        assert result == 4

    @pytest.mark.asyncio
    async def test_list_operations(self, redis_client):
        """Test list operations"""
        await redis_client.delete("test_list")

        # Push elements
        await redis_client.lpush("test_list", "value3")
        await redis_client.lpush("test_list", "value2")
        await redis_client.lpush("test_list", "value1")

        # Get length
        length = await redis_client.llen("test_list")
        assert length == 3

        # Get range
        values = await redis_client.lrange("test_list", 0, -1)
        assert values == ["value1", "value2", "value3"]

    @pytest.mark.asyncio
    async def test_set_operations(self, redis_client):
        """Test set operations"""
        await redis_client.delete("test_set")

        # Add members
        await redis_client.sadd("test_set", "member1")
        await redis_client.sadd("test_set", "member2")
        await redis_client.sadd("test_set", "member3")

        # Get size
        size = await redis_client.scard("test_set")
        assert size == 3

        # Check membership
        is_member = await redis_client.sismember("test_set", "member2")
        assert is_member is True

        not_member = await redis_client.sismember("test_set", "member999")
        assert not_member is False

    @pytest.mark.asyncio
    async def test_hash_operations(self, redis_client):
        """Test hash operations"""
        await redis_client.delete("test_hash")

        # Set hash fields
        await redis_client.hset("test_hash", "field1", "value1")
        await redis_client.hset("test_hash", "field2", "value2")

        # Get hash fields
        all_fields = await redis_client.hgetall("test_hash")
        assert all_fields["field1"] == "value1"
        assert all_fields["field2"] == "value2"

        # Get specific field
        value = await redis_client.hget("test_hash", "field1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_json_operations(self, redis_client):
        """Test JSON operations"""
        import json

        test_data = {"key": "value", "number": 123, "nested": {"field": "data"}}
        await redis_client.set("json_key", json.dumps(test_data))

        # Get and parse
        value = await redis_client.get("json_key")
        parsed = json.loads(value)

        assert parsed["key"] == "value"
        assert parsed["number"] == 123
        assert parsed["nested"]["field"] == "data"

    @pytest.mark.asyncio
    async def test_flushdb(self, redis_client):
        """Test flushing database"""
        # Add some data
        await redis_client.set("key1", "value1")
        await redis_client.set("key2", "value2")

        # Flush
        await redis_client.flushdb()

        # Check all keys are gone
        keys = await redis_client.keys("*")
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_pipeline(self, redis_client):
        """Test pipeline operations"""
        async with redis_client.pipeline() as pipe:
            await pipe.set("pipe_key1", "value1")
            await pipe.set("pipe_key2", "value2")
            await pipe.set("pipe_key3", "value3")
            results = await pipe.execute()

        assert all(result is True for result in results)

        # Verify values
        assert await redis_client.get("pipe_key1") == "value1"
        assert await redis_client.get("pipe_key2") == "value2"
        assert await redis_client.get("pipe_key3") == "value3"
