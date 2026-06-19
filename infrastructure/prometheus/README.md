# Prometheus Metrics Configuration

This directory contains the Prometheus configuration for the GenAI Knowledge Retrieval System.

## Overview

The application exposes comprehensive metrics at `/api/v1/metrics` endpoint for Prometheus to scrape and collect.

## Metrics Exposed

### Standard HTTP Metrics (via prometheus-fastapi-instrumentator)

1. **http_requests_total** - Total HTTP request count
   - Labels: `method`, `handler`, `status`
   
2. **http_request_duration_seconds** - Request duration histogram
   - Percentiles: p50, p95, p99
   - Labels: `method`, `handler`
   
3. **http_requests_inprogress** - Currently active requests
   - Labels: `method`, `handler`

### Custom Application Metrics

#### RAG Query Processing
- **query_processing_duration_seconds** - Total RAG pipeline execution time
- **embedding_generation_duration_seconds** - Time to generate query embeddings
- **vector_search_duration_seconds** - Vector similarity search execution time
- **vector_search_results_count** - Number of results returned from vector search

#### LLM API Metrics
- **llm_api_requests_total** - Total LLM API calls
  - Labels: `model`, `status` (success/error)
- **llm_api_duration_seconds** - LLM API call duration
  - Labels: `model`
- **llm_tokens_used_total** - Total tokens consumed
  - Labels: `model`, `type` (prompt/completion)

#### Embedding Generation
- **embedding_generation_total** - Total embeddings generated
  - Labels: `model`, `status` (success/error)

#### Database Metrics
- **database_query_duration_seconds** - Database query execution time
  - Labels: `operation`
- **database_connection_pool_size** - Connection pool metrics
  - Labels: `state` (active/idle/total)

#### Chat & Session Metrics
- **active_chat_sessions** - Currently active chat sessions
- **chat_messages_total** - Total chat messages
  - Labels: `role` (user/assistant), `session_type`

#### Knowledge Base Metrics
- **knowledge_documents_total** - Documents in knowledge base
  - Labels: `content_type`
- **knowledge_embeddings_total** - Total embeddings in vector database

#### Document Ingestion
- **document_ingestion_duration_seconds** - Document ingestion time
  - Labels: `source_type`
- **documents_ingested_total** - Documents processed
  - Labels: `source_type`, `status`

#### Cache Metrics (Redis)
- **cache_operations_total** - Cache operations count
  - Labels: `operation`, `status`
- **cache_operation_duration_seconds** - Cache operation duration
  - Labels: `operation`

## Configuration

### Retention Policy
- **Retention Time**: 15 days
- **Retention Size**: 10 GB
- Configured in `prometheus.yml` under `storage.tsdb`

### Scrape Configuration
- **Scrape Interval**: 10 seconds (backend API), 15 seconds (default)
- **Scrape Timeout**: 5 seconds
- **Metrics Path**: `/api/v1/metrics`
- **Target**: `backend:8000`

## Running Prometheus

### Using Docker Compose

```bash
# Start Prometheus with the application
docker-compose up -d prometheus

# View Prometheus logs
docker-compose logs -f prometheus
```

### Standalone Docker

```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.retention.time=15d \
  --storage.tsdb.retention.size=10GB
```

## Accessing Prometheus

- **Prometheus UI**: http://localhost:9090
- **Metrics Endpoint**: http://localhost:8000/api/v1/metrics
- **Query Interface**: http://localhost:9090/graph

## Example Queries

### Request Rate
```promql
rate(http_requests_total[5m])
```

### Request Latency (p95)
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### Error Rate
```promql
rate(http_requests_total{status=~"5.."}[5m])
```

### Average Query Processing Time
```promql
rate(query_processing_duration_seconds_sum[5m]) / rate(query_processing_duration_seconds_count[5m])
```

### LLM Token Usage
```promql
rate(llm_tokens_used_total[1h])
```

### Active Connections
```promql
database_connection_pool_size{state="active"}
```

## Integration with Grafana

Import the included Grafana dashboards (if available) or create custom dashboards using the exposed metrics.

Recommended panels:
- Request rate and latency
- Error rates
- Query processing time breakdown
- LLM API usage and costs
- Database performance
- Cache hit/miss rates

## Alerting

Configure alerting rules in `alerts/*.yml` files (to be created) for:
- High error rates (> 5%)
- Slow request latency (p95 > 3s)
- High LLM API costs
- Database connection pool exhaustion
- Circuit breaker activation

## Troubleshooting

### Metrics not appearing
1. Check if the backend is running: `curl http://localhost:8000/api/v1/metrics`
2. Verify Prometheus can reach the backend: Check Prometheus targets at http://localhost:9090/targets
3. Review Prometheus logs: `docker-compose logs prometheus`

### High cardinality warnings
If you see warnings about high cardinality metrics, review label usage and consider aggregating or removing high-cardinality labels.
