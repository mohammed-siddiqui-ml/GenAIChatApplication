"""Add video metadata fields and folder_watch data source type

Revision ID: 002
Revises: 001
Create Date: 2026-06-20

This migration adds:
1. Video metadata fields to knowledge_documents table (video_start_time, video_end_time, video_duration)
2. 'folder_watch' value to data_source_type enum

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add video metadata columns to knowledge_documents and folder_watch to data_source_type enum.
    """
    
    # Add folder_watch to data_source_type enum
    # For PostgreSQL, we need to use raw SQL to alter enum types
    op.execute("""
        ALTER TYPE data_source_type ADD VALUE IF NOT EXISTS 'folder_watch';
    """)
    
    # Add video metadata columns to knowledge_documents table
    op.add_column(
        'knowledge_documents',
        sa.Column(
            'video_start_time',
            sa.Float(),
            nullable=True,
            comment='Video timestamp start in seconds (for video transcript chunks)'
        )
    )
    
    op.add_column(
        'knowledge_documents',
        sa.Column(
            'video_end_time',
            sa.Float(),
            nullable=True,
            comment='Video timestamp end in seconds (for video transcript chunks)'
        )
    )
    
    op.add_column(
        'knowledge_documents',
        sa.Column(
            'video_duration',
            sa.Float(),
            nullable=True,
            comment='Total video duration in seconds'
        )
    )
    
    # Create index on video_start_time for efficient timestamp-based queries
    op.create_index(
        'ix_knowledge_documents_video_start_time',
        'knowledge_documents',
        ['video_start_time'],
        unique=False
    )


def downgrade() -> None:
    """
    Remove video metadata columns and folder_watch enum value.
    
    Note: PostgreSQL does not support removing enum values easily,
    so we'll leave the enum value in place during downgrade.
    """
    
    # Drop index
    op.drop_index(
        'ix_knowledge_documents_video_start_time',
        table_name='knowledge_documents'
    )
    
    # Drop video metadata columns
    op.drop_column('knowledge_documents', 'video_duration')
    op.drop_column('knowledge_documents', 'video_end_time')
    op.drop_column('knowledge_documents', 'video_start_time')
    
    # Note: Cannot easily remove enum value in PostgreSQL
    # Manual intervention required if you need to remove 'folder_watch' from enum
