#!/bin/bash

###############################################################################
# Database Restore Script
# 
# This script restores PostgreSQL database from a compressed backup file.
#
# Usage: ./scripts/restore-db.sh <backup_file>
# Example: ./scripts/restore-db.sh /var/backups/knowledge-db/backup-20240115-020000.sql.gz
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

# Check if backup file argument is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /var/backups/knowledge-db/backup-20240115-020000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

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

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}Error: Backup file not found: ${BACKUP_FILE}${NC}"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}Database Restore Script${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo "Backup file: ${BACKUP_FILE}"
echo "Backup size: ${BACKUP_SIZE}"
echo "Database: ${POSTGRES_DB}"
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

# Warning prompt
echo -e "${YELLOW}===========================================================${NC}"
echo -e "${YELLOW}WARNING: This will replace all data in the database!${NC}"
echo -e "${YELLOW}===========================================================${NC}"
echo -e "${YELLOW}Database: ${POSTGRES_DB}${NC}"
echo -e "${YELLOW}Backup: ${BACKUP_FILE}${NC}"
echo -e "${YELLOW}===========================================================${NC}"
read -p "Are you sure you want to continue? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Restore cancelled${NC}"
    exit 0
fi

# Create a pre-restore backup
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PRE_RESTORE_BACKUP="/tmp/pre-restore-backup-${TIMESTAMP}.sql.gz"

echo -e "${YELLOW}Creating pre-restore backup...${NC}"
docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --clean \
    --if-exists \
    --create \
    | gzip > "${PRE_RESTORE_BACKUP}"

echo -e "${GREEN}Pre-restore backup created: ${PRE_RESTORE_BACKUP}${NC}"

# Stop services that depend on the database
echo -e "${YELLOW}Stopping dependent services...${NC}"
docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" stop backend celery_worker 2>/dev/null || true

# Decompress and restore backup
echo -e "${YELLOW}Restoring database from backup...${NC}"

# Check if backup is compressed
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    echo -e "${YELLOW}Decompressing and restoring...${NC}"
    gunzip -c "${BACKUP_FILE}" | docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
        psql -U "${POSTGRES_USER}" -d postgres
else
    echo -e "${YELLOW}Restoring from uncompressed backup...${NC}"
    cat "${BACKUP_FILE}" | docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
        psql -U "${POSTGRES_USER}" -d postgres
fi

# Check restore status
if [ $? -eq 0 ]; then
    echo -e "${GREEN}===========================================================${NC}"
    echo -e "${GREEN}Database restored successfully!${NC}"
    echo -e "${GREEN}===========================================================${NC}"
    echo "Pre-restore backup saved to: ${PRE_RESTORE_BACKUP}"
    echo -e "${GREEN}===========================================================${NC}"
    
    # Restart services
    echo -e "${YELLOW}Restarting services...${NC}"
    docker-compose -f "${PROJECT_ROOT}/docker-compose.yml" up -d backend celery_worker
    
    echo -e "${GREEN}Services restarted${NC}"
    echo -e "${GREEN}===========================================================${NC}"
    echo -e "${GREEN}Restore completed successfully!${NC}"
    echo -e "${GREEN}===========================================================${NC}"
    
    exit 0
else
    echo -e "${RED}===========================================================${NC}"
    echo -e "${RED}Error: Database restore failed!${NC}"
    echo -e "${RED}===========================================================${NC}"
    echo "You can restore from the pre-restore backup:"
    echo "gunzip -c ${PRE_RESTORE_BACKUP} | docker-compose exec -T postgres psql -U ${POSTGRES_USER} -d postgres"
    echo -e "${RED}===========================================================${NC}"
    
    exit 1
fi
