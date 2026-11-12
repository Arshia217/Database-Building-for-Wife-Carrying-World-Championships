#!/usr/bin/env bash
set -e

# Resolve repository root directory (one level up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Step 1: Granting DB user access ==="
if command -v mariadb &> /dev/null; then
    DB_CLI="mariadb"
else
    DB_CLI="mysql"
fi

echo "Executing: sudo $DB_CLI < scripts/setup_access.sql"
sudo "$DB_CLI" < "$REPO_ROOT/scripts/setup_access.sql"

echo "=== Step 2: Initializing Schema ==="
if [ "$DB_CLI" = "mariadb" ]; then
    # MariaDB compatibility: replace MySQL 8-specific utf8mb4_0900_ai_ci collation with utf8mb4_unicode_ci
    sed 's/COLLATE utf8mb4_0900_ai_ci/COLLATE utf8mb4_unicode_ci/g' "$REPO_ROOT/src/schema.sql" | $DB_CLI -u eukakanto_user -peukakanto_pass
else
    $DB_CLI -u eukakanto_user -peukakanto_pass < "$REPO_ROOT/src/schema.sql"
fi

echo "=== Step 3: Populating Data ==="
$DB_CLI -u eukakanto_user -peukakanto_pass < "$REPO_ROOT/src/populate.sql"

echo "=== Step 4: Verifying Connection ==="
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/src/db.py"
else
    python3 "$REPO_ROOT/src/db.py"
fi

echo "=== Database setup completed successfully! ==="
