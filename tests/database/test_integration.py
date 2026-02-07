"""
Integration tests for database operations
"""
import pytest
from datetime import datetime, timezone
import asyncio


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations"""

    @pytest.mark.asyncio
    async def test_connection_to_real_database(self, test_db):
        """Test connection to real database (SQLite in-memory for tests)"""
        from sqlalchemy import text

        result = await test_db.execute(text("SELECT 1"))
        assert result.scalar() == 1, "Database connection failed"

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, test_db):
        """Test that transactions roll back correctly"""
        from app.database.models import User
        from app.auth.security import SecurityService

        security = SecurityService()

        # Start transaction
        async with test_db.begin():
            user = User(
                username="rollback_test",
                email="rollback@example.com",
                hashed_password=security.hash_password("TestPassword123"),
                api_key=None,
                settings={},
                is_admin=False,
                is_active=True
            )
            test_db.add(user)

        # Check if user exists (should not, transaction rolled back)
        from sqlalchemy import select
        result = await test_db.execute(
            select(User).where(User.username == "rollback_test")
        )
        user = result.scalar_one_or_none()

        assert user is None, "Transaction should have been rolled back"

    @pytest.mark.asyncio
    async def test_transaction_commit(self, test_db):
        """Test that transactions commit correctly"""
        from app.database.models import User
        from sqlalchemy import select
        from app.auth.security import SecurityService

        security = SecurityService()

        # Create user within transaction
        user = User(
            username="commit_test",
            email="commit@example.com",
            hashed_password=security.hash_password("TestPassword123"),
            api_key=None,
            settings={},
            is_admin=False,
            is_active=True
        )

        test_db.add(user)
        await test_db.commit()

        # Check if user exists (should, transaction committed)
        result = await test_db.execute(
            select(User).where(User.username == "commit_test")
        )
        user = result.scalar_one()

        assert user is not None, "Transaction should have been committed"
        assert user.username == "commit_test"

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_exception(self, test_db):
        """Test that transactions roll back on exception"""
        from app.database.models import User
        from app.auth.security import SecurityService
        from sqlalchemy import select

        security = SecurityService()

        # Start transaction and raise exception
        try:
            async with test_db.begin():
                user1 = User(
                    username="user1",
                    email="user1@example.com",
                    hashed_password=security.hash_password("TestPassword123"),
                    api_key=None,
                    settings={},
                    is_admin=False,
                    is_active=True
                )
                test_db.add(user1)

                # This should cause rollback
                user2 = User(
                    username="user1",  # Duplicate username
                    email="user2@example.com",
                    hashed_password=security.hash_password("TestPassword123"),
                    api_key=None,
                    settings={},
                    is_admin=False,
                    is_active=True
                )
                test_db.add(user2)
                await test_db.commit()
        except Exception:
            pass  # Expected error

        # Check if any user exists (should not, transaction rolled back)
        result = await test_db.execute(
            select(User).where(User.username == "user1")
        )
        user = result.scalar_one_or_none()

        assert user is None, "Transaction should have been rolled back on exception"


@pytest.mark.integration
class TestConnectionPool:
    """Test connection pool functionality"""

    @pytest.mark.asyncio
    async def test_connection_pool_multiple_connections(self, test_db):
        """Test that connection pool handles multiple concurrent connections"""
        from sqlalchemy import text
        import concurrent.futures

        async def query_database(query_num):
            """Run a query in a separate connection"""
            result = await test_db.execute(text(f"SELECT {query_num}"))
            return result.scalar()

        # Run multiple concurrent queries
        queries = [query_database(i) for i in range(10)]
        results = await asyncio.gather(*queries)

        # All queries should succeed
        assert len(results) == 10, "Not all concurrent queries succeeded"
        assert results == list(range(10)), "Query results don't match expected values"

    @pytest.mark.asyncio
    async def test_connection_pool_stress(self, test_db):
        """Test connection pool under stress"""
        from sqlalchemy import text
        import random

        async def random_query():
            """Run a random query"""
            value = random.randint(1, 1000)
            result = await test_db.execute(text(f"SELECT {value}"))
            return result.scalar()

        # Run many concurrent queries
        queries = [random_query() for _ in range(100)]
        results = await asyncio.gather(*queries)

        # All queries should succeed
        assert len(results) == 100, "Not all stress test queries succeeded"

        # All values should be integers
        assert all(isinstance(r, int) for r in results), "Not all results are integers"


@pytest.mark.integration
class TestConcurrentRequests:
    """Test concurrent database operations"""

    @pytest.mark.asyncio
    async def test_concurrent_inserts(self, test_db):
        """Test concurrent insert operations"""
        from app.database.models import User
        from app.auth.security import SecurityService
        from sqlalchemy import select

        security = SecurityService()

        async def create_user(user_num):
            """Create a user"""
            user = User(
                username=f"concurrent_{user_num}",
                email=f"concurrent_{user_num}@example.com",
                hashed_password=security.hash_password("TestPassword123"),
                api_key=None,
                settings={},
                is_admin=False,
                is_active=True
            )
            test_db.add(user)
            await test_db.flush()
            return user

        # Create 20 users concurrently
        users = await asyncio.gather(*[create_user(i) for i in range(20)])
        await test_db.commit()

        # Verify all users were created
        result = await test_db.execute(
            select(User).where(User.username.like("concurrent_%"))
        )
        created_users = result.scalars().all()

        assert len(created_users) == 20, f"Expected 20 users, got {len(created_users)}"

    @pytest.mark.asyncio
    async def test_concurrent_updates(self, test_db, sample_user):
        """Test concurrent update operations"""
        from sqlalchemy import select

        # Update user multiple times concurrently
        async def update_user(user_num):
            """Update user settings"""
            sample_user.settings[f"update_{user_num}"] = user_num
            test_db.add(sample_user)
            await test_db.flush()

        await asyncio.gather(*[update_user(i) for i in range(10)])
        await test_db.commit()

        # Refresh and check updates
        await test_db.refresh(sample_user)

        # Should have 10 updates
        assert len(sample_user.settings) >= 10, "Not all concurrent updates succeeded"

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self, test_db):
        """Test concurrent read and write operations"""
        from app.database.models import User
        from app.auth.security import SecurityService
        from sqlalchemy import select

        security = SecurityService()

        # Create initial user
        user = User(
            username="read_write_test",
            email="readwrite@example.com",
            hashed_password=security.hash_password("TestPassword123"),
            api_key=None,
            settings={},
            is_admin=False,
            is_active=True
        )
        test_db.add(user)
        await test_db.commit()

        async def read_user():
            """Read user"""
            result = await test_db.execute(
                select(User).where(User.username == "read_write_test")
            )
            return result.scalar_one()

        async def write_user(user_num):
            """Write to user settings"""
            user.settings[f"setting_{user_num}"] = user_num
            test_db.add(user)
            await test_db.flush()

        # Perform concurrent reads and writes
        operations = [read_user()] + [write_user(i) for i in range(10)]
        await asyncio.gather(*operations)
        await test_db.commit()

        # Verify user was updated
        await test_db.refresh(user)
        assert len(user.settings) >= 10, "Not all concurrent writes succeeded"


@pytest.mark.integration
class TestDatabasePerformance:
    """Performance tests for database operations"""

    @pytest.mark.asyncio
    async def test_crud_performance(self, test_db):
        """Test CRUD operations are fast enough"""
        import time

        from app.database.models import User
        from app.auth.security import SecurityService
        from sqlalchemy import select

        security = SecurityService()

        # Test CREATE
        start = time.time()
        user = User(
            username="perf_test",
            email="perf@example.com",
            hashed_password=security.hash_password("TestPassword123"),
            api_key=None,
            settings={},
            is_admin=False,
            is_active=True
        )
        test_db.add(user)
        await test_db.commit()
        create_time = (time.time() - start) * 1000  # Convert to ms

        # Test READ
        start = time.time()
        result = await test_db.execute(
            select(User).where(User.username == "perf_test")
        )
        user = result.scalar_one()
        read_time = (time.time() - start) * 1000

        # Test UPDATE
        start = time.time()
        user.settings = {"updated": True}
        test_db.add(user)
        await test_db.commit()
        update_time = (time.time() - start) * 1000

        # Test DELETE
        start = time.time()
        await test_db.delete(user)
        await test_db.commit()
        delete_time = (time.time() - start) * 1000

        # Check performance (< 50ms for basic CRUD)
        assert create_time < 50, f"CREATE too slow: {create_time:.2f}ms"
        assert read_time < 50, f"READ too slow: {read_time:.2f}ms"
        assert update_time < 50, f"UPDATE too slow: {update_time:.2f}ms"
        assert delete_time < 50, f"DELETE too slow: {delete_time:.2f}ms"

    @pytest.mark.asyncio
    async def test_complex_query_performance(self, test_db, sample_user, sample_task, sample_file):
        """Test complex queries with JOINs are fast enough"""
        import time

        from sqlalchemy import select
        from app.database.models import Task, User, File

        # Complex query with JOINs
        start = time.time()
        result = await test_db.execute(
            select(Task, User)
            .join(User, Task.user_id == User.id)
            .where(Task.user_id == sample_user.id)
        )
        tasks = result.all()
        query_time = (time.time() - start) * 1000

        # Check performance (< 100ms for complex queries with JOIN)
        assert query_time < 100, f"Complex query too slow: {query_time:.2f}ms"
        assert len(tasks) >= 1, "Complex query returned no results"
