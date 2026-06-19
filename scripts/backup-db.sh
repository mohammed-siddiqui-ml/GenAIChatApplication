#!/bin/bash

###############################################################################
# Database Backup Script
# 
# This script creates compressed backups of the PostgreSQL database including:
# - Full database dump
# - Schema and data
# - Custom metadata
#
# Usage: ./scripts/backup-db.sh [backup_directory]
#
# Environment variables required:
# - POSTGRES_USER
# - POSTGRES_PASSWORD
# - POSTGRES_DB
###############################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${1:-/var/backups/knowledge-db}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="backup-${TIMESTAMP}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"
COMPRESSED_PATH="${BACKUP_PATH}.gz"
RETENTION_DAYS=30  # Keep backups for 30 days

# Load environment variables
if [ -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${GREEN}Loading environment variables from .env${NC}"
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found, using environment variables${NC}"
fi

# Validate required environment variables
if [ -z "${POSTGRES_USER:-}" ] || [ -z "${POSTGRES_PASSWORD:-}" ] || [ -z "${POSTGRES_DB:-}" ]; then
    echo -e "${RED}Error: Required environment variables not set${NC}"
    echo "Please set POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}Database Backup Script${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo "Backup directory: ${BACKUP_DIR}"
echo "Database: ${POSTGRES_DB}"
echo "Timestamp: ${TIMESTAMP}"
echo -e "${GREEN}===========================================================${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if postgres container is running
if ! docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" ps postgres | grep -q "Up"; then
    echo -e "${RED}Error: PostgreSQL container is not running${NC}"
    echo "Start it with: docker-compose up -d postgres"
    exit 1
fi

echo -e "${YELLOW}Creating database backup...${NC}"

# Create backup using pg_dump via Docker
docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --verbose \
    --clean \
    --if-exists \
    --create \
    --format=plain \
    > "${BACKUP_PATH}"

# Check if backup was created successfully
if [ ! -f "${BACKUP_PATH}" ]; then
    echo -e "${RED}Error: Backup file was not created${NC}"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
echo -e "${GREEN}Backup created successfully: ${BACKUP_SIZE}${NC}"

# Compress backup
echo -e "${YELLOW}Compressing backup...${NC}"
gzip -f "${BACKUP_PATH}"

# Check if compression was successful
if [ ! -f "${COMPRESSED_PATH}" ]; then
    echo -e "${RED}Error: Backup compression failed${NC}"
    exit 1
fi

COMPRESSED_SIZE=$(du -h "${COMPRESSED_PATH}" | cut -f1)
echo -e "${GREEN}Backup compressed successfully: ${COMPRESSED_SIZE}${NC}"

# Create backup metadata
METADATA_FILE="${BACKUP_DIR}/backup-${TIMESTAMP}.meta"
cat > "${METADATA_FILE}" << EOF
{
  "timestamp": "${TIMESTAMP}",
  "database": "${POSTGRES_DB}",
  "user": "${POSTGRES_USER}",
  "backup_file": "${BACKUP_FILE}.gz",
  "compressed_size": "${COMPRESSED_SIZE}",
  "created_at": "$(date -Iseconds)",
  "hostname": "$(hostname)",
  "docker_compose_version": "$(docker-compose version --short)"
}
EOF

echo -e "${GREEN}Metadata created: ${METADATA_FILE}${NC}"

# Remove old backups (older than RETENTION_DAYS)
echo -e "${YELLOW}Cleaning up old backups (older than ${RETENTION_DAYS} days)...${NC}"
find "${BACKUP_DIR}" -name "backup-*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "backup-*.meta" -type f -mtime +${RETENTION_DAYS} -delete

REMAINING_BACKUPS=$(find "${BACKUP_DIR}" -name "backup-*.sql.gz" -type f | wc -l)
echo -e "${GREEN}Cleanup complete. Remaining backups: ${REMAINING_BACKUPS}${NC}"

# List recent backups
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}Recent Backups:${NC}"
echo -e "${GREEN}===========================================================${NC}"
ls -lht "${BACKUP_DIR}"/backup-*.sql.gz | head -5

echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}Backup completed successfully!${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo "Backup file: ${COMPRESSED_PATH}"
echo "Compressed size: ${COMPRESSED_SIZE}"
echo "Metadata: ${METADATA_FILE}"
echo -e "${GREEN}===========================================================${NC}"

# Exit successfully
exit 0
