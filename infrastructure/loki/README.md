# Loki Log Aggregation

This directory contains the configuration for Grafana Loki log aggregation system and Promtail log shipping agent for the GenAI Knowledge Retrieval System.

## Overview

Loki is a horizontally-scalable, highly-available, multi-tenant log aggregation system inspired by Prometheus. It's designed to be cost-effective and easy to operate, as it doesn't index the contents of logs, but rather a set of labels for each log stream.

## Components

### 1. Loki Server (`loki-config.yml`)

The main log aggregation server that:
- Receives logs from Promtail agents
- Stores logs efficiently using filesystem storage
- Provides query API for Grafana
- Handles log retention and compaction

**Key Configuration:**
- HTTP Port: 3100
- GRPC Port: 9096
- Storage: Filesystem-based (boltdb-shipper)
- Retention: 30 days
- Ingestion Rate: 16MB/s
- Burst Size: 32MB

### 2. Promtail Agent (`promtail-config.yml`)

Log shipping agent that:
- Scrapes logs from various sources
- Parses JSON structured logs
- Extracts labels and metadata
- Ships logs to Loki server

**Log Sources:**
- FastAPI backend application logs
- Celery worker task logs
- Nginx access and error logs
- Docker container logs

## Structured Logging Format

All application logs follow a structured JSON format with the following fields:

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `timestamp` | string | ISO 8601 formatted timestamp | `2024-01-15T10:30:45.123Z` |
| `level` | string | Log level | `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `service` | string | Service name | `fastapi`, `celery-worker`, `nginx` |
| `message` | string | Log message | `Request completed successfully` |
| `trace_id` | string | Request trace ID for distributed tracing | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `user_id` | string | User ID if authenticated | `user_12345` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `method` | string | HTTP method (GET, POST, etc.) |
| `path` | string | Request path |
| `status_code` | integer | HTTP status code |
| `duration` | string | Request duration in milliseconds |
| `task_id` | string | Celery task ID |
| `task_name` | string | Celery task name |
| `error` | string | Error message if exception occurred |

## Log Query Examples

Access Grafana at `http://localhost:3001` (default credentials: admin/admin123) and use the Loki datasource.

### Basic Queries

#### 1. All logs from FastAPI service
```logql
{service="fastapi"}
```

#### 2. All ERROR level logs
```logql
{level="ERROR"}
```

#### 3. Logs from a specific service with ERROR level
```logql
{service="fastapi", level="ERROR"}
```

### Advanced Queries

#### 4. Filter logs by trace ID (track a specific request)
```logql
{service="fastapi"} |= "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

#### 5. Filter logs by user ID
```logql
{service="fastapi"} | json | user_id="user_12345"
```

#### 6. Find all 5xx errors in last hour
```logql
{service="fastapi"} | json | status_code >= 500
```

#### 7. Logs containing specific text
```logql
{service="fastapi"} |= "database connection"
```

#### 8. Regular expression matching
```logql
{service="fastapi"} |~ "failed|error|exception"
```

#### 9. Celery task failures
```logql
{service="celery-worker", level="ERROR"}
```

#### 10. Slow requests (duration > 1000ms)
```logql
{service="fastapi"} | json | duration > 1000
```

### Aggregation Queries

#### 11. Count errors by service in last hour
```logql
sum by (service) (count_over_time({level="ERROR"}[1h]))
```

#### 12. Rate of requests per minute
```logql
rate({service="fastapi"}[1m])
```

#### 13. Top 10 slowest endpoints
```logql
topk(10, avg_over_time({service="fastapi"} | json | unwrap duration [1h]) by (path))
```

#### 14. Error rate by endpoint
```logql
sum by (path) (rate({service="fastapi", level="ERROR"}[5m]))
```

## Accessing Logs

### Via Grafana UI

1. Open Grafana: `http://localhost:3001`
2. Navigate to **Explore** (compass icon)
3. Select **Loki** datasource
4. Enter your LogQL query
5. Set time range
6. Click **Run query**

### Via Loki API

Query logs programmatically:

```bash
# Query logs
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service="fastapi"}' \
  --data-urlencode 'limit=100'

# Query labels
curl -s "http://localhost:3100/loki/api/v1/labels"

# Query label values
curl -s "http://localhost:3100/loki/api/v1/label/service/values"
```

## Troubleshooting

### Check Loki Health
```bash
curl http://localhost:3100/ready
curl http://localhost:3100/metrics
```

### Check Promtail Status
```bash
docker-compose logs -f promtail
```

### View Loki Logs
```bash
docker-compose logs -f loki
```

### Common Issues

**Issue: Logs not appearing in Grafana**
- Check Promtail is running: `docker-compose ps promtail`
- Verify log file paths in promtail-config.yml
- Check Promtail logs for errors

**Issue: High memory usage**
- Reduce `ingestion_rate_mb` in loki-config.yml
- Decrease retention period
- Limit query parallelism

## Performance Tuning

### Optimize Query Performance
- Use specific labels in queries
- Limit time range
- Avoid regex when possible
- Use `|= "text"` instead of `|~ "text"` for exact matches

### Storage Management
- Default retention: 30 days
- Compaction runs every 10 minutes
- Monitor disk usage: `/loki` volume

## References

- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [LogQL Query Language](https://grafana.com/docs/loki/latest/logql/)
- [Promtail Configuration](https://grafana.com/docs/loki/latest/clients/promtail/configuration/)
