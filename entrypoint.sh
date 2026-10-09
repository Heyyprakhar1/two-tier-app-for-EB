#!/bin/bash
set -e

# Default environment configuration
export MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
export MYSQL_PORT="${MYSQL_PORT:-3306}"
export MYSQL_DB="${MYSQL_DB:-devops_dashboard}"
export MYSQL_USER="${MYSQL_USER:-dashboard}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-dashboard123}"
export MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-rootpassword123}"
export PORT="${PORT:-5000}"
export SECRET_KEY="${SECRET_KEY:-devops-dashboard-secret-key}"

GUNICORN_PID=""

cleanup() {
    echo "[entrypoint] Received stop signal. Shutting down gracefully..."
    if [ -n "$GUNICORN_PID" ] && kill -0 "$GUNICORN_PID" 2>/dev/null; then
        kill -TERM "$GUNICORN_PID" 2>/dev/null || true
    fi
    if [ "$MYSQL_HOST" = "127.0.0.1" ] || [ "$MYSQL_HOST" = "localhost" ]; then
        echo "[entrypoint] Stopping embedded MySQL/MariaDB..."
        /etc/init.d/mariadb stop > /dev/null 2>&1 || true
    fi
    wait 2>/dev/null || true
    echo "[entrypoint] All services stopped."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Embedded database management
if [ "$MYSQL_HOST" = "127.0.0.1" ] || [ "$MYSQL_HOST" = "localhost" ]; then
    echo "[entrypoint] Managing embedded MySQL/MariaDB for zero-config single-container operation..."

    mkdir -p /var/lib/mysql /var/run/mysqld /var/log/mysql
    chown -R mysql:mysql /var/lib/mysql /var/run/mysqld /var/log/mysql

    # Initialize storage if empty
    if [ ! -d "/var/lib/mysql/mysql" ]; then
        echo "[entrypoint] Initializing fresh database tables in /var/lib/mysql..."
        mariadb-install-db --user=mysql --datadir=/var/lib/mysql > /dev/null 2>&1
    fi

    # Start MariaDB service
    echo "[entrypoint] Starting MariaDB service..."
    /etc/init.d/mariadb start

    # Use Debian system maintenance credentials for guaranteed administrative access
    SQL_ADMIN="mariadb --defaults-file=/etc/mysql/debian.cnf"

    # Configure database, user, permissions, and initial seed
    echo "[entrypoint] Ensuring database '${MYSQL_DB}' and user '${MYSQL_USER}' exist..."
    $SQL_ADMIN <<EOSQL
CREATE DATABASE IF NOT EXISTS \`${MYSQL_DB}\`;
GRANT ALL PRIVILEGES ON \`${MYSQL_DB}\`.* TO '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${MYSQL_DB}\`.* TO '${MYSQL_USER}'@'localhost' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${MYSQL_DB}\`.* TO '${MYSQL_USER}'@'127.0.0.1' IDENTIFIED BY '${MYSQL_PASSWORD}';
FLUSH PRIVILEGES;
EOSQL

    # Initialize schema and seed data if table does not exist
    TABLE_CHECK=$($SQL_ADMIN -N -s -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${MYSQL_DB}' AND table_name='deployments';" 2>/dev/null || echo "0")
    if [ "$TABLE_CHECK" = "0" ] && [ -f "/app/database/init.sql" ]; then
        echo "[entrypoint] Seeding initial tables and records from /app/database/init.sql..."
        $SQL_ADMIN "${MYSQL_DB}" < /app/database/init.sql
    fi

    echo "[entrypoint] Embedded MySQL service is healthy and ready on port ${MYSQL_PORT}."
else
    echo "[entrypoint] External database specified at ${MYSQL_HOST}:${MYSQL_PORT}. Skipping local MySQL startup."
fi

# Start Gunicorn production server in background
echo "[entrypoint] Starting Gunicorn WSGI server on 0.0.0.0:${PORT}..."
gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --threads 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    app:app &
GUNICORN_PID=$!

echo "[entrypoint] Application started successfully. Entering supervisor monitoring loop..."

# Supervisor loop: check both services every 2 seconds
while true; do
    # Check MySQL if running embedded
    if [ "$MYSQL_HOST" = "127.0.0.1" ] || [ "$MYSQL_HOST" = "localhost" ]; then
        if ! /etc/init.d/mariadb status > /dev/null 2>&1; then
            echo "[entrypoint] FATAL: Embedded MariaDB service died or became unresponsive!"
            cleanup
            exit 1
        fi
    fi

    # Check Gunicorn process
    if ! kill -0 "$GUNICORN_PID" 2>/dev/null; then
        echo "[entrypoint] FATAL: Gunicorn process (PID ${GUNICORN_PID}) exited unexpectedly!"
        cleanup
        exit 1
    fi

    sleep 2
done
