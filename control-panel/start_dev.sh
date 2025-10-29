#!/bin/bash

# WebOps Development Server Startup Script
# Starts both Django development server and Celery worker together
# Author: WebOps Team

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
VENV_DIR="$PROJECT_DIR/venv"
CELERY_PIDFILE="/tmp/celery_webops.pid"
CELERY_LOGFILE="/tmp/celery_webops.log"
BEAT_PIDFILE="/tmp/celery_beat.pid"
DAPHNE_LOGFILE="/tmp/daphne_webops.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  WebOps Development Environment${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Cleanup function to stop all services
cleanup() {
    echo ""
    print_info "Shutting down services..."

    # Stop Celery worker
    if [ -f "$CELERY_PIDFILE" ]; then
        local worker_pid=$(cat "$CELERY_PIDFILE")
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
        local beat_pid=$(cat "$BEAT_PIDFILE")
        if kill -0 "$beat_pid" 2>/dev/null; then
            print_info "Stopping Celery Beat (PID: $beat_pid)..."
            kill -TERM "$beat_pid" 2>/dev/null || true
            sleep 2
            kill -KILL "$beat_pid" 2>/dev/null || true
        fi
        rm -f "$BEAT_PIDFILE"
    fi

    # Kill any remaining Celery processes
    pkill -f "celery.*worker" 2>/dev/null || true
    pkill -f "celery.*beat" 2>/dev/null || true

    print_status "All services stopped"
    exit 0
}

# Register cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found at $VENV_DIR"
    print_info "Please run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

cd "$PROJECT_DIR"

print_header

# Check Redis connection
print_info "Checking Redis connection..."
if python -c "import redis; r = redis.Redis(); r.ping()" 2>/dev/null; then
    print_status "Redis is running"
else
    print_warning "Redis is not running or not accessible"
    print_info "Celery background tasks will not work without Redis"
    print_info "To start Redis: sudo service redis-server start"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for existing Celery workers and clean them up
print_info "Checking for existing workers..."
if pgrep -f "celery.*worker" > /dev/null; then
    print_warning "Found existing Celery workers, cleaning up..."
    pkill -9 -f "celery.*worker" 2>/dev/null || true
    pkill -9 -f "celery.*beat" 2>/dev/null || true
    rm -f "$CELERY_PIDFILE" "$BEAT_PIDFILE"
    sleep 1
fi


# Start Celery Worker in background
print_info "Starting Celery worker..."
python -m celery -A config.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --pidfile="$CELERY_PIDFILE" \
    --logfile="$CELERY_LOGFILE" &

CELERY_WORKER_PID=$!
sleep 2

if kill -0 "$CELERY_WORKER_PID" 2>/dev/null; then
    echo "$CELERY_WORKER_PID" > "$CELERY_PIDFILE"
    print_status "Celery worker started (PID: $CELERY_WORKER_PID)"
    print_info "Celery logs: $CELERY_LOGFILE"
else
    print_error "Failed to start Celery worker"
    exit 1
fi

# Start Celery Beat in background
print_info "Starting Celery Beat scheduler..."
python -m celery -A config.celery_app beat \
    --loglevel=info \
    --pidfile="$BEAT_PIDFILE" &

CELERY_BEAT_PID=$!
sleep 2

if kill -0 "$CELERY_BEAT_PID" 2>/dev/null; then
    echo "$CELERY_BEAT_PID" > "$BEAT_PIDFILE"
    print_status "Celery Beat started (PID: $CELERY_BEAT_PID)"
else
    print_warning "Failed to start Celery Beat (optional service)"
fi

echo ""
print_status "Background services started successfully!"
echo ""
print_info "Starting Daphne ASGI server on port 8008..."
print_info "Daphne handles both HTTP and WebSocket connections"
print_info "Press Ctrl+C to stop all services"
echo ""

# Start Daphne ASGI server (this will run in foreground)
# Daphne handles both HTTP and WebSocket traffic on the same port
python -m daphne \
    -b 0.0.0.0 \
    -p "${1:-8008}" \
    config.asgi:application \
    --access-log "$DAPHNE_LOGFILE" \
    --verbosity 1

# Cleanup will be called automatically via trap when the script exits
