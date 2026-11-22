#!/bin/bash
set -e

# WebOps Docker Entrypoint Script
# Handles initialization and startup for the control panel container

echo "🚀 Starting WebOps Control Panel..."

# Function to wait for database
wait_for_db() {
    echo "⏳ Waiting for database..."
    while ! pg_isready -h "${DATABASE_HOST:-db}" -p "${DATABASE_PORT:-5432}" -U "${DATABASE_USER:-webops}"; do
        echo "Database not ready, waiting..."
        sleep 2
    done
    echo "✅ Database is ready"
}

# Function to wait for Redis
wait_for_redis() {
    echo "⏳ Waiting for Redis..."
    while ! redis-cli -h "${REDIS_HOST:-redis}" -p "${REDIS_PORT:-6379}" ping; do
        echo "Redis not ready, waiting..."
        sleep 2
    done
    echo "✅ Redis is ready"
}

# Function to run migrations
run_migrations() {
    echo "🔄 Running database migrations..."
    python manage.py migrate --noinput
    echo "✅ Migrations completed"
}

# Function to collect static files
collect_static() {
    echo "📁 Collecting static files..."
    python manage.py collectstatic --noinput --clear
    echo "✅ Static files collected"
}

# Function to create superuser if needed
create_superuser() {
    if [ "${CREATE_SUPERUSER:-false}" != "true" ]; then
        return
    fi
    if [ -z "${WEBOPS_ADMIN_PASSWORD:-}" ] || [ "${#WEBOPS_ADMIN_PASSWORD}" -lt 16 ] || [ -z "${WEBOPS_ADMIN_EMAIL:-}" ]; then
        echo "ERROR: CREATE_SUPERUSER=true requires WEBOPS_ADMIN_PASSWORD (16+ chars) and WEBOPS_ADMIN_EMAIL" >&2
        exit 1
    fi
    python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get("WEBOPS_ADMIN_USERNAME", "webops-admin")
password = os.environ["WEBOPS_ADMIN_PASSWORD"]
email = os.environ["WEBOPS_ADMIN_EMAIL"]
if password.lower() in ("admin123", "password123", "changeme", "password"):
    raise SystemExit("Refusing an insecure administrator password")
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print("Administrator account created; credentials are not logged")
else:
    print("Administrator already exists; credentials were not changed")
PY
}

# Function to initialize WebOps directories
init_webops_dirs() {
    echo "📂 Initializing WebOps directories..."
    python manage.py init_webops_dirs
    echo "✅ WebOps directories initialized"
}

# Main execution
main() {
    # Wait for dependencies
    wait_for_db
    wait_for_redis
    
    # Initialize application
    run_migrations
    collect_static
    init_webops_dirs
    
    # Create superuser if requested
    create_superuser
    
    echo "🎉 WebOps Control Panel is ready!"
    
    # Execute the main command
    exec "$@"
}

# Run main function with all arguments
main "$@"