"""Change embedding dimension from 1536 to 768 for Ollama

Revision ID: 003
Revises: 002
Create Date: 2026-06-21 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change vector dimension from 1536 (OpenAI) to 768 (Ollama)."""
    
    # Drop existing indexes that depend on the vector column
    op.execute('DROP INDEX IF EXISTS idx_document_embeddings_hnsw')
    op.execute('DROP INDEX IF EXISTS idx_document_embeddings_embedding')
    
    # Delete all existing embeddings (they're the wrong dimensions)
    op.execute('TRUNCATE TABLE document_embeddings')
    
    # Alter the column to use 768 dimensions
    op.execute('ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(768) USING NULL::vector(768)')
    
    # Recreate the vector index (using IVFFlat for now since HNSW requires more data)
    op.execute(
        'CREATE INDEX idx_document_embeddings_embedding ON document_embeddings '
        'USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
    )


def downgrade() -> None:
    """Revert back to 1536 dimensions."""
    
    # Drop existing indexes
    op.execute('DROP INDEX IF EXISTS idx_document_embeddings_embedding')
    
    # Delete all existing embeddings (they're the wrong dimensions)
    op.execute('TRUNCATE TABLE document_embeddings')
    
    # Alter the column back to 1536 dimensions
    op.execute('ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(1536) USING NULL::vector(1536)')
    
    # Recreate the HNSW index
    op.execute(
        'CREATE INDEX idx_document_embeddings_hnsw ON document_embeddings '
        'USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)'
    )
