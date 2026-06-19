# Grafana Dashboards for GenAI Knowledge Retrieval System

This directory contains pre-configured Grafana dashboards for comprehensive monitoring of the GenAI Knowledge Retrieval System.

## Overview

The monitoring stack includes:
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Loki**: Log aggregation (optional)

## Dashboards

### 1. API Performance Dashboard (`api-dashboard.json`)

**Purpose**: Monitor API health, performance, and user activity

**Key Panels**:
- **Request Rate**: HTTP requests per second by method, handler, and status code
- **Request Latency Percentiles**: p50, p95, p99 latency metrics
- **Error Rate**: 4xx and 5xx error rates with alerting (threshold: 5%)
- **Active Sessions**: Real-time active chat session count
- **Query Processing Duration**: RAG pipeline performance (p95, p99)
- **LLM API Requests Rate**: LLM API call rates by model and status

**Metrics Used**:
- `http_requests_total`
- `http_request_duration_seconds`
- `active_chat_sessions`
- `query_processing_duration_seconds`
- `llm_api_requests_total`

---

### 2. System Resources Dashboard (`system-dashboard.json`)

**Purpose**: Monitor infrastructure and system resources

**Key Panels**:
- **CPU Usage**: Overall and backend-specific CPU utilization (alert at 80%)
- **Memory Usage**: Total, used, and backend memory consumption
- **Disk I/O Rate**: Read/write operations per device
- **Network Traffic**: Inbound/outbound network traffic by interface
- **Disk Space Usage**: Disk utilization gauge with thresholds (70%, 85%)
- **Process Count**: Number of running backend instances
- **File Descriptors**: Open file descriptors vs. limits

**Metrics Used**:
- `node_cpu_seconds_total`
- `process_cpu_seconds_total`
- `node_memory_*`
- `process_resident_memory_bytes`
- `node_disk_*`
- `node_network_*`
- `node_filesystem_*`
- `process_open_fds`, `process_max_fds`

---

### 3. Database Performance Dashboard (`database-dashboard.json`)

**Purpose**: Monitor database and cache performance

**Key Panels**:
- **Connection Pool Usage**: Active, idle, and total database connections (alert at 90%)
- **Query Duration**: p95 and p99 query execution times by operation
- **Cache Hit Rate**: Redis cache hit percentage (threshold: 70%)
- **Cache Operations Rate**: Cache hits, misses, and set operations
- **Database Query Rate by Operation**: Queries per second by operation type
- **PostgreSQL Active Connections**: Real-time active connection count
- **PostgreSQL Idle Connections**: Idle connection count
- **Cache Operation Duration**: p95 and p99 cache operation latencies

**Metrics Used**:
- `database_connection_pool_size`
- `database_query_duration_seconds`
- `cache_operations_total`
- `cache_operation_duration_seconds`
- `pg_stat_activity_count`

---

### 4. Celery Tasks Dashboard (`celery-dashboard.json`)

**Purpose**: Monitor background task processing and workers

**Key Panels**:
- **Task Queue Depth**: Number of pending tasks per queue (alert at 100)
- **Task Success/Failure Rate**: Task completion rates and retries
- **Task Duration**: p95 and p99 task execution times by task type
- **Task Failure Rate**: Percentage of failed tasks (threshold: 5%)
- **Active Workers**: Current number of active Celery workers
- **Task Execution Rate**: Tasks processed per second
- **Document Ingestion Tasks**: Ingestion performance and success/failure rates
- **Task Queue Throughput**: Tasks sent, received, and started
- **Worker Pool Utilization**: Worker pool usage percentage

**Metrics Used**:
- `celery_queue_length`
- `celery_task_succeeded_total`, `celery_task_failed_total`
- `celery_task_runtime_seconds`
- `celery_workers_active`
- `document_ingestion_duration_seconds`
- `documents_ingested_total`
- `celery_worker_pool_active`, `celery_worker_pool_max`

---

## Installation & Setup

### 1. Auto-Loading Dashboards

Dashboards are automatically loaded via Grafana provisioning:

```yaml
# infrastructure/grafana/provisioning/dashboards/dashboards.yml
providers:
  - name: 'GenAI Knowledge Retrieval Dashboards'
    folder: 'GenAI Monitoring'
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

### 2. Docker Compose Configuration

The `docker-compose.yml` mounts dashboards automatically:

```yaml
grafana:
  volumes:
    - ./infrastructure/grafana/provisioning/dashboards/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml:ro
    - ./infrastructure/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
```

### 3. Starting Grafana

```bash
# Start the entire stack
docker-compose up -d

# Start only Grafana and dependencies
docker-compose up -d grafana prometheus
```

### 4. Accessing Grafana

- **URL**: http://localhost:3001
- **Default Username**: admin
- **Default Password**: admin123 (configure via environment variables)

---

## Configuration

### Prometheus Data Source

The Prometheus data source is pre-configured in `config/grafana-datasources.yml`:

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

### Dashboard Customization

All dashboards support:
- **Time Range Selection**: Last 1h, 6h, 24h, 7d, 30d
- **Refresh Intervals**: 5s, 10s, 30s, 1m, 5m, 15m, 30m, 1h
- **Auto-Refresh**: Dashboards refresh every 10 seconds by default
- **Editable**: Dashboards can be edited and saved from the UI

---

## Alerts

Dashboards include built-in alert conditions:

| Dashboard | Alert | Threshold | Action |
|-----------|-------|-----------|--------|
| API | High Error Rate | > 5% | Investigate failing endpoints |
| System | High CPU Usage | > 80% | Scale resources or optimize |
| Database | Connection Pool Exhaustion | > 90% | Increase pool size |
| Celery | High Queue Depth | > 100 | Add workers or optimize tasks |
| Celery | High Task Failure Rate | > 5% | Review failed tasks |

---

## Troubleshooting

### Dashboards Not Loading

1. Check Grafana logs:
   ```bash
   docker-compose logs grafana
   ```

2. Verify volume mounts:
   ```bash
   docker exec knowledge_grafana ls -la /etc/grafana/provisioning/dashboards
   ```

3. Check dashboard JSON syntax:
   ```bash
   cat infrastructure/grafana/dashboards/api-dashboard.json | jq .
   ```

### No Data in Panels

1. Verify Prometheus is scraping metrics:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

2. Check backend metrics endpoint:
   ```bash
   curl http://localhost:8000/api/v1/metrics
   ```

3. Verify Prometheus data source in Grafana (Settings > Data Sources)

### Missing Metrics

Some metrics require additional exporters:
- **Node Exporter**: For system metrics (`node_*`)
- **PostgreSQL Exporter**: For database metrics (`pg_*`)
- **Celery Exporter**: For Celery metrics (`celery_*`)

Install via Docker Compose or configure manually.

---

## Best Practices

1. **Regular Review**: Review dashboards daily for anomalies
2. **Set Alerts**: Configure Grafana alerts or use Alertmanager
3. **Customize**: Adjust thresholds based on your workload
4. **Export**: Export custom dashboards for version control
5. **Document**: Document any custom modifications

---

## References

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
