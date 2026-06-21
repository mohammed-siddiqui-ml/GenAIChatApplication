"""Initial database schema with all tables

Revision ID: 001
Revises: 
Create Date: 2026-06-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all database tables and extensions."""
    
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create ENUM types
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'user')")
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system')")
    op.execute("CREATE TYPE data_source_type AS ENUM ('confluence', 'jira', 'onboarding', 'custom')")
    op.execute("CREATE TYPE content_type AS ENUM ('page', 'issue', 'document', 'video_transcript')")
    op.execute("CREATE TYPE job_status AS ENUM ('pending', 'running', 'success', 'failed')")
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'user', name='user_role'), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_activity_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('ended_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_chat_sessions_session_token', 'chat_sessions', ['session_token'], unique=True)
    op.create_index('idx_chat_sessions_user_id', 'chat_sessions', ['user_id'])
    
    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', postgresql.ENUM('user', 'assistant', 'system', name='message_role'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('embedding', postgresql.ARRAY(sa.Float(), dimensions=1), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE')
    )
    op.create_index('idx_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('idx_chat_messages_created_at', 'chat_messages', ['created_at'])
    
    # Create data_sources table
    op.create_table(
        'data_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', postgresql.ENUM('confluence', 'jira', 'onboarding', 'custom', name='data_source_type'), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sync_schedule', sa.String(length=50), nullable=True),
        sa.Column('last_sync_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_data_sources_type', 'data_sources', ['type'])
    op.create_index('idx_data_sources_created_by', 'data_sources', ['created_by'])
    
    # Create ingestion_jobs table
    op.create_table(
        'ingestion_jobs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('data_source_id', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'success', 'failed', name='job_status'), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('documents_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('documents_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ondelete='CASCADE')
    )
    op.create_index('idx_ingestion_jobs_data_source_id', 'ingestion_jobs', ['data_source_id'])
    op.create_index('idx_ingestion_jobs_status_started_at', 'ingestion_jobs', ['status', 'started_at'])

    # Create knowledge_documents table
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('data_source_id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_type', postgresql.ENUM('page', 'issue', 'document', 'video_transcript', name='content_type'), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('document_hash', sa.String(length=64), nullable=True),
        sa.Column('indexed_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tsvector_content', postgresql.TSVECTOR(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ondelete='CASCADE')
    )
    op.create_index('idx_knowledge_documents_data_source_id', 'knowledge_documents', ['data_source_id'])
    op.create_index('idx_knowledge_documents_external_id', 'knowledge_documents', ['external_id', 'data_source_id'], unique=True)
    op.create_index('idx_knowledge_documents_document_hash', 'knowledge_documents', ['document_hash'])

    # Create GIN index for full-text search
    op.execute(
        'CREATE INDEX idx_knowledge_documents_tsvector_gin ON knowledge_documents USING gin(tsvector_content)'
    )

    # Create trigger to automatically update tsvector_content
    op.execute("""
        CREATE OR REPLACE FUNCTION knowledge_documents_tsvector_update() RETURNS trigger AS $$
        BEGIN
            NEW.tsvector_content := to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER tsvector_update_trigger
        BEFORE INSERT OR UPDATE ON knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION knowledge_documents_tsvector_update();
    """)

    # Create document_embeddings table
    op.create_table(
        'document_embeddings',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=False),  # Will be cast to vector in raw SQL
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE')
    )

    # Alter embedding column to use pgvector type (768 dimensions for Ollama nomic-embed-text)
    op.execute('ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)')

    op.create_index('idx_document_embeddings_document_id', 'document_embeddings', ['document_id'])
    op.create_index('idx_document_embeddings_document_chunk', 'document_embeddings', ['document_id', 'chunk_index'], unique=True)

    # Create HNSW index for vector similarity search
    # Using HNSW (Hierarchical Navigable Small World) for better performance
    op.execute(
        'CREATE INDEX idx_document_embeddings_hnsw ON document_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)'
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.BigInteger(), nullable=True),
        sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])


def downgrade() -> None:
    """Drop all database tables and extensions."""

    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_table('audit_logs')
    op.drop_table('document_embeddings')

    # Drop trigger and function for tsvector
    op.execute('DROP TRIGGER IF EXISTS tsvector_update_trigger ON knowledge_documents')
    op.execute('DROP FUNCTION IF EXISTS knowledge_documents_tsvector_update()')

    op.drop_table('knowledge_documents')
    op.drop_table('ingestion_jobs')
    op.drop_table('data_sources')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('users')

    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS job_status')
    op.execute('DROP TYPE IF EXISTS content_type')
    op.execute('DROP TYPE IF EXISTS data_source_type')
    op.execute('DROP TYPE IF EXISTS message_role')
    op.execute('DROP TYPE IF EXISTS user_role')

    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
