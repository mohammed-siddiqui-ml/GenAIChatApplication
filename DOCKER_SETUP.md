# Docker Compose Environment Setup

## Overview
This Docker Compose configuration sets up a complete development and production-ready environment for the GenAI Knowledge Retrieval System with 11 services across 3 isolated networks.

## Services Architecture

### Core Services (4)
1. **PostgreSQL with pgvector** - Primary database with vector extension support
2. **Redis** - Cache and message broker with password authentication
3. **MinIO** - S3-compatible object storage for documents and assets
4. **Backend (FastAPI)** - Main API application server

### Worker Services (1)
5. **Celery Worker** - Background task processing for data ingestion and refresh

### Frontend Services (2)
6. **Frontend (React)** - User interface application
7. **Nginx** - Reverse proxy and load balancer

### Monitoring Services (3)
8. **Prometheus** - Metrics collection and monitoring
9. **Grafana** - Visualization and dashboards
10. **Loki** - Log aggregation and analysis

## Network Architecture

### Networks
- **frontend_network**: Frontend, Backend, Nginx
- **backend_network**: Backend, Celery, PostgreSQL, Redis, MinIO, Prometheus
- **monitoring_network**: Prometheus, Grafana, Loki, Nginx, Backend

### Service Isolation
- Frontend services isolated from direct database access
- Backend services have access to all data stores
- Monitoring services can observe all application services

## Health Checks

All stateful services have health checks configured:
- **PostgreSQL**: pg_isready check every 10s
- **Redis**: Connection ping every 10s
- **MinIO**: Health endpoint check every 30s
- **Backend**: HTTP health endpoint every 30s
- **Celery**: Worker ping check every 30s
- **Frontend**: HTTP check every 30s
- **Nginx**: Health endpoint proxy every 30s
- **Prometheus**: Health endpoint every 30s
- **Grafana**: API health check every 30s
- **Loki**: Ready endpoint every 30s

## Volumes

### Data Persistence
- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis persistence and AOF files
- `minio_data`: Object storage data
- `prometheus_data`: Metrics time-series database
- `grafana_data`: Dashboards and configurations
- `loki_data`: Log storage

### Log Volumes
- `backend_logs`: Application logs
- `celery_logs`: Worker task logs
- `nginx_logs`: Access and error logs

## Quick Start

### 1. Set up environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start all services
```bash
docker-compose up -d
```

### 3. Start specific services
```bash
docker-compose up -d postgres redis minio
docker-compose up -d backend celery_worker
docker-compose up -d frontend nginx
docker-compose up -d prometheus grafana loki
```

### 4. View logs
```bash
docker-compose logs -f backend
docker-compose logs -f celery_worker
```

### 5. Stop services
```bash
docker-compose down
```

### 6. Stop and remove volumes
```bash
docker-compose down -v
```

## Service Access

| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| Frontend | 80 | http://localhost | - |
| Backend API | 8000 | http://localhost:8000/api | - |
| PostgreSQL | 5432 | localhost:5432 | user/password |
| Redis | 6379 | localhost:6379 | redispassword |
| MinIO Console | 9001 | http://localhost:9001 | minioadmin/minioadmin123 |
| MinIO API | 9000 | http://localhost:9000 | minioadmin/minioadmin123 |
| Prometheus | 9090 | http://localhost:9090 | - |
| Grafana | 3001 | http://localhost:3001 | admin/admin123 |
| Loki | 3100 | http://localhost:3100 | - |

## Configuration Files

- `config/nginx.conf`: Nginx reverse proxy configuration
- `config/prometheus.yml`: Prometheus scraping configuration
- `config/loki-config.yml`: Loki log aggregation configuration
- `config/grafana-datasources.yml`: Grafana data source provisioning

## Environment Variables

See `.env.example` for all configurable environment variables.

### Critical Variables
- `POSTGRES_PASSWORD`: Database password
- `REDIS_PASSWORD`: Redis authentication
- `MINIO_ROOT_USER/PASSWORD`: Object storage credentials
- `OPENAI_API_KEY`: GenAI API key
- `GRAFANA_ADMIN_PASSWORD`: Monitoring dashboard access

## Troubleshooting

### Service won't start
```bash
docker-compose ps
docker-compose logs <service-name>
```

### Reset database
```bash
docker-compose down -v
docker-compose up -d postgres
```

### Check health status
```bash
docker-compose ps
docker inspect <container-name> | grep -A 10 Health
```

### Network issues
```bash
docker network ls
docker network inspect knowledge_backend_network
```

## Production Considerations

1. **Security**: Change all default passwords in `.env`
2. **Volumes**: Use named volumes or external storage
3. **Networking**: Configure firewall rules
4. **SSL/TLS**: Add certificates to Nginx configuration
5. **Resource Limits**: Add memory/CPU limits to services
6. **Backup**: Schedule regular backups of volumes
7. **Monitoring**: Configure alerting in Prometheus/Grafana
