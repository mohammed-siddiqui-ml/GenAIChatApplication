# Loki Logging Quick Start Guide

## Getting Started in 5 Minutes

### 1. Start the Logging Stack

```bash
# Start Loki, Promtail, and Grafana
docker-compose up -d loki promtail grafana

# Verify services are running
docker-compose ps loki promtail grafana
```

### 2. Start Application Services

```bash
# Start backend and celery to generate logs
docker-compose up -d backend celery_worker

# Generate some test logs
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/docs
```

### 3. Access Grafana

1. Open browser: http://localhost:3001
2. Login: `admin` / `admin123`
3. Click **Explore** (compass icon in sidebar)
4. Select **Loki** from datasource dropdown

### 4. Run Your First Query

Try these queries in Grafana Explore:

**All FastAPI logs:**
```logql
{service="fastapi"}
```

**Only errors:**
```logql
{level="ERROR"}
```

**Track a request by trace ID:**
```logql
{service="fastapi"} |= "trace_id_here"
```

## Common Use Cases

### Debug a Specific User's Request

```logql
{service="fastapi"} | json | user_id="user_12345"
```

### Find Slow Requests (>1 second)

```logql
{service="fastapi"} | json | duration > 1000
```

### Monitor Celery Task Failures

```logql
{service="celery-worker", level="ERROR"}
```

### View Nginx Access Logs

```logql
{service="nginx", log_type="access"}
```

## Log Example

When you make a request, you'll see structured logs like this:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "service": "fastapi",
  "message": "Request completed: GET /api/v1/chat/sessions - 200",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "user_12345",
  "method": "GET",
  "path": "/api/v1/chat/sessions",
  "status_code": 200,
  "duration": "45.67ms"
}
```

## Troubleshooting

### Logs not appearing?

1. Check Promtail is running:
   ```bash
   docker-compose logs -f promtail
   ```

2. Verify Loki is healthy:
   ```bash
   curl http://localhost:3100/ready
   ```

3. Check log file paths exist:
   ```bash
   docker-compose exec backend ls -la /app/logs/
   ```

### Query returning no data?

- Check time range in Grafana (top right)
- Verify service is generating logs
- Try broader query: `{service=~".*"}`

## Next Steps

1. Read full documentation: `infrastructure/loki/README.md`
2. Explore query examples in README
3. Create custom Grafana dashboards
4. Set up alerts for critical errors

## Useful Commands

```bash
# View all logs from a service
docker-compose logs -f backend

# Restart Promtail to reload config
docker-compose restart promtail

# Check Loki metrics
curl http://localhost:3100/metrics | grep loki_

# Query via API
curl -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service="fastapi"}' \
  --data-urlencode 'limit=10'
```

## Tips

- Use `trace_id` to follow a request through multiple services
- Filter by `level="ERROR"` for troubleshooting
- Use `| json` to parse and filter JSON log fields
- Set appropriate time ranges to improve query performance
- Combine with Prometheus metrics for complete observability

Happy logging! 🚀
