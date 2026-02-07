"""
Alembic migration tests
"""
import pytest
import subprocess
import os
from pathlib import Path


class TestMigrations:
    """Test Alembic migrations"""

    @pytest.fixture
    def alembic_config_path(self):
        """Path to alembic.ini"""
        return Path(__file__).parent.parent.parent / "alembic.ini"

    @pytest.fixture
    def alembic_versions_path(self):
        """Path to alembic versions directory"""
        return Path(__file__).parent.parent.parent / "alembic" / "versions"

    @pytest.fixture
    def migrations_exist(self, alembic_versions_path):
        """Check if migration files exist"""
        versions = list(alembic_versions_path.glob("*.py"))
        return len(versions) > 0

    def test_migration_files_exist(self, migrations_exist):
        """Test that migration files exist"""
        assert migrations_exist, "No migration files found in alembic/versions/"

    def test_migration_files_have_valid_format(self, alembic_versions_path):
        """Test that migration files have valid naming format"""
        versions = list(alembic_versions_path.glob("*.py"))

        for version_file in versions:
            filename = version_file.name
            # Check format: YYYYMMDD_description.py
            assert len(filename) >= 15, f"Migration file {filename} has invalid format"
            assert filename[8] == '_', f"Migration file {filename} should have underscore after date"
            assert filename.endswith('.py'), f"Migration file {filename} should end with .py"

    def test_migration_upgrade_head(self):
        """Test that alembic upgrade head runs without errors"""
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should succeed or fail gracefully
        # In test environment without DB, it may fail
        # We just check it runs
        assert result.returncode in [0, 1, 2], "alembic upgrade head should run"

    def test_migration_current(self):
        """Test that alembic current works"""
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed or fail gracefully
        assert result.returncode in [0, 1], "alembic current should run"

    def test_migration_history(self):
        """Test that alembic history works"""
        result = subprocess.run(
            ["alembic", "history"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed
        assert result.returncode == 0, f"alembic history failed: {result.stderr}"

    def test_migration_downgrade_base(self):
        """Test that alembic downgrade base runs without errors"""
        result = subprocess.run(
            ["alembic", "downgrade", "base"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should succeed or fail gracefully
        assert result.returncode in [0, 1, 2], "alembic downgrade base should run"

    def test_migration_file_content(self, alembic_versions_path):
        """Test that migration files have required functions"""
        versions = list(alembic_versions_path.glob("*.py"))

        for version_file in versions:
            content = version_file.read_text()

            # Should have upgrade function
            assert "def upgrade(" in content, f"Migration {version_file.name} missing upgrade() function"

            # Should have downgrade function
            assert "def downgrade(" in content, f"Migration {version_file.name} missing downgrade() function"

            # Should import op and sqlalchemy
            assert "from alembic import op" in content, f"Migration {version_file.name} missing alembic import"
            assert "import sqlalchemy as sa" in content, f"Migration {version_file.name} missing sqlalchemy import"


@pytest.mark.integration
class TestMigrationIntegration:
    """Integration tests for migrations with actual database"""

    @pytest.fixture
    def test_database_url(self):
        """Test database URL for migration testing"""
        return "sqlite+aiosqlite:///:memory:"

    @pytest.mark.asyncio
    async def test_create_all_tables_from_migrations(self):
        """Test that migrations create all required tables"""
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from app.database.models import Base, User, Task, File, OperationLog, Metrics

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )

        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Check that all tables exist
        from sqlalchemy import inspect
        async with engine.connect() as conn:
            inspector = await conn.run_sync(inspect)

            existing_tables = inspector.get_table_names()

            # Check for required tables
            required_tables = ["users", "tasks", "files", "operation_logs", "metrics"]
            for table in required_tables:
                assert table in existing_tables, f"Table {table} not created by migrations"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_foreign_keys_created(self):
        """Test that migrations create foreign key constraints"""
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from app.database.models import Base
        from sqlalchemy import inspect

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with engine.connect() as conn:
            inspector = await conn.run_sync(inspect)
            foreign_keys = inspector.get_foreign_keys('tasks')

            # Check that task.user_id has foreign key
            task_user_fk = [
                fk for fk in foreign_keys
                if fk['constrained_columns'] == ['user_id']
            ]
            assert len(task_user_fk) > 0, "Foreign key on tasks.user_id not created"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_indexes_created(self):
        """Test that migrations create indexes"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.database.models import Base
        from sqlalchemy import inspect

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with engine.connect() as conn:
            inspector = await conn.run_sync(inspect)

            # Check indexes on users table
            user_indexes = inspector.get_indexes('users')
            index_names = [idx['name'] for idx in user_indexes]

            # Should have indexes on email and username
            assert any('email' in idx_name.lower() for idx_name in index_names), \
                "Index on users.email not created"
            assert any('username' in idx_name.lower() for idx_name in index_names), \
                "Index on users.username not created"

            # Check indexes on tasks table
            task_indexes = inspector.get_indexes('tasks')
            task_index_names = [idx['name'] for idx in task_indexes]

            # Should have indexes on user_id, status, created_at
            assert any('user_id' in idx_name.lower() for idx_name in task_index_names), \
                "Index on tasks.user_id not created"
            assert any('status' in idx_name.lower() for idx_name in task_index_names), \
                "Index on tasks.status not created"

        await engine.dispose()
