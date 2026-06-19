# Production Deployment Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Server Setup](#server-setup)
- [Environment Configuration](#environment-configuration)
- [SSL/TLS Setup](#ssltls-setup)
- [Deployment Steps](#deployment-steps)
- [Database Backups](#database-backups)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Server Requirements
- **Operating System**: Ubuntu 20.04 LTS or later / CentOS 8+ / Debian 11+
- **CPU**: Minimum 4 cores (8+ recommended for production)
- **RAM**: Minimum 16GB (32GB+ recommended)
- **Storage**: Minimum 100GB SSD (500GB+ recommended)
- **Network**: Public IP address and domain name

### Software Requirements
- Docker Engine 24.0+
- Docker Compose 2.20+
- Git 2.30+
- SSL certificate (Let's Encrypt recommended)

## Server Setup

### 1. Install Docker and Docker Compose

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

### 2. Configure Firewall

```bash
# Allow SSH, HTTP, and HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 3. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/your-repo.git
cd your-repo

# Checkout production branch
git checkout main
```

## Environment Configuration

### 1. Create Production Environment File

```bash
# Copy example environment file
cp .env.example .env

# Edit environment variables
nano .env
```

### 2. Critical Environment Variables

**Database Configuration:**
```bash
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=<strong-password-here>
POSTGRES_DB=knowledge_db_prod
```

**Redis Configuration:**
```bash
REDIS_PASSWORD=<strong-redis-password>
```

**MinIO Configuration:**
```bash
MINIO_ROOT_USER=<minio-admin-user>
MINIO_ROOT_PASSWORD=<strong-minio-password>
```

**Application Settings:**
```bash
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-64-char-random-string>
```

**GenAI Configuration:**
```bash
OPENAI_API_KEY=sk-your-production-api-key
```

**Domain Configuration:**
```bash
DOMAIN=yourdomain.com
BACKEND_URL=https://yourdomain.com/api
```

**Monitoring:**
```bash
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<strong-grafana-password>
GRAFANA_ROOT_URL=https://yourdomain.com/monitoring
```

### 3. Generate Strong Passwords

```bash
# Generate random passwords
openssl rand -base64 32
```

## SSL/TLS Setup

### Option 1: Let's Encrypt (Recommended)

#### 1. Install Certbot

```bash
sudo apt install certbot -y
```

#### 2. Obtain SSL Certificate

```bash
# Stop nginx if running
docker-compose down nginx

# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Certificates will be in /etc/letsencrypt/live/yourdomain.com/
```

#### 3. Copy Certificates to Project

```bash
# Create SSL directory
mkdir -p ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/chain.pem ssl/

# Set permissions
sudo chown -R $USER:$USER ssl/
chmod 600 ssl/privkey.pem
```

#### 4. Setup Auto-Renewal

```bash
# Add renewal cron job
sudo crontab -e

# Add this line (runs at 2 AM daily)
0 2 * * * certbot renew --quiet && docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
```

### Option 2: Custom SSL Certificate

If you have your own SSL certificate:

```bash
# Create SSL directory
mkdir -p ssl

# Copy your certificates
cp /path/to/your/fullchain.pem ssl/
cp /path/to/your/privkey.pem ssl/
cp /path/to/your/chain.pem ssl/

# Set permissions
chmod 600 ssl/privkey.pem
```

## Deployment Steps

### 1. Update Nginx Configuration

```bash
# Edit nginx.prod.conf with your domain
nano infrastructure/nginx/nginx.prod.conf

# Replace 'yourdomain.com' with your actual domain
```

### 2. Build Production Images

```bash
# Build all images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# This may take 5-10 minutes
```

### 3. Initialize Database

```bash
# Start only database services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis minio

# Wait for services to be healthy (30 seconds)
sleep 30

# Run database migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

### 4. Start All Services

```bash
# Start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### 5. Verify Deployment

```bash
# Check backend health
curl https://yourdomain.com/health

# Check API documentation
curl https://yourdomain.com/api/v1/docs

# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
```

### 6. Create Admin User

```bash
# Access backend container
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend bash

# Run admin creation script
python -m scripts.create_admin_user --email admin@yourdomain.com --password <secure-password>
```

## Database Backups

### Automated Backups

Backups are automatically created daily at 2 AM using the backup script:

```bash
# The backup script runs via cron
# See scripts/backup-db.sh for details

# Backups are stored in: /var/backups/knowledge-db/
```

### Manual Backup

```bash
# Run backup manually
./scripts/backup-db.sh

# Backups are stored with timestamp: backup-YYYYMMDD-HHMMSS.sql.gz
```

### Restore from Backup

```bash
# List available backups
ls -lh /var/backups/knowledge-db/

# Restore specific backup
./scripts/restore-db.sh /var/backups/knowledge-db/backup-20240115-020000.sql.gz
```

## Monitoring

### Access Monitoring Dashboards

1. **Grafana Dashboard**: https://yourdomain.com/monitoring
   - Username: Set in `GRAFANA_ADMIN_USER`
   - Password: Set in `GRAFANA_ADMIN_PASSWORD`

2. **System Metrics**: Available in Grafana
   - Application metrics
   - Database performance
   - API response times
   - Error rates

### Log Aggregation

Logs are centralized in Loki and viewable through Grafana:

```bash
# View backend logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend

# View all logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Check logs for specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs <service-name>

# Restart specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart <service-name>
```

### Database Connection Issues

```bash
# Check PostgreSQL health
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres pg_isready -U $POSTGRES_USER

# Check database logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs postgres

# Access database
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB
```

### SSL Certificate Issues

```bash
# Check certificate validity
openssl x509 -in ssl/fullchain.pem -text -noout

# Check certificate expiration
openssl x509 -in ssl/fullchain.pem -noout -dates

# Renew Let's Encrypt certificate
sudo certbot renew --force-renewal
```

### High Memory Usage

```bash
# Check container resource usage
docker stats

# Restart memory-intensive services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart celery_worker backend
```

### API Response Slow

```bash
# Check database query performance
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB

# Inside psql
SELECT * FROM pg_stat_activity WHERE state = 'active';

# Check Redis performance
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli info stats
```

## Maintenance

### Update Application

```bash
# Pull latest changes
git pull origin main

# Rebuild images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Run database migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Restart services with zero downtime
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --build backend frontend
```

### Scale Services

```bash
# Scale Celery workers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale celery_worker=4

# Scale backend instances (requires load balancer)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale backend=3
```

## Security Best Practices

1. **Change all default passwords** in `.env`
2. **Enable firewall** and allow only necessary ports
3. **Keep Docker and packages updated**
4. **Use SSL/TLS** for all external communication
5. **Regular security audits** and dependency updates
6. **Monitor logs** for suspicious activity
7. **Backup regularly** and test restore procedures
8. **Use secrets management** for sensitive data in production

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Review documentation: `/docs`
- Contact: support@yourdomain.com


