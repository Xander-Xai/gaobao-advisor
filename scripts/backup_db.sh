#!/bin/bash
# Database Backup Script for Gaokao Advisor
# Creates timestamped gzip backups, keeps last 7 days
# Usage: ./scripts/backup_db.sh

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${PROJECT_DIR}/data"
BACKUP_DIR="${PROJECT_DIR}/backups"
DB_FILE="${DATA_DIR}/gaokao.db"
MAX_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if database exists
if [[ ! -f "$DB_FILE" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Database file not found at $DB_FILE, skipping backup"
    exit 0
fi

# Generate timestamp
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="${BACKUP_DIR}/gaokao_db_${TIMESTAMP}.sql.gz"

# Perform backup
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting database backup..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Source: $DB_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Destination: $BACKUP_FILE"

# Copy and compress the database
cp "$DB_FILE" "$BACKUP_FILE.tmp" && \
gzip -9 "$BACKUP_FILE.tmp" && \
mv "$BACKUP_FILE.tmp.gz" "$BACKUP_FILE"

# Verify backup was created
if [[ -f "$BACKUP_FILE" ]]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completed successfully: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Backup file was not created"
    exit 1
fi

# Clean up old backups (keep last 7 days)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up backups older than $MAX_DAYS days..."
DELETED_COUNT=0
while IFS= read -r backup; do
    rm -f "$backup"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -maxdepth 1 -name "gaokao_db_*.sql.gz" -type f -mtime +$MAX_DAYS)

if [[ $DELETED_COUNT -gt 0 ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deleted $DELETED_COUNT old backup(s)"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No old backups to delete"
fi

# Show current backup count
CURRENT_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 -name "gaokao_db_*.sql.gz" -type f | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Current backup count: $CURRENT_COUNT"

exit 0
