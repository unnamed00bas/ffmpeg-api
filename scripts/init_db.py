"""
Database initialization script

This script creates the initial database schema and default data.
Run this script to set up the database for the first time.
"""
import asyncio
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database.connection import get_db_sync, engine
from app.database.models import User, Task, File, OperationLog, Metrics, BaseModel
from app.database.repositories.user_repository import UserRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_tables():
    """
    Create all database tables
    
    This function creates all tables based on the SQLAlchemy models.
    In production, you should use Alembic migrations instead.
    """
    logger.info("Creating database tables...")
    
    try:
        # Create sync engine for initialization
        sync_url = settings.database_url.replace("+asyncpg", "")
        sync_engine = create_engine(sync_url, echo=settings.DEBUG)
        
        # Create all tables
        BaseModel.metadata.create_all(sync_engine)
        
        sync_engine.dispose()
        logger.info("Database tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


def create_admin_user(session):
    """
    Create default admin user
    
    Args:
        session: Database session
        
    Returns:
        Created User instance or None if already exists
    """
    logger.info("Creating admin user...")
    
    try:
        user_repo = UserRepository(session)
        
        # Check if admin user already exists
        existing_admin = await user_repo.get_by_email("admin@example.com")
        if existing_admin:
            logger.info("Admin user already exists. Skipping creation.")
            return existing_admin
        
        # Create admin user
        admin_user = await user_repo.create(
            username="admin",
            email="admin@example.com",
            password="admin123",
            is_admin=True,
            is_active=True
        )
        
        # Generate API key for admin
        await user_repo.generate_api_key(admin_user.id)
        
        logger.info(f"Admin user created successfully! Email: admin@example.com, Password: admin123")
        logger.info(f"Admin API Key: {admin_user.api_key}")
        
        return admin_user
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        return None


def create_test_data(session):
    """
    Create optional test data for development
    
    Args:
        session: Database session
    """
    logger.info("Creating test data...")
    
    try:
        user_repo = UserRepository(session)
        
        # Create test regular user
        test_user = await user_repo.create(
            username="testuser",
            email="test@example.com",
            password="test123",
            is_admin=False,
            is_active=True
        )
        await user_repo.generate_api_key(test_user.id)
        logger.info(f"Test user created: {test_user.email}")
        
        logger.info("Test data created successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to create test data: {e}")
        return False


async def async_create_admin_user(session):
    """
    Async version of create_admin_user
    
    Args:
        session: Database session
    """
    logger.info("Creating admin user...")
    
    try:
        user_repo = UserRepository(session)
        
        # Check if admin user already exists
        existing_admin = await user_repo.get_by_email("admin@example.com")
        if existing_admin:
            logger.info("Admin user already exists. Skipping creation.")
            return existing_admin
        
        # Create admin user
        admin_user = await user_repo.create(
            username="admin",
            email="admin@example.com",
            password="admin123",
            is_admin=True,
            is_active=True
        )
        
        # Generate API key for admin
        await user_repo.generate_api_key(admin_user.id)
        
        logger.info(f"Admin user created successfully!")
        logger.info(f"Email: admin@example.com")
        logger.info(f"Password: admin123")
        logger.info(f"API Key: {admin_user.api_key}")
        
        return admin_user
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        return None


async def init_database():
    """
    Initialize the database with tables and default data
    """
    logger.info("Starting database initialization...")
    logger.info(f"Database URL: {settings.database_url}")
    
    # Create tables
    if not create_tables():
        logger.error("Failed to create database tables. Aborting initialization.")
        return False
    
    # Create admin user using async
    async with engine.begin() as conn:
        from app.database.connection import async_session_maker
        async with async_session_maker() as session:
            try:
                admin_user = await async_create_admin_user(session)
                if not admin_user:
                    logger.warning("Failed to create admin user")
                else:
                    logger.info("Admin user created/verified successfully")
            except Exception as e:
                logger.error(f"Error during admin user creation: {e}")
    
    logger.info("Database initialization completed successfully!")
    return True


def main():
    """
    Main entry point for database initialization
    """
    print("=" * 60)
    print("FFmpeg API - Database Initialization")
    print("=" * 60)
    print()
    
    # Run async initialization
    try:
        success = asyncio.run(init_database())
        
        if success:
            print()
            print("=" * 60)
            print("SUCCESS: Database initialized successfully!")
            print("=" * 60)
            print()
            print("Default credentials:")
            print("  Email:    admin@example.com")
            print("  Password: admin123")
            print()
            print("Next steps:")
            print("  1. Start the application: uvicorn app.main:app --reload")
            print("  2. Access the API: http://localhost:8000")
            print("  3. View API docs: http://localhost:8000/docs")
            print()
        else:
            print()
            print("=" * 60)
            print("FAILED: Database initialization failed!")
            print("=" * 60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nInitialization cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error during initialization: {e}", exc_info=True)
        print()
        print("=" * 60)
        print(f"ERROR: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
