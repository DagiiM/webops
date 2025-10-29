#!/bin/bash

# WebOps Development Environment Stop Script
# Cleanly stops all development services

CELERY_PIDFILE="/tmp/celery_webops.pid"
BEAT_PIDFILE="/tmp/celery_beat.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

echo ""
print_info "Stopping WebOps development services..."
echo ""

# Stop Django development server and Daphne
print_info "Stopping development servers..."
pkill -f "manage.py runserver" 2>/dev/null || true
pkill -f "daphne.*config.asgi" 2>/dev/null || true

# Stop Celery worker
if [ -f "$CELERY_PIDFILE" ]; then
    worker_pid=$(cat "$CELERY_PIDFILE")
    if kill -0 "$worker_pid" 2>/dev/null; then
        print_info "Stopping Celery worker (PID: $worker_pid)..."
        kill -TERM "$worker_pid" 2>/dev/null || true
        sleep 2
        kill -KILL "$worker_pid" 2>/dev/null || true
    fi
    rm -f "$CELERY_PIDFILE"
fi

# Stop Celery Beat
if [ -f "$BEAT_PIDFILE" ]; then
    beat_pid=$(cat "$BEAT_PIDFILE")
    if kill -0 "$beat_pid" 2>/dev/null; then
        print_info "Stopping Celery Beat (PID: $beat_pid)..."
        kill -TERM "$beat_pid" 2>/dev/null || true
        sleep 2
        kill -KILL "$beat_pid" 2>/dev/null || true
    fi
    rm -f "$BEAT_PIDFILE"
fi

# Kill any remaining processes
pkill -f "celery.*worker" 2>/dev/null || true
pkill -f "celery.*beat" 2>/dev/null || true

echo ""
print_status "All services stopped"
echo ""
