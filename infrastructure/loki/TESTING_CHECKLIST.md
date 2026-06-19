# Loki Log Aggregation Testing Checklist

## Pre-Deployment Checks

- [ ] All configuration files are valid YAML
- [ ] Python syntax validated for modified files
- [ ] No sensitive data in configuration files
- [ ] Docker volumes configured correctly

## Deployment Steps

### 1. Start Infrastructure Services

- [ ] Start Loki: `docker-compose up -d loki`
- [ ] Verify Loki health: `curl http://localhost:3100/ready`
- [ ] Check Loki logs: `docker-compose logs loki`

### 2. Start Promtail

- [ ] Start Promtail: `docker-compose up -d promtail`
- [ ] Check Promtail logs: `docker-compose logs -f promtail`
- [ ] Verify no errors in Promtail startup

### 3. Start Application Services

- [ ] Start backend: `docker-compose up -d backend`
- [ ] Start Celery: `docker-compose up -d celery_worker`
- [ ] Verify services are healthy: `docker-compose ps`

### 4. Start Grafana

- [ ] Start Grafana: `docker-compose up -d grafana`
- [ ] Access Grafana: http://localhost:3001
- [ ] Login with admin/admin123
- [ ] Verify Loki datasource is configured

## Functional Tests

### Basic Logging

- [ ] Generate test logs:
  ```bash
  curl http://localhost:8000/api/v1/health
  curl http://localhost:8000/api/v1/docs
  ```

- [ ] Check backend logs contain JSON:
  ```bash
  docker-compose logs backend | grep -o '{.*}' | head -1 | jq .
  ```

- [ ] Verify required fields present:
  - [ ] timestamp
  - [ ] level
  - [ ] service
  - [ ] message
  - [ ] trace_id
  - [ ] user_id
  - [ ] environment
  - [ ] application

### Grafana Queries

Test in Grafana Explore (http://localhost:3001/explore):

- [ ] Query all logs: `{service="fastapi"}`
- [ ] Query errors: `{level="ERROR"}`
- [ ] Query by service: `{service="celery-worker"}`
- [ ] Filter by trace_id: `{service="fastapi"} |= "trace-id-here"`

### API Queries

- [ ] Query via Loki API:
  ```bash
  curl -G "http://localhost:3100/loki/api/v1/query_range" \
    --data-urlencode 'query={service="fastapi"}' \
    --data-urlencode 'limit=10'
  ```

- [ ] Get available labels:
  ```bash
  curl http://localhost:3100/loki/api/v1/labels
  ```

- [ ] Get service values:
  ```bash
  curl http://localhost:3100/loki/api/v1/label/service/values
  ```

### Trace ID Testing

- [ ] Make a request and capture trace_id from response header:
  ```bash
  curl -v http://localhost:8000/api/v1/health 2>&1 | grep -i x-trace-id
  ```

- [ ] Query logs by that trace_id in Grafana
- [ ] Verify all logs for that request have same trace_id

### User ID Testing

- [ ] Authenticate as a user
- [ ] Make authenticated request
- [ ] Query logs: `{service="fastapi"} | json | user_id="user-id-here"`
- [ ] Verify user_id appears in logs

### Celery Task Logging

- [ ] Trigger a Celery task
- [ ] Query task logs: `{service="celery-worker"}`
- [ ] Verify task_id and task_name are present
- [ ] Check task completion logs

### Error Logging

- [ ] Trigger an error (e.g., invalid endpoint)
- [ ] Query error logs: `{level="ERROR"}`
- [ ] Verify error details are captured
- [ ] Check stack trace is included

## Performance Tests

- [ ] Generate high volume of logs (100+ requests)
- [ ] Check Loki ingestion rate: `curl http://localhost:3100/metrics | grep loki_ingester_chunks_created_total`
- [ ] Verify no dropped logs
- [ ] Check Promtail backlog is empty

## Retention Tests

- [ ] Verify retention configuration (30 days)
- [ ] Check compaction is running
- [ ] Monitor disk usage: `docker exec knowledge_loki du -sh /loki`

## Integration Tests

- [ ] Logs appear in Grafana within 10 seconds
- [ ] JSON parsing works correctly
- [ ] Labels are extracted properly
- [ ] Timestamps are correct
- [ ] No duplicate log entries

## Troubleshooting Validation

Test common issues and solutions:

- [ ] Logs not appearing:
  - Check Promtail is running
  - Verify log file paths
  - Check Loki ingestion metrics

- [ ] Query performance:
  - Test with specific labels
  - Verify time range is appropriate
  - Check query parallelism

- [ ] Storage issues:
  - Monitor disk usage
  - Verify compaction is running
  - Check retention policy

## Documentation Verification

- [ ] README.md is complete and accurate
- [ ] QUICKSTART.md provides working examples
- [ ] log-examples.json has valid sample logs
- [ ] All query examples work correctly

## Final Checks

- [ ] All services are running
- [ ] No errors in any logs
- [ ] Grafana dashboards accessible
- [ ] Loki metrics endpoint working
- [ ] Promtail is shipping logs
- [ ] Log retention is configured
- [ ] Documentation is accessible

## Sign-Off

- [ ] Functional tests passed
- [ ] Performance tests passed
- [ ] Integration tests passed
- [ ] Documentation verified
- [ ] Ready for production deployment

---

**Notes:**
- Record any issues encountered during testing
- Document any configuration adjustments needed
- Update documentation based on test results
