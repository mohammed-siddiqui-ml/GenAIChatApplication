"""
Prometheus Metrics Configuration

This module defines custom Prometheus metrics for monitoring the GenAI Knowledge Retrieval System.
Metrics include:
- Query processing duration
- Embedding generation duration
- Vector search duration
- Database query duration
- Custom business metrics
"""

import logging
from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Dict

# Logger
logger = logging.getLogger(__name__)

# ============================================================================
# HTTP Metrics (automatically handled by instrumentator)
# ============================================================================
# These are collected automatically:
# - http_requests_total
# - http_request_duration_seconds (with percentiles p50, p95, p99)
# - http_requests_in_progress

# ============================================================================
# Custom Business Metrics
# ============================================================================

# Query Processing Metrics
query_processing_duration = Histogram(
    'query_processing_duration_seconds',
    'Time spent processing queries in RAG pipeline',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Embedding Generation Metrics
embedding_generation_duration = Histogram(
    'embedding_generation_duration_seconds',
    'Time spent generating embeddings from OpenAI',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

embedding_generation_total = Counter(
    'embedding_generation_total',
    'Total number of embeddings generated',
    ['model', 'status']
)

# Vector Search Metrics
vector_search_duration = Histogram(
    'vector_search_duration_seconds',
    'Time spent performing vector similarity search',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

vector_search_results = Histogram(
    'vector_search_results_count',
    'Number of results returned from vector search',
    buckets=[0, 5, 10, 20, 50, 100]
)

# Database Query Metrics
database_query_duration = Histogram(
    'database_query_duration_seconds',
    'Time spent executing database queries',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

database_connection_pool = Gauge(
    'database_connection_pool_size',
    'Current database connection pool size',
    ['state']  # active, idle, total
)

# Chat Session Metrics
active_chat_sessions = Gauge(
    'active_chat_sessions',
    'Number of currently active chat sessions'
)

chat_messages_total = Counter(
    'chat_messages_total',
    'Total number of chat messages',
    ['role', 'session_type']  # user/assistant, authenticated/anonymous
)

# Document Ingestion Metrics
document_ingestion_duration = Histogram(
    'document_ingestion_duration_seconds',
    'Time spent ingesting documents',
    ['source_type'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0]
)

documents_ingested_total = Counter(
    'documents_ingested_total',
    'Total number of documents ingested',
    ['source_type', 'status']
)

# Knowledge Base Metrics
knowledge_documents_total = Gauge(
    'knowledge_documents_total',
    'Total number of documents in knowledge base',
    ['content_type']
)

knowledge_embeddings_total = Gauge(
    'knowledge_embeddings_total',
    'Total number of embeddings in vector database'
)

# LLM API Metrics
llm_api_requests_total = Counter(
    'llm_api_requests_total',
    'Total number of LLM API requests',
    ['model', 'status']
)

llm_api_duration = Histogram(
    'llm_api_duration_seconds',
    'Time spent on LLM API calls',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

llm_tokens_used = Counter(
    'llm_tokens_used_total',
    'Total number of tokens used in LLM requests',
    ['model', 'type']  # prompt/completion
)

# Cache Metrics (Redis)
cache_operations_total = Counter(
    'cache_operations_total',
    'Total number of cache operations',
    ['operation', 'status']  # get/set/delete, hit/miss/success/error
)

cache_operation_duration = Histogram(
    'cache_operation_duration_seconds',
    'Time spent on cache operations',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)


def get_metrics_dict() -> Dict[str, str]:
    """
    Get a dictionary of all custom metrics for reference.
    
    Returns:
        Dict mapping metric names to their descriptions
    """
    return {
        'query_processing_duration_seconds': 'RAG query processing time',
        'embedding_generation_duration_seconds': 'Embedding generation time',
        'vector_search_duration_seconds': 'Vector search execution time',
        'database_query_duration_seconds': 'Database query execution time',
        'active_chat_sessions': 'Currently active chat sessions',
        'chat_messages_total': 'Total chat messages',
        'document_ingestion_duration_seconds': 'Document ingestion time',
        'knowledge_documents_total': 'Documents in knowledge base',
        'knowledge_embeddings_total': 'Embeddings in vector DB',
        'llm_api_requests_total': 'LLM API requests',
        'llm_tokens_used_total': 'LLM tokens consumed',
        'cache_operations_total': 'Cache operations',
    }
