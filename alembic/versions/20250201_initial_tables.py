"""Initial database tables creation

Revision ID: 20250201_initial
Revises: 
Create Date: 2025-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20250201_initial"
down_revision = None
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists in the database"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(index_name):
    """Check if an index exists in the database"""
    bind = op.get_bind()
    # Query pg_indexes to check if index exists
    result = bind.execute(sa.text(
        f"SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}'"
    ))
    return result.fetchone() is not None


def type_exists(type_name):
    """Check if a PostgreSQL type exists"""
    bind = op.get_bind()
    result = bind.execute(sa.text(
        f"SELECT 1 FROM pg_type WHERE typname = '{type_name}'"
    ))
    return result.fetchone() is not None


def upgrade() -> None:
    # Create ENUM types if they don't exist
    if not type_exists('task_type'):
        task_type_enum = postgresql.ENUM(
            'join', 'audio_overlay', 'text_overlay', 'subtitles', 'video_overlay', 'combined',
            name='task_type',
            create_type=True
        )
        task_type_enum.create(op.get_bind(), checkfirst=True)
    
    if not type_exists('task_status'):
        task_status_enum = postgresql.ENUM(
            'pending', 'processing', 'completed', 'failed', 'cancelled',
            name='task_status',
            create_type=True
        )
        task_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create users table if not exists
    if not table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('username', sa.String(50), unique=True, nullable=False),
            sa.Column('email', sa.String(255), unique=True, nullable=False),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('api_key', sa.String(64), unique=True, nullable=True),
            sa.Column('settings', postgresql.JSON(), nullable=True),
            sa.Column('is_admin', sa.Boolean(), default=False, nullable=False),
            sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    
    # Create users indexes if not exist
    if not index_exists('ix_users_username'):
        op.create_index('ix_users_username', 'users', ['username'])
    if not index_exists('ix_users_email'):
        op.create_index('ix_users_email', 'users', ['email'])
    if not index_exists('ix_users_api_key'):
        op.create_index('ix_users_api_key', 'users', ['api_key'])
    if not index_exists('ix_users_is_active'):
        op.create_index('ix_users_is_active', 'users', ['is_active'])
    
    # Create tasks table if not exists
    if not table_exists('tasks'):
        op.create_table(
            'tasks',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', postgresql.ENUM('join', 'audio_overlay', 'text_overlay', 'subtitles', 'video_overlay', 'combined', name='task_type', create_type=False), nullable=False),
            sa.Column('status', postgresql.ENUM('pending', 'processing', 'completed', 'failed', 'cancelled', name='task_status', create_type=False), nullable=False, server_default='pending'),
            sa.Column('input_files', postgresql.JSON(), nullable=False, server_default='[]'),
            sa.Column('output_files', postgresql.JSON(), nullable=False, server_default='[]'),
            sa.Column('config', postgresql.JSON(), nullable=True),
            sa.Column('error_message', sa.String(2000), nullable=True),
            sa.Column('progress', sa.Float(), default=0.0, nullable=False, server_default='0'),
            sa.Column('result', postgresql.JSON(), nullable=True),
            sa.Column('retry_count', sa.Integer(), default=0, nullable=False, server_default='0'),
            sa.Column('priority', sa.Integer(), default=5, nullable=False, server_default='5'),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    
    # Create tasks indexes if not exist
    if not index_exists('ix_tasks_user_id_status'):
        op.create_index('ix_tasks_user_id_status', 'tasks', ['user_id', 'status'])
    if not index_exists('ix_tasks_status'):
        op.create_index('ix_tasks_status', 'tasks', ['status'])
    if not index_exists('ix_tasks_created_at'):
        op.create_index('ix_tasks_created_at', 'tasks', ['created_at'])
    if not index_exists('ix_tasks_type'):
        op.create_index('ix_tasks_type', 'tasks', ['type'])
    
    # Create files table if not exists
    if not table_exists('files'):
        op.create_table(
            'files',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('original_filename', sa.String(255), nullable=False),
            sa.Column('size', sa.Integer(), nullable=False),
            sa.Column('content_type', sa.String(100), nullable=False),
            sa.Column('storage_path', sa.String(500), nullable=False),
            sa.Column('metadata', postgresql.JSON(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), default=False, nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    
    # Create files indexes if not exist
    if not index_exists('ix_files_user_id'):
        op.create_index('ix_files_user_id', 'files', ['user_id'])
    if not index_exists('ix_files_is_deleted'):
        op.create_index('ix_files_is_deleted', 'files', ['is_deleted'])
    if not index_exists('ix_files_created_at'):
        op.create_index('ix_files_created_at', 'files', ['created_at'])
    if not index_exists('ix_files_user_id_is_deleted'):
        op.create_index('ix_files_user_id_is_deleted', 'files', ['user_id', 'is_deleted'])
    
    # Create operation_logs table if not exists
    if not table_exists('operation_logs'):
        op.create_table(
            'operation_logs',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('operation_type', sa.String(100), nullable=False),
            sa.Column('duration', sa.Float(), nullable=False),
            sa.Column('success', sa.Boolean(), nullable=False),
            sa.Column('error_details', postgresql.JSON(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    
    # Create operation_logs indexes if not exist
    if not index_exists('ix_operation_logs_task_id'):
        op.create_index('ix_operation_logs_task_id', 'operation_logs', ['task_id'])
    if not index_exists('ix_operation_logs_operation_type'):
        op.create_index('ix_operation_logs_operation_type', 'operation_logs', ['operation_type'])
    if not index_exists('ix_operation_logs_timestamp'):
        op.create_index('ix_operation_logs_timestamp', 'operation_logs', ['timestamp'])
    if not index_exists('ix_operation_logs_task_id_timestamp'):
        op.create_index('ix_operation_logs_task_id_timestamp', 'operation_logs', ['task_id', 'timestamp'])
    
    # Create metrics table if not exists
    if not table_exists('metrics'):
        op.create_table(
            'metrics',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('metric_name', sa.String(100), nullable=False),
            sa.Column('metric_value', sa.Float(), nullable=False),
            sa.Column('tags', postgresql.JSON(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    
    # Create metrics indexes if not exist
    if not index_exists('ix_metrics_metric_name_timestamp'):
        op.create_index('ix_metrics_metric_name_timestamp', 'metrics', ['metric_name', 'timestamp'])
    if not index_exists('ix_metrics_metric_name'):
        op.create_index('ix_metrics_metric_name', 'metrics', ['metric_name'])
    if not index_exists('ix_metrics_timestamp'):
        op.create_index('ix_metrics_timestamp', 'metrics', ['timestamp'])


def downgrade() -> None:
    # Drop tables in reverse order (respect foreign keys)
    op.drop_table('metrics')
    op.drop_table('operation_logs')
    op.drop_table('files')
    op.drop_table('tasks')
    op.drop_table('users')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS task_type")
