#!/bin/bash
# Záloha SQLite databázy spz-register
# Spúšťaj cez cron: 0 3 * * * /home/fifteen/spz-register/scripts/backup_db.sh >> /home/fifteen/spz-backups/backup.log 2>&1

set -euo pipefail

CONTAINER_PREFIX="spz"
BACKUP_DIR="/home/fifteen/spz-backups"
KEEP_DAYS=7
DATE=$(date +%Y-%m-%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Nájdi bežiaci kontajner podľa prefixu (funguje aj s Coolify názvami)
CONTAINER=$(docker ps --format '{{.Names}}' | grep "^${CONTAINER_PREFIX}" | head -1)

if [ -z "$CONTAINER" ]; then
  echo "$(date): CHYBA – žiadny bežiaci kontajner s prefixom '${CONTAINER_PREFIX}', záloha preskočená."
  exit 1
fi

BACKUP_FILE="${BACKUP_DIR}/db_${DATE}.sqlite"

# Bezpečná záloha cez SQLite backup API (funguje aj pri živom zápise)
docker exec "$CONTAINER" python3 -c "
import sqlite3
src = sqlite3.connect('/app/data/db.sqlite')
dst = sqlite3.connect('/tmp/db_backup.sqlite')
src.backup(dst)
dst.close()
src.close()
"

# Skopíruj zálohu z kontajnera na host
docker cp "${CONTAINER}:/tmp/db_backup.sqlite" "$BACKUP_FILE"

# Uprac tmp súbor v kontajneri
docker exec "$CONTAINER" rm -f /tmp/db_backup.sqlite

# Vymaž zálohy staršie ako KEEP_DAYS dní
find "$BACKUP_DIR" -name "db_*.sqlite" -mtime +${KEEP_DAYS} -delete

echo "$(date): OK – záloha uložená: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
