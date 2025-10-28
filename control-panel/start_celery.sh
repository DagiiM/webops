#!/bin/bash

# WebOps Celery Worker Startup Script
# This script starts the Celery worker for the WebOps control panel
# Author: Douglas Mutethia
# Reference: Project refinement proposal - Step 1

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
VENV_DIR="$PROJECT_DIR/venv"
CELERY_APP="config.celery_app"
LOG_LEVEL="info"
CONCURRENCY=4
PIDFILE="/tmp/celery_webops.pid"
LOGFILE="/tmp/celery_webops.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Celery worker is already running
check_worker_status() {
    if [ -f "$PIDFILE" ]; then
        local pid=$(cat "$PIDFILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Worker is running
        else
            rm -f "$PIDFILE"  # Remove stale PID file
            return 1  # Worker is not running
        fi
    else
        return 1  # PID file doesn't exist
    fi
}

# Function to start Celery worker
start_worker() {
    print_status "Starting Celery worker for WebOps..."
    
    # Ensure any existing worker is stopped
    stop_worker

    # Check if already running
    if check_worker_status; then
        print_warning "Celery worker is already running (PID: $(cat $PIDFILE))"
        return 0
    fi
    
    # Activate virtual environment
    if [ -f "$VENV_DIR/bin/activate" ]; then
        print_status "Activating virtual environment..."
        source "$VENV_DIR/bin/activate"
    else
        print_error "Virtual environment not found at $VENV_DIR"
        exit 1
    fi
    
    # Change to project directory
    cd "$PROJECT_DIR"
    
    # Check if Redis is running
    print_status "Checking Redis connection..."
    if ! python -c "import redis; r = redis.Redis(); r.ping()" 2>/dev/null; then
        print_error "Redis is not running or not accessible"
        print_error "Please start Redis server before starting Celery worker"
        exit 1
    fi
    
    print_status "Redis connection successful"
    
    # Start Celery worker in background
    print_status "Starting Celery worker with the following configuration:"
    print_status "  - App: $CELERY_APP"
    print_status "  - Log level: $LOG_LEVEL"
    print_status "  - Concurrency: $CONCURRENCY"
    print_status "  - PID file: $PIDFILE"
    print_status "  - Log file: $LOGFILE"
    
    nohup python -m celery -A "$CELERY_APP" worker \
        --loglevel="$LOG_LEVEL" \
        --concurrency="$CONCURRENCY" \
        --pidfile="$PIDFILE" \
        --logfile="$LOGFILE" \
        --detach > "$LOGFILE" 2>&1
    
    # Wait a moment and check if worker started successfully
    sleep 2
    if check_worker_status; then
        print_status "Celery worker started successfully (PID: $(cat $PIDFILE))"
        print_status "Log file: $LOGFILE"
    else
        print_error "Failed to start Celery worker"
        print_error "Check the log file for details: $LOGFILE"
        exit 1
    fi
}

# Function to stop Celery worker
stop_worker() {
    print_status "Stopping Celery worker..."
    
    if check_worker_status; then
        local pid=$(cat "$PIDFILE")
        print_status "Stopping worker with PID: $pid"
        
        # Send TERM signal first
        kill -TERM "$pid" 2>/dev/null || true
        
        # Wait for graceful shutdown
        local count=0
        while [ $count -lt 10 ] && ps -p "$pid" > /dev/null 2>&1; do
            sleep 1
            count=$((count + 1))
        done
        
        # Force kill if still running
        if ps -p "$pid" > /dev/null 2>&1; then
            print_warning "Worker didn't stop gracefully, forcing shutdown..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
        
        rm -f "$PIDFILE"
        print_status "Celery worker stopped"
    else
        print_warning "Celery worker is not running"
    fi
}

# Function to restart Celery worker
restart_worker() {
    print_status "Restarting Celery worker..."
    stop_worker
    sleep 2
    start_worker
}

# Function to show worker status
status_worker() {
    if check_worker_status; then
        local pid=$(cat "$PIDFILE")
        print_status "Celery worker is running (PID: $pid)"
        
        # Show worker info using celery inspect
        if command -v python >/dev/null 2>&1; then
            cd "$PROJECT_DIR"
            if [ -f "$VENV_DIR/bin/activate" ]; then
                source "$VENV_DIR/bin/activate"
            fi
            
            echo ""
            print_status "Worker details:"
            python -m celery -A "$CELERY_APP" inspect active 2>/dev/null || true
        fi
    else
        print_warning "Celery worker is not running"
        return 1
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$LOGFILE" ]; then
        print_status "Showing Celery worker logs (last 50 lines):"
        echo ""
        tail -n 50 "$LOGFILE"
    else
        print_warning "Log file not found: $LOGFILE"
    fi
}

# Main script logic
case "${1:-start}" in
    start)
        start_worker
        ;;
    stop)
        stop_worker
        ;;
    restart)
        restart_worker
        ;;
    status)
        status_worker
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the Celery worker"
        echo "  stop    - Stop the Celery worker"
        echo "  restart - Restart the Celery worker"
        echo "  status  - Show worker status"
        echo "  logs    - Show recent worker logs"
        exit 1
        ;;
esac