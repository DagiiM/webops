#!/bin/bash
#
# WebOps VPS Setup Script
# Transforms a fresh Ubuntu/Debian VPS into a complete hosting platform
#
# Usage: sudo ./setup.sh
#
# This script implements best practices from docs/edge_cases.md

set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly WEBOPS_USER="webops"
readonly WEBOPS_DIR="${WEBOPS_DIR:-/opt/webops}"
readonly CONTROL_PANEL_DIR="${WEBOPS_DIR}/control-panel"
readonly DEPLOYMENTS_DIR="${WEBOPS_DIR}/deployments"
readonly SHARED_DIR="${WEBOPS_DIR}/shared"
readonly BACKUPS_DIR="${WEBOPS_DIR}/backups"
readonly LOGS_DIR="${WEBOPS_DIR}/logs"

# Python version
readonly PYTHON_VERSION_DEFAULT="3.11"
# By default we will NOT install Python. Use --install-python to enable.
PYTHON_VERSION="${PYTHON_VERSION_DEFAULT}"
INSTALL_PYTHON=false

# Automation flags (can be set via CLI)
AUTO_YES=false
AUTO_DRYRUN_PYTHON=false
AUTO_APPLY_PYTHON=false
RECOMMEND_ONLY=false

# PostgreSQL version
readonly POSTGRES_VERSION="14"

#=============================================================================
# Logging Functions
#=============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}
usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --yes, -y               Assume yes for prompts (non-interactive)
  --auto-dryrun-python    Automatically run the python helper in dry-run mode
  --auto-apply-python     Automatically apply the python default change (requires sudo)
  --recommend-only        Only print and run the recommendation helper, then exit
  --help, -h              Show this help message
EOF
}

parse_cli_args() {
    # Basic CLI arg parsing for automation flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                AUTO_YES=true
                shift
                ;;
            --auto-dryrun-python)
                AUTO_DRYRUN_PYTHON=true
                shift
                ;;
            --auto-apply-python)
                AUTO_APPLY_PYTHON=true
                shift
                ;;
            --install-python)
                INSTALL_PYTHON=true
                shift
                ;;
            --python-version)
                if [[ -n ${2:-} ]]; then
                    PYTHON_VERSION="$2"
                    shift 2
                else
                    log_warn "--python-version requires an argument"
                    shift
                fi
                ;;
            --recommend-only)
                RECOMMEND_ONLY=true
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            --*)
                log_warn "Unknown option: $1"
                shift
                ;;
            *)
                # positional args not used currently
                shift
                ;;
        esac
    done
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

#=============================================================================
# Cleanup Handler
#=============================================================================

cleanup_on_failure() {
#    Clean up on installation failure to leave system in known state.
    log_error "Installation failed! Cleaning up..."

    # Stop WebOps services if they were created
    log_info "Stopping WebOps services..."
    systemctl stop webops-web 2>/dev/null || true
    systemctl stop webops-celery 2>/dev/null || true
    systemctl stop webops-celerybeat 2>/dev/null || true

    # Disable services
    systemctl disable webops-web 2>/dev/null || true
    systemctl disable webops-celery 2>/dev/null || true
    systemctl disable webops-celerybeat 2>/dev/null || true

    # Remove systemd service files
    log_info "Removing systemd service files..."
    rm -f /etc/systemd/system/webops-web.service
    rm -f /etc/systemd/system/webops-celery.service
    rm -f /etc/systemd/system/webops-celerybeat.service
    systemctl daemon-reload

    # Remove Nginx configuration
    log_info "Removing Nginx configuration..."
    rm -f /etc/nginx/sites-enabled/webops-panel.conf
    rm -f /etc/nginx/sites-available/webops-panel.conf
    nginx -t &>/dev/null && systemctl reload nginx 2>/dev/null || true

    # Keep /opt/webops directory for debugging
    log_warn "Installation directory /opt/webops kept for debugging"
    log_warn "To completely remove: sudo rm -rf /opt/webops"

    # Keep PostgreSQL database and user for debugging
    log_warn "PostgreSQL database and user kept for debugging"
    log_warn "To remove: sudo -u postgres psql -c 'DROP DATABASE webops_control_panel;'"
    log_warn "          sudo -u postgres psql -c 'DROP USER webops;'"

    log_error "Cleanup complete. Please review the error messages above."
    log_error "Installation logs may contain additional information."

    exit 1
}

#=============================================================================
# Validation Functions
#=============================================================================

check_root() {
#    Check if script is running as root.
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    log_info "Running as root ✓"
}

check_os() {
#    Check if running on supported OS.
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot detect OS. Only Ubuntu 22.04+ and Debian 11+ are supported."
        exit 1
    fi

    source /etc/os-release

    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        log_error "Unsupported OS: $ID. Only Ubuntu and Debian are supported."
        exit 1
    fi

    log_info "Operating System: $PRETTY_NAME ✓"
}

check_resources() {
#    Check if system has minimum required resources.
    local total_ram_mb=$(free -m | awk '/^Mem:/{print $2}')
    local cpu_cores=$(nproc)
    local disk_gb=$(df -BG / | awk 'NR==2 {print $2}' | sed 's/G//')

    log_info "System Resources:"
    log_info "  RAM: ${total_ram_mb}MB"
    log_info "  CPU Cores: ${cpu_cores}"
    log_info "  Disk: ${disk_gb}GB"

    if [[ $total_ram_mb -lt 2048 ]]; then
        log_warn "Less than 2GB RAM detected. Minimum 2GB recommended."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    if [[ $cpu_cores -lt 2 ]]; then
        log_warn "Less than 2 CPU cores detected. Performance may be limited."
    fi

    if [[ $disk_gb -lt 10 ]]; then
        log_error "Less than 10GB disk space. Minimum 10GB required."
        exit 1
    fi
}

check_internet_connectivity() {
#    Check if server has internet access.
    log_step "Checking internet connectivity..."

    if ping -c 1 -W 5 8.8.8.8 &> /dev/null; then
        log_info "Internet connectivity: OK ✓"
        return 0
    else
        log_error "No internet connectivity. Cannot proceed with installation."
        log_error "Please check your network configuration and try again."
        exit 1
    fi
}

check_dns_resolution() {
#    Check if DNS resolution works.
    log_step "Checking DNS resolution..."

    if host -W 5 github.com &> /dev/null || host -W 5 google.com &> /dev/null; then
        log_info "DNS resolution: OK ✓"
        return 0
    else
        log_warn "DNS resolution issues detected. This may cause problems."
        log_warn "Attempting to continue anyway..."
        return 0
    fi
}

check_package_manager() {
#    Verify apt-get is installed.
    log_step "Checking package manager..."

    if ! command -v apt-get &> /dev/null; then
        log_error "apt-get not found. This script requires Ubuntu/Debian."
        exit 1
    fi

    if ! command -v dpkg &> /dev/null; then
        log_error "dpkg not found. This script requires Ubuntu/Debian."
        exit 1
    fi

    log_info "Package manager: OK ✓"
    log_warn "Note: Repository updates will be performed in the next step"
}

ensure_python3_present_or_fail() {
    # When install is skipped, ensure python3 exists on the system.
    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found in PATH. The installer was configured to skip Python installation."
        log_error "Either install Python3 manually or run setup.sh with --install-python"
        exit 1
    else
        log_info "python3 detected: $(python3 --version 2>&1 | head -1)"
    fi
}

#=============================================================================
# Recommendations / Post-install prompts
#=============================================================================
recommend_python_default() {
    # Inform the operator about the recommended approach to setting the system 'python'
    log_step "Python default recommendation"

    cat <<-EOF
It is recommended to avoid changing the system 'python' global unless you
understand the implications. Many system utilities expect 'python3' to be
available but not necessarily 'python' pointing to a specific version.

This setup prefers using 'python3' and registers the requested Python with
the alternatives system. If you want to change the global 'python' to
point to the installed ${PYTHON_VERSION}, you can run the helper script that
attempts to do this safely.

Helper script: scripts/set-default-python.sh

You can run a dry-run to see what would change:
  ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run

Or run with sudo to apply the change system-wide:
  sudo ./scripts/set-default-python.sh ${PYTHON_VERSION}

If you rely on system packages, use 'python3' or a virtual environment
instead of changing the global 'python'.
EOF

    # Non-interactive automation support
    if [[ "$AUTO_APPLY_PYTHON" == true ]]; then
        log_info "AUTO_APPLY_PYTHON enabled: applying python default automatically"
        if [[ -x "./scripts/set-default-python.sh" ]]; then
            if ! command -v sudo &> /dev/null; then
                log_error "sudo command not available but required for auto-apply. Aborting auto-apply."
                return 2
            fi
            if ! sudo -n true 2>/dev/null; then
                log_warn "sudo will prompt for a password. Running auto-apply may block or fail in non-interactive environments."
            fi
            sudo ./scripts/set-default-python.sh ${PYTHON_VERSION} || { log_error "Auto-apply failed"; return 3; }
        else
            log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
            return 4
        fi
        return
    fi

    if [[ "$AUTO_DRYRUN_PYTHON" == true ]]; then
        log_info "AUTO_DRYRUN_PYTHON enabled: running helper dry-run"
        if [[ -x "./scripts/set-default-python.sh" ]]; then
            ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run || true
        else
            log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
        fi
        return
    fi

    # Offer interactive prompt only if not in automation mode
    if [[ -t 0 && "$AUTO_YES" != true ]]; then
        read -p "Run helper dry-run now? (Y/n) " -r
        echo
        if [[ -z "$REPLY" || "$REPLY" =~ ^[Yy] ]]; then
            if [[ -x "./scripts/set-default-python.sh" ]]; then
                ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run || true
            else
                log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
            fi
        fi
    elif [[ "$AUTO_YES" == true ]]; then
        log_info "AUTO_YES enabled: skipping prompt and running dry-run"
        if [[ -x "./scripts/set-default-python.sh" ]]; then
            ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run || true
        else
            log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
        fi
    else
        log_info "Non-interactive shell: skipping helper dry-run prompt."
    fi
}

check_existing_services() {
#    Check for port conflicts.
    log_step "Checking for port conflicts..."

    local conflicts=0

    # Check critical ports
    if ss -tlnp | grep -q ":80 "; then
        log_warn "Port 80 (HTTP) is already in use"
        conflicts=$((conflicts + 1))
    fi

    if ss -tlnp | grep -q ":443 "; then
        log_warn "Port 443 (HTTPS) is already in use"
        conflicts=$((conflicts + 1))
    fi

    if ss -tlnp | grep -q ":8000 "; then
        log_warn "Port 8000 (Control Panel) is already in use"
        conflicts=$((conflicts + 1))
    fi

    if [[ $conflicts -gt 0 ]]; then
        log_warn "Found $conflicts port conflict(s). Existing services may conflict with WebOps."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_info "No port conflicts detected ✓"
    fi
}

check_disk_io() {
#    Verify disk write capability.
    log_step "Checking disk I/O..."

    local test_file="/tmp/webops_io_test_$$"

    if echo "test" > "$test_file" 2>/dev/null; then
        rm -f "$test_file"
        log_info "Disk I/O: OK ✓"
    else
        log_error "Cannot write to /tmp. Check disk permissions."
        exit 1
    fi
}

#=============================================================================
# Package Installation
#=============================================================================

install_with_retry() {
#    Install packages with retry logic and error handling.
    local packages="$1"
    local max_attempts=3
    local attempt=1
    local wait_time=5

    log_step "Installing packages with retry support..."

    while [[ $attempt -le $max_attempts ]]; do
        log_info "Attempt $attempt/$max_attempts: Installing $packages"

        if apt-get install -y -qq $packages 2>&1; then
            log_info "Packages installed successfully ✓"
            return 0
        else
            log_warn "Installation attempt $attempt failed"

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Waiting ${wait_time}s before retry..."
                sleep $wait_time

                # Try to fix broken packages
                log_info "Attempting to fix broken packages..."
                dpkg --configure -a 2>/dev/null || true
                apt-get install -f -y -qq 2>/dev/null || true

                # Update package lists
                apt-get update -qq

                # Exponential backoff
                wait_time=$((wait_time * 2))
                attempt=$((attempt + 1))
            else
                log_error "Failed to install packages after $max_attempts attempts"
                log_error "Packages: $packages"
                return 1
            fi
        fi
    done
}

validate_command() {
#    Validate that a command exists and is executable.
    local command=$1
    local package=$2

    if command -v "$command" &> /dev/null; then
        local version=$("$command" --version 2>&1 | head -1 || echo "version unknown")
        log_info "$package: $version ✓"
        return 0
    else
        log_error "$package command '$command' not found after installation"
        return 1
    fi
}

update_system() {
    log_step "Updating system packages..."
    export DEBIAN_FRONTEND=noninteractive

    # Suppress warnings for Ubuntu Pro services that may not be available
    apt-get update -qq 2>&1 | grep -v "Failed to start apt-news.service\|Failed to start esm-cache.service" || true
    apt-get upgrade -y -qq 2>&1 | grep -v "Failed to start apt-news.service\|Failed to start esm-cache.service" || true
    apt-get install -y -qq \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common

    log_info "System updated ✓"
}

# Ensure Python venv/ensurepip is available; auto-install if missing
ensure_python_venv_available() {
    log_step "Checking Python venv/ensurepip availability..."

    if python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
        log_info "Python venv and ensurepip available ✓"
        return 0
    fi

    log_warn "Python venv/ensurepip missing; installing python3-venv package..."

    # Determine installed Python3 minor version (e.g., 3.11, 3.12)
    local py_minor
    py_minor=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

    # Try generic package first, then version-specific as fallback
    install_with_retry "python3-venv" || true
    install_with_retry "python3.${py_minor}-venv" || true

    # Re-check
    if python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
        log_info "Python venv/ensurepip installed ✓"
        return 0
    else
        log_error "python3-venv installation failed; cannot create virtual environment"
        exit 1
    fi
}

install_python() {
    log_step "Installing Python ${PYTHON_VERSION}..."

    # Add deadsnakes PPA for Ubuntu (latest Python versions)
    if [[ "$ID" == "ubuntu" ]]; then
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq 2>&1 | grep -v "Failed to start apt-news.service\|Failed to start esm-cache.service" || true
    fi

    apt-get install -y -qq \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python${PYTHON_VERSION}-dev \
        python3-pip \
        build-essential

    # Set python3 to point to our version
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

    log_info "Python $(python3 --version) installed ✓"
}

install_postgresql() {
    log_step "Installing PostgreSQL ${POSTGRES_VERSION}..."

    # Add PostgreSQL repository
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list

    apt-get update -qq 2>&1 | grep -v "Failed to start apt-news.service\|Failed to start esm-cache.service" || true
    apt-get install -y -qq \
        postgresql-${POSTGRES_VERSION} \
        postgresql-contrib-${POSTGRES_VERSION} \
        postgresql-server-dev-${POSTGRES_VERSION} \
        libpq-dev

    # Start PostgreSQL
    systemctl enable postgresql
    systemctl start postgresql

    log_info "PostgreSQL ${POSTGRES_VERSION} installed ✓"
}

install_redis() {
    log_step "Installing Redis..."

    apt-get install -y -qq redis-server

    # Configure Redis for production
    sed -i 's/^supervised no/supervised systemd/' /etc/redis/redis.conf
    sed -i 's/^# maxmemory <bytes>/maxmemory 256mb/' /etc/redis/redis.conf
    sed -i 's/^# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf

    systemctl enable redis-server
    systemctl restart redis-server

    log_info "Redis installed ✓"
}

install_nginx() {
    log_step "Installing Nginx..."

    apt-get install -y -qq nginx

    # Remove default site
    rm -f /etc/nginx/sites-enabled/default

    systemctl enable nginx
    systemctl start nginx

    log_info "Nginx installed ✓"
}

install_certbot() {
    log_step "Installing Certbot (Let's Encrypt)..."

    apt-get install -y -qq \
        certbot \
        python3-certbot-nginx

    log_info "Certbot installed ✓"
}

install_system_dependencies() {
    log_step "Installing system dependencies..."

    # Common dependencies for Python packages
    apt-get install -y -qq \
        git \
        supervisor \
        logrotate \
        ufw \
        fail2ban \
        htop \
        vim \
        wget \
        unzip \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        libmysqlclient-dev

    log_info "System dependencies installed ✓"
}

#=============================================================================
# Service Health Verification
#=============================================================================

verify_postgresql() {
#    Verify PostgreSQL is running and accepting connections.
    log_step "Verifying PostgreSQL service..."

    local max_attempts=5
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        # Check systemd status
        if ! systemctl is-active --quiet postgresql; then
            log_warn "PostgreSQL not active (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Waiting 5s before retry..."
                sleep 5
                systemctl restart postgresql
                attempt=$((attempt + 1))
                continue
            else
                log_error "PostgreSQL failed to start after $max_attempts attempts"
                return 1
            fi
        fi

        # Test connection
        if sudo -u postgres psql -c "SELECT 1;" &> /dev/null; then
            log_info "PostgreSQL: Service running and accepting connections ✓"

            # Check port
            if ss -tlnp | grep -q ":5432"; then
                log_info "PostgreSQL: Port 5432 listening ✓"
            fi

            return 0
        else
            log_warn "PostgreSQL not accepting connections (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                sleep 5
                attempt=$((attempt + 1))
            else
                log_error "PostgreSQL not responding after $max_attempts attempts"
                return 1
            fi
        fi
    done
}

verify_redis() {
#    Verify Redis is running and accepting commands.
    log_step "Verifying Redis service..."

    local max_attempts=5
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        # Check systemd status
        if ! systemctl is-active --quiet redis-server; then
            log_warn "Redis not active (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Waiting 5s before retry..."
                sleep 5
                systemctl restart redis-server
                attempt=$((attempt + 1))
                continue
            else
                log_error "Redis failed to start after $max_attempts attempts"
                return 1
            fi
        fi

        # Test PING command
        if redis-cli ping 2>&1 | grep -q "PONG"; then
            log_info "Redis: Service running and responding to PING ✓"

            # Test SET/GET
            if redis-cli set webops_test "ok" &> /dev/null && \
               redis-cli get webops_test 2>&1 | grep -q "ok"; then
                redis-cli del webops_test &> /dev/null
                log_info "Redis: SET/GET operations working ✓"
            fi

            # Check port
            if ss -tlnp | grep -q ":6379"; then
                log_info "Redis: Port 6379 listening ✓"
            fi

            return 0
        else
            log_warn "Redis not responding (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                sleep 5
                attempt=$((attempt + 1))
            else
                log_error "Redis not responding after $max_attempts attempts"
                return 1
            fi
        fi
    done
}

verify_nginx() {
#    Verify Nginx is running with valid configuration.
    log_step "Verifying Nginx service..."

    local max_attempts=5
    local attempt=1

    # First check config syntax
    if ! nginx -t &> /dev/null; then
        log_error "Nginx configuration test failed"
        nginx -t
        return 1
    fi
    log_info "Nginx: Configuration valid ✓"

    while [[ $attempt -le $max_attempts ]]; do
        # Check systemd status
        if ! systemctl is-active --quiet nginx; then
            log_warn "Nginx not active (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Waiting 5s before retry..."
                sleep 5
                systemctl restart nginx
                attempt=$((attempt + 1))
                continue
            else
                log_error "Nginx failed to start after $max_attempts attempts"
                return 1
            fi
        fi

        # Check port 80
        if ss -tlnp | grep -q ":80 "; then
            log_info "Nginx: Port 80 listening ✓"
        else
            log_warn "Nginx: Port 80 not listening"
        fi

        # Test HTTP request
        if curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -qE "^(200|301|302|404)"; then
            log_info "Nginx: Responding to HTTP requests ✓"
            return 0
        else
            log_warn "Nginx not responding to HTTP (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                sleep 5
                attempt=$((attempt + 1))
            else
                log_error "Nginx not responding after $max_attempts attempts"
                return 1
            fi
        fi
    done
}

verify_celery() {
    # Verify Celery worker is running and processing tasks.
    log_step "Verifying Celery worker..."

    # Allow more time for Celery to initialize properly
    local max_attempts=3
    local attempt=1
    local initial_wait=20
    local retry_wait=15

    # Give Celery time to start up initially
    log_info "Allowing ${initial_wait}s for Celery worker initialization..."
    sleep $initial_wait

    while [[ $attempt -le $max_attempts ]]; do
        log_info "Verification attempt $attempt/$max_attempts"

        # Check systemd status first
        if ! systemctl is-active --quiet webops-celery; then
            log_warn "Celery worker service not active"
            
            # Show service status for debugging
            log_info "Service status:"
            systemctl status webops-celery --no-pager -l | head -10 | sed 's/^/  /'
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Restarting Celery service..."
                systemctl restart webops-celery
                log_info "Waiting ${retry_wait}s for service to stabilize..."
                sleep $retry_wait
                attempt=$((attempt + 1))
                continue
            else
                log_error "Celery worker service failed to start after $max_attempts attempts"
                log_error "Full service status:"
                systemctl status webops-celery --no-pager -l
                return 1
            fi
        fi

        log_info "Celery service is active ✓"

        # Check if process is actually running
        local celery_pid
        celery_pid=$(pgrep -u "$WEBOPS_USER" -f "celery.*worker" | head -1)
        
        if [[ -z "$celery_pid" ]]; then
            log_warn "Celery worker process not found"
            
            # Check recent logs for startup issues
            log_info "Recent systemd logs:"
            journalctl -u webops-celery --since "1 minute ago" --no-pager | grep -v "CPendingDeprecationWarning" | tail -5 | sed 's/^/  /'
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Restarting Celery worker..."
                systemctl restart webops-celery
                sleep $retry_wait
                attempt=$((attempt + 1))
                continue
            else
                log_error "Celery worker process not running after $max_attempts attempts"
                log_error "Check full logs: journalctl -u webops-celery -n 50"
                return 1
            fi
        fi

        log_info "Celery worker process running (PID: $celery_pid) ✓"

        # Test worker responsiveness with better error handling
        log_info "Testing Celery worker responsiveness..."
        
        # Set environment variables to suppress warnings and ensure proper Django loading
        local celery_env="PYTHONWARNINGS=ignore::DeprecationWarning CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=true DJANGO_SETTINGS_MODULE=config.settings"
        
        local ping_output
        ping_output=$(timeout 20 sudo -u "$WEBOPS_USER" bash -c "cd '$CONTROL_PANEL_DIR' && $celery_env '$CONTROL_PANEL_DIR/venv/bin/celery' -A config.celery_app inspect ping" 2>&1)
        local ping_exit_code=$?
        
        # Filter out warnings and check for success
        local filtered_output
        filtered_output=$(echo "$ping_output" | grep -v -E "(CPendingDeprecationWarning|DeprecationWarning|PendingDeprecationWarning)")
        
        if [[ $ping_exit_code -eq 0 ]] && echo "$filtered_output" | grep -q "pong"; then
            log_info "Celery worker responded to ping ✓"
            
            # Verify worker has registered tasks
            log_info "Checking registered tasks..."
            local tasks_output
            tasks_output=$(timeout 15 sudo -u "$WEBOPS_USER" bash -c "cd '$CONTROL_PANEL_DIR' && $celery_env '$CONTROL_PANEL_DIR/venv/bin/celery' -A config.celery_app inspect registered" 2>&1)
            local tasks_exit_code=$?
            
            if [[ $tasks_exit_code -eq 0 ]]; then
                local task_count
                task_count=$(echo "$tasks_output" | grep -c "apps\." 2>/dev/null || echo "0")
                if [[ $task_count -gt 0 ]]; then
                    log_info "Celery worker has $task_count registered tasks ✓"
                else
                    log_warn "No tasks registered, but worker is responsive"
                fi
            else
                log_warn "Could not check registered tasks, but worker is responsive"
            fi
            
            log_info "Celery worker verification successful ✓"
            return 0
        else
            log_warn "Celery worker ping failed (attempt $attempt/$max_attempts)"
            
            # Show diagnostic information
            if [[ $ping_exit_code -eq 124 ]]; then
                log_warn "Ping command timed out - worker may be overloaded"
            elif [[ $ping_exit_code -ne 0 ]]; then
                log_warn "Ping command failed with exit code: $ping_exit_code"
            fi
            
            # Show filtered output for debugging
            if [[ -n "$filtered_output" ]]; then
                log_info "Ping output (filtered):"
                echo "$filtered_output" | head -3 | sed 's/^/  /'
            fi

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Restarting Celery worker for retry..."
                systemctl restart webops-celery
                sleep $retry_wait
                attempt=$((attempt + 1))
            else
                log_error "Celery worker not responding after $max_attempts attempts"
                log_error "Final diagnostics:"
                log_error "- Service status: $(systemctl is-active webops-celery)"
                log_error "- Process count: $(pgrep -u "$WEBOPS_USER" -f "celery.*worker" | wc -l)"
                log_error "- Check detailed logs: journalctl -u webops-celery -n 100"
                
                # Show recent error logs
                if [[ -f "$LOGS_DIR/celery-worker.log" ]]; then
                    log_error "Recent worker log entries (filtered):"
                    tail -10 "$LOGS_DIR/celery-worker.log" | grep -v -E "(CPendingDeprecationWarning|DeprecationWarning)" | sed 's/^/  /'
                fi
                
                return 1
            fi
        fi
    done
}

#=============================================================================
# User and Directory Setup
#=============================================================================

create_webops_user() {
    log_step "Creating WebOps system user..."

    if id "$WEBOPS_USER" &>/dev/null; then
        log_warn "User $WEBOPS_USER already exists"
    else
        # Create system user with bash shell for running deployment tasks
        useradd -r -m -d "$WEBOPS_DIR" -s /bin/bash "$WEBOPS_USER"
        log_info "User $WEBOPS_USER created ✓"
    fi

    # Add to necessary groups
    log_info "Adding $WEBOPS_USER to required groups..."

    # Add to www-data group for nginx interaction
    usermod -a -G www-data "$WEBOPS_USER"
    
    # Add www-data user to webops group for static file access
    usermod -a -G "$WEBOPS_USER" www-data

    # Add to postgres group for database operations (if postgres is installed)
    if getent group postgres >/dev/null 2>&1; then
        usermod -a -G postgres "$WEBOPS_USER"
    fi

    log_info "User groups configured ✓"
}

create_directory_structure() {
    log_step "Creating directory structure..."

    mkdir -p "$CONTROL_PANEL_DIR"/{logs,static,media,tmp}
    mkdir -p "$DEPLOYMENTS_DIR"
    mkdir -p "$SHARED_DIR"
    mkdir -p "$BACKUPS_DIR"/{postgres,control-panel,deployments}
    mkdir -p "$LOGS_DIR"
    mkdir -p "$WEBOPS_DIR/.secrets"

    # Set ownership
    chown -R "$WEBOPS_USER:$WEBOPS_USER" "$WEBOPS_DIR"

    # Set permissions
    chmod 750 "$WEBOPS_DIR"
    chmod 755 "$CONTROL_PANEL_DIR"  # Changed from 750 to 755 to allow installer user to read/traverse
    chmod 750 "$DEPLOYMENTS_DIR"
    chmod 755 "$SHARED_DIR"
    chmod 700 "$BACKUPS_DIR"
    chmod 700 "$WEBOPS_DIR/.secrets"
    chmod 1777 "$CONTROL_PANEL_DIR/tmp"  # Sticky bit for temp directory

    log_info "Directory structure created ✓"
}

configure_sudo_access() {
    log_step "Configuring limited sudo access for deployments..."

    # Create sudoers file for webops user
    # This allows specific commands needed for deployment operations
    cat > /etc/sudoers.d/webops <<EOF
# WebOps user - limited sudo access for deployment tasks
# This file is managed by WebOps setup.sh
Defaults:$WEBOPS_USER !requiretty

# Allow nginx reload/restart (for new site configurations)
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl reload nginx
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl restart nginx
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/nginx -t

# Allow systemd service management for WebOps services
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl start webops-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl stop webops-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl restart webops-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl reload webops-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl enable webops-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl disable webops-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl status webops-*

# Allow systemd service management for deployed apps (app-*)
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl start app-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl stop app-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl restart app-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl reload app-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl enable app-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl disable app-*
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl status app-*

# Allow systemd daemon-reload (after creating new service files)
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl daemon-reload

# Allow copying service files to systemd directory
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/cp /opt/webops/deployments/*/systemd/app-*.service /etc/systemd/system/

# Allow copying nginx configurations
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/cp /opt/webops/deployments/*/nginx/webops-*.conf /etc/nginx/sites-available/
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/ln -sf /etc/nginx/sites-available/webops-*.conf /etc/nginx/sites-enabled/
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/rm -f /etc/nginx/sites-enabled/webops-*.conf

# Allow certbot for SSL certificate management
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/certbot certonly *
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/certbot renew *
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/certbot delete *
EOF

    # Set correct permissions on sudoers file (must be 0440)
    chmod 0440 /etc/sudoers.d/webops

    # Validate sudoers syntax
    if visudo -c -f /etc/sudoers.d/webops >/dev/null 2>&1; then
        log_info "Sudo configuration validated ✓"
    else
        log_error "Invalid sudoers configuration detected!"
        log_error "Removing invalid sudoers file for safety..."
        rm -f /etc/sudoers.d/webops
        exit 1
    fi

    log_info "Sudo access configured ✓"
}

#=============================================================================
# Database Setup
#=============================================================================

setup_postgresql() {
    log_step "Configuring PostgreSQL..."

    # Create secrets directory
    local SECRETS_DIR="/opt/webops/.secrets"
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"

    # Password file
    local PG_PASS_FILE="$SECRETS_DIR/postgres_password"

    # Generate or load password
    if [[ -f "$PG_PASS_FILE" ]]; then
        PG_PASSWORD=$(cat "$PG_PASS_FILE")
        log_info "Using existing PostgreSQL password from $PG_PASS_FILE"
    else
        PG_PASSWORD=$(openssl rand -base64 32)
        echo "$PG_PASSWORD" > "$PG_PASS_FILE"
        chmod 600 "$PG_PASS_FILE"
        log_info "Generated new PostgreSQL password and saved to $PG_PASS_FILE"
    fi

    # Create WebOps database user
    if sudo -u postgres psql -c "\\du" | grep -q "^  *$WEBOPS_USER"; then
        log_warn "PostgreSQL user $WEBOPS_USER already exists"
        # Update password in case it changed
        sudo -u postgres psql -c "ALTER USER $WEBOPS_USER WITH PASSWORD '$PG_PASSWORD';"
    else
        sudo -u postgres psql -c "CREATE USER $WEBOPS_USER WITH PASSWORD '$PG_PASSWORD';"
        log_info "PostgreSQL user $WEBOPS_USER created"
    fi

    # Grant CREATEDB permission
    sudo -u postgres psql -c "ALTER USER $WEBOPS_USER CREATEDB;"

    # Create control panel database
    if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw webops_control_panel; then
        log_warn "Database webops_control_panel already exists"
    else
        sudo -u postgres psql -c "CREATE DATABASE webops_control_panel OWNER $WEBOPS_USER;"
        log_info "Database webops_control_panel created"
    fi

    # Configure PostgreSQL for connections
    PG_HBA="/etc/postgresql/${POSTGRES_VERSION}/main/pg_hba.conf"
    if ! grep -q "# WebOps configuration" "$PG_HBA"; then
        echo "" >> "$PG_HBA"
        echo "# WebOps configuration" >> "$PG_HBA"
        echo "local   all             $WEBOPS_USER                            peer" >> "$PG_HBA"
        echo "host    all             $WEBOPS_USER    127.0.0.1/32            md5" >> "$PG_HBA"
        log_info "PostgreSQL pg_hba.conf configured"
    fi

    # Reload PostgreSQL to apply changes
    systemctl reload postgresql

    # Test connection
    if sudo -u $WEBOPS_USER psql -d webops_control_panel -c "SELECT 1;" &> /dev/null; then
        log_info "PostgreSQL: Test connection successful ✓"
    else
        log_warn "PostgreSQL: Test connection failed (may work with password auth)"
    fi

    log_info "PostgreSQL configured ✓"
}

#=============================================================================
# Security Configuration
#=============================================================================

configure_firewall() {
    log_step "Configuring firewall (UFW)..."

    # Reset UFW to defaults
    ufw --force reset

    # Default policies
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (IMPORTANT!)
    ufw allow 22/tcp comment 'SSH'

    # Allow HTTP and HTTPS
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'

    # Enable firewall
    ufw --force enable

    log_info "Firewall configured ✓"
}

configure_fail2ban() {
    log_step "Configuring Fail2Ban..."

    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
EOF

    systemctl enable fail2ban
    systemctl restart fail2ban

    log_info "Fail2Ban configured ✓"
}

configure_logrotate() {
    log_step "Configuring log rotation..."

    cat > /etc/logrotate.d/webops <<EOF
$LOGS_DIR/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0640 $WEBOPS_USER $WEBOPS_USER
}

$DEPLOYMENTS_DIR/*/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    maxsize 100M
}
EOF

    log_info "Log rotation configured ✓"
}

#=============================================================================
# WebOps Control Panel Installation
#=============================================================================

install_control_panel() {
    log_step "Installing WebOps Control Panel..."

    # Copy control panel code
    if [[ -d "$(pwd)/control-panel" ]]; then
        cp -r "$(pwd)/control-panel"/* "$CONTROL_PANEL_DIR/"
        chown -R "$WEBOPS_USER:$WEBOPS_USER" "$CONTROL_PANEL_DIR"
    else
        log_error "Control panel source not found in $(pwd)/control-panel"
        exit 1
    fi

    # Install system templates with unified structure
    install_system_templates

    # Ensure python3 venv support is available
    ensure_python_venv_available

    # Create virtual environment
    rm -rf "$CONTROL_PANEL_DIR/venv"
    sudo -u "$WEBOPS_USER" python3 -m venv --copies "$CONTROL_PANEL_DIR/venv"
    
    # Ensure virtual environment binaries have proper execute permissions
    chmod -R 755 "$CONTROL_PANEL_DIR/venv/bin"

    # Install Python dependencies (use python -m pip to avoid broken pip shebangs if venv was moved)
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" -m pip install --upgrade pip
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" -m pip install -r "$CONTROL_PANEL_DIR/requirements.txt"

    # Final check on permissions
    chmod -R 755 "$CONTROL_PANEL_DIR/venv/bin"

    log_info "Control panel installed ✓"
    ls -l "$CONTROL_PANEL_DIR/venv/bin" >> "$LOGS_DIR/setup.log"
}

install_system_templates() {
    log_step "Installing system templates with unified structure..."
    
    local SYSTEM_TEMPLATES_DIR="$WEBOPS_DIR/system-templates"
    local BACKUP_DIR="$WEBOPS_DIR/system-templates.backup"
    
    # Backup existing templates if they exist
    if [[ -d "$SYSTEM_TEMPLATES_DIR" ]]; then
        log_info "Backing up existing templates..."
        if [[ -d "$BACKUP_DIR" ]]; then
            rm -rf "$BACKUP_DIR"
        fi
        mv "$SYSTEM_TEMPLATES_DIR" "$BACKUP_DIR"
        log_info "Backed up old templates to $BACKUP_DIR"
    fi
    
    # Create new unified template structure
    mkdir -p "$SYSTEM_TEMPLATES_DIR"/{app,llm,control-panel,unified,base}/{nginx,systemd}
    
    # Create app templates
    cat > "$SYSTEM_TEMPLATES_DIR/app/nginx/app.conf.j2" <<'EOF'
# Nginx configuration for {{ app_name }}
# Generated by WebOps

server {
    listen {{ http_port|default(80) }};
    server_name {{ domain if domain else '_' }};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    {% if csp %}
    add_header Content-Security-Policy "{{ csp }}" always;
    {% endif %}

    # Logging
    access_log {{ access_log_path|default('/var/log/nginx/' + app_name + '-access.log') }};
    error_log {{ error_log_path|default('/var/log/nginx/' + app_name + '-error.log') }};

    {% if app_type == 'django' %}
    # Django application
    location / {
        proxy_pass http://127.0.0.1:{{ port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static/ {
        alias {{ static_root }}/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias {{ media_root }}/;
        expires 30d;
    }
    {% else %}
    # Static site or generic app
    location / {
        proxy_pass {{ proxy_pass_url|default('http://127.0.0.1:' + port|string) }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};
    }
    {% endif %}

    # Deny access to hidden files
    location ~ /\\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}

{% if ssl_enabled|default(false) and domain %}
# SSL configuration
server {
    listen 443 ssl http2;
    server_name {{ domain }};

    # SSL certificates
    ssl_certificate {{ ssl_cert_path|default('/etc/letsencrypt/live/' + domain + '/fullchain.pem') }};
    ssl_certificate_key {{ ssl_cert_key_path|default('/etc/letsencrypt/live/' + domain + '/privkey.pem') }};
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    
    # Same configuration as HTTP server
    access_log {{ access_log_path|default('/var/log/nginx/' + app_name + '-access.log') }};
    error_log {{ error_log_path|default('/var/log/nginx/' + app_name + '-error.log') }};

    {% if app_type == 'django' %}
    # Django application
    location / {
        proxy_pass http://127.0.0.1:{{ port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static/ {
        alias {{ static_root }}/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias {{ media_root }}/;
        expires 30d;
    }
    {% else %}
    # Static site or generic app
    location / {
        proxy_pass {{ proxy_pass_url|default('http://127.0.0.1:' + port|string) }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};
    }
    {% endif %}

    # Deny access to hidden files
    location ~ /\\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
{% endif %}
EOF

    cat > "$SYSTEM_TEMPLATES_DIR/app/systemd/app.service.j2" <<'EOF'
# Systemd service file for {{ app_name }}
# Generated by WebOps

[Unit]
Description={{ app_name }} - WebOps Deployment
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User={{ webops_user }}
Group={{ webops_user }}
WorkingDirectory={{ repo_path }}

# Environment
Environment="PATH={{ venv_path }}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH={{ repo_path }}"
{% for key, value in env_vars.items() %}
Environment="{{ key }}={{ value }}"
{% endfor %}

# Gunicorn configuration (ASGI/WSGI auto-detected)
ExecStart={{ venv_path }}/bin/gunicorn \
    --bind 127.0.0.1:{{ port }} \
    --workers {{ workers }} \
    {% if extra_gunicorn_args %}{{ extra_gunicorn_args }} \
    {% endif %}--timeout 60 \
    --access-logfile {{ log_path }}/access.log \
    --error-logfile {{ log_path }}/error.log \
    --log-level info \
    {{ app_module }}

# Restart policy
Restart=always
RestartSec=5

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={{ repo_path }} {{ log_path }}

[Install]
WantedBy=multi-user.target
EOF

    cat > "$SYSTEM_TEMPLATES_DIR/llm/nginx/llm.conf.j2" <<'EOF'
## Nginx reverse proxy for vLLM API
upstream {{ app_name }}_llm {
    server 127.0.0.1:{{ port }};
}

server {
    listen 80;
    server_name {{ domain }};

    # Optional: SSL handled elsewhere; this is a base HTTP config
    # Add rate limiting and timeouts suitable for LLM streaming
    client_max_body_size 10m;
    keepalive_timeout 65;

    location / {
        proxy_pass http://{{ app_name }}_llm;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for streaming responses
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;

        # Buffering off for server-sent events / streaming
        proxy_buffering off;
    }
}
EOF

    cat > "$SYSTEM_TEMPLATES_DIR/llm/systemd/vllm.service.j2" <<'EOF'
[Unit]
Description=vLLM LLM Model Server - {{ app_name }}
After=network.target

[Service]
Type=simple
User={{ webops_user }}
WorkingDirectory={{ venv_path }}
Environment="PATH={{ venv_path }}/bin"
Environment="HF_HOME={{ model_cache_path }}"
Environment="TRANSFORMERS_CACHE={{ model_cache_path }}"
Environment="VLLM_TARGET_DEVICE=cpu"
Environment="CMAKE_DISABLE_FIND_PACKAGE_CUDA=ON"
Environment="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4:$LD_PRELOAD"
Environment="VLLM_LOGGING_LEVEL={{ logging_level }}

# vLLM server command
ExecStart={{ python_path }} -m vllm.entrypoints.openai.api_server {{ vllm_args }}

# Logging
StandardOutput=append:{{ log_path }}/vllm.log
StandardError=append:{{ log_path }}/vllm-error.log

# Restart policy
Restart=on-failure
RestartSec=10s

# Resource limits
# vLLM can use significant GPU memory
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

    cat > "$SYSTEM_TEMPLATES_DIR/llm/systemd/vllm_cpu.service.j2" <<'EOF'
## vLLM CPU systemd service
[Unit]
Description=vLLM OpenAI-Compatible API Server (CPU) - {{ app_name }}
After=network.target

[Service]
Type=simple
User={{ webops_user }}
WorkingDirectory={{ work_dir }}
Environment="VLLM_TARGET_DEVICE=cpu"
Environment="CMAKE_DISABLE_FIND_PACKAGE_CUDA=ON"
Environment="HF_HOME={{ model_cache_path }}"
Environment="TRANSFORMERS_CACHE={{ model_cache_path }}"
{% if ld_preload %}Environment="LD_PRELOAD={{ ld_preload }}"{% endif %}
Environment="PYTHONUNBUFFERED=1"

ExecStart={{ python_path }} -m vllm.entrypoints.openai.api_server {{ vllm_args }}
Restart=always
RestartSec=5

# Logging to journal; higher verbosity can be set via args
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    cat > "$SYSTEM_TEMPLATES_DIR/app/systemd/docker.service.j2" <<'EOF'
[Unit]
Description=WebOps Docker Container - {{ app_name }}
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory={{ repo_path }}

# Stop existing container
ExecStartPre=-/usr/bin/docker stop webops-{{ app_name }}
ExecStartPre=-/usr/bin/docker rm webops-{{ app_name }}

# Start container
ExecStart=/usr/bin/docker run -d \
    --name webops-{{ app_name }} \
    --restart unless-stopped \
    --network {{ network_mode }} \
    -p {{ port }}:{{ port }} \
    {% for key, value in env_vars.items() %}-e {{ key }}="{{ value }}" \
    {% endfor %}-e PORT={{ port }} \
    {% for volume in volumes %}-v {{ volume.host }}:{{ volume.container }} \
    {% endfor %}{% for port_map in additional_ports %}-p {{ port_map.host }}:{{ port_map.container }} \
    {% endfor %}{{ image_name }}

# Stop container
ExecStop=/usr/bin/docker stop webops-{{ app_name }}

# Restart = always handled by docker --restart flag
Restart=no

[Install]
WantedBy=multi-user.target
EOF

    # Create unified templates that can handle multiple scenarios
    cat > "$SYSTEM_TEMPLATES_DIR/unified/nginx/unified.conf.j2" <<'EOF'
# Unified Nginx configuration for {{ app_name }}
# Generated by WebOps - handles different app types through parameters

server {
    listen {{ http_port|default(80) }};
    server_name {{ domain if domain else '_' }};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    {% if csp %}
    add_header Content-Security-Policy "{{ csp }}" always;
    {% endif %}

    # Logging
    access_log {{ access_log_path|default('/var/log/nginx/' + app_name + '-access.log') }};
    error_log {{ error_log_path|default('/var/log/nginx/' + app_name + '-error.log') }};

    # Application-specific configurations
    {% if app_type == 'django' %}
    # Django application
    location / {
        proxy_pass http://127.0.0.1:{{ port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static/ {
        alias {{ static_root }}/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias {{ media_root }}/;
        expires 30d;
    }
    
    {% elif app_type == 'llm' %}
    # LLM API server (vLLM or similar)
    location / {
        proxy_pass http://127.0.0.1:{{ port }};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for streaming responses
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('600s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('600s') }};

        # Buffering off for server-sent events / streaming
        proxy_buffering off;
    }
    
    {% else %}
    # Generic application or static site
    location / {
        proxy_pass {{ proxy_pass_url|default('http://127.0.0.1:' + port|string) }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};
    }
    {% endif %}

    # Deny access to hidden files
    location ~ /\\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}

{% if ssl_enabled|default(false) and domain %}
# SSL configuration
server {
    listen 443 ssl http2;
    server_name {{ domain }};

    # SSL certificates
    ssl_certificate {{ ssl_cert_path|default('/etc/letsencrypt/live/' + domain + '/fullchain.pem') }};
    ssl_certificate_key {{ ssl_cert_key_path|default('/etc/letsencrypt/live/' + domain + '/privkey.pem') }};
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    
    # Same configuration as HTTP server (reusing the same logic)
    access_log {{ access_log_path|default('/var/log/nginx/' + app_name + '-access.log') }};
    error_log {{ error_log_path|default('/var/log/nginx/' + app_name + '-error.log') }};

    # Application-specific configurations
    {% if app_type == 'django' %}
    # Django application
    location / {
        proxy_pass http://127.0.0.1:{{ port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static/ {
        alias {{ static_root }}/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias {{ media_root }}/;
        expires 30d;
    }
    
    {% elif app_type == 'llm' %}
    # LLM API server (vLLM or similar)
    location / {
        proxy_pass http://127.0.0.1:{{ port }};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for streaming responses
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('600s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('600s') }};

        # Buffering off for server-sent events / streaming
        proxy_buffering off;
    }
    
    {% else %}
    # Generic application or static site
    location / {
        proxy_pass {{ proxy_pass_url|default('http://127.0.0.1:' + port|string) }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout {{ proxy_connect_timeout|default('60s') }};
        proxy_send_timeout {{ proxy_send_timeout|default('60s') }};
        proxy_read_timeout {{ proxy_read_timeout|default('60s') }};
    }
    {% endif %}

    # Deny access to hidden files
    location ~ /\\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
{% endif %}
EOF

    cat > "$SYSTEM_TEMPLATES_DIR/unified/systemd/unified.service.j2" <<'EOF'
# Unified systemd service for {{ app_name }}
# Generated by WebOps - handles different service types through parameters

[Unit]
Description={{ app_name }} - {{ service_description|default("WebOps Deployment") }}
After=network.target {{ after_services|default("postgresql.service") }}
{% if wants_services %}Wants={{ wants_services }}{% endif %}

[Service]
Type={{ service_type|default("simple") }}
User={{ webops_user }}
Group={{ webops_user|default(webops_user) }}
WorkingDirectory={{ working_directory|default(repo_path) }}

# Environment Variables
Environment="PATH={{ venv_path }}/bin:/usr/local/bin:/usr/bin:/bin"
{% if python_path %}Environment="PATH={{ python_path }}:/usr/local/bin:/usr/bin:/bin"{% endif %}
{% if app_env_vars %}
{% for key, value in app_env_vars.items() %}
Environment="{{ key }}={{ value }}"
{% endfor %}
{% else %}
{% for key, value in env_vars.items() %}
Environment="{{ key }}={{ value }}"
{% endfor %}
{% endif %}

# Service-specific environment variables
{% if service_type_name == 'vllm' %}
Environment="HF_HOME={{ model_cache_path|default('/tmp') }}"
Environment="TRANSFORMERS_CACHE={{ model_cache_path|default('/tmp') }}"
{% if service_subtype == 'cpu' %}
Environment="VLLM_TARGET_DEVICE=cpu"
Environment="CMAKE_DISABLE_FIND_PACKAGE_CUDA=ON"
{% endif %}
Environment="VLLM_LOGGING_LEVEL={{ logging_level|default('info') }}"
{% elif service_type_name == 'docker' %}
# Docker-specific environment would go here
{% endif %}

# Command execution based on service type
{% if service_type_name == 'vllm' %}
ExecStart={{ python_path|default(venv_path + '/bin/python') }} -m vllm.entrypoints.openai.api_server {{ vllm_args|default('') }}
{% elif service_type_name == 'django' or service_type_name == 'general' %}
ExecStart={{ venv_path }}/bin/gunicorn \
    --bind 127.0.0.1:{{ port }} \
    --workers {{ workers|default(2) }} \
    {% if extra_gunicorn_args %}{{ extra_gunicorn_args }} \
    {% endif %}--timeout 60 \
    --access-logfile {{ log_path }}/access.log \
    --error-logfile {{ log_path }}/error.log \
    --log-level info \
    {{ app_module|default('wsgi:application') }}
{% elif service_type_name == 'docker' %}
ExecStartPre=-/usr/bin/docker stop webops-{{ app_name }}
ExecStartPre=-/usr/bin/docker rm webops-{{ app_name }}
ExecStart=/usr/bin/docker run -d \
    --name webops-{{ app_name }} \
    --restart unless-stopped \
    --network {{ network_mode|default('bridge') }} \
    -p {{ port }}:{{ port }} \
    {% for key, value in env_vars.items() %}-e {{ key }}="{{ value }}" \
    {% endfor %}-e PORT={{ port }} \
    {% for volume in (volumes|default([])) %}-v {{ volume.host }}:{{ volume.container }} \
    {% endfor %}{% for port_map in (additional_ports|default([])) %}-p {{ port_map.host }}:{{ port_map.container }} \
    {% endfor %}{{ image_name }}
ExecStop=/usr/bin/docker stop webops-{{ app_name }}
{% endif %}

# Logging
{% if service_type_name == 'vllm' %}
StandardOutput=append:{{ log_path }}/vllm.log
StandardError=append:{{ log_path }}/vllm-error.log
{% else %}
{% if log_path %}
StandardOutput=journal
StandardError=journal
{% endif %}
{% endif %}

# Restart policy
Restart={{ restart_policy|default("always") }}
RestartSec={{ restart_sec|default("5") }}

# Security
{% if security_enabled|default(true) %}
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={{ repo_path|default('/tmp') }} {{ log_path|default('/tmp') }}
{% endif %}

# Resource limits (if needed)
{% if resource_limits %}
{% for limit, value in resource_limits.items() %}
{{ limit }}={{ value }}
{% endfor %}
{% endif %}

[Install]
WantedBy=multi-user.target
EOF

    # Create template registry
    cat > "$SYSTEM_TEMPLATES_DIR/template_registry.py" <<'EOF'
"""
Template Registry for WebOps
Centralizes template selection logic to reduce duplication and improve maintainability
"""

class TemplateRegistry:
    """
    A registry that maps deployment types to appropriate templates
    """
    
    def __init__(self):
        # Define template mappings for different deployment types
        self.template_mappings = {
            'app': {
                'nginx': 'app/nginx/app.conf.j2',
                'systemd': 'app/systemd/app.service.j2',
                'env': 'control-panel/env.j2'
            },
            'django': {
                'nginx': 'app/nginx/app.conf.j2',  # Uses the same as general app but with django-specific vars
                'systemd': 'app/systemd/app.service.j2',
                'env': 'control-panel/env.j2'
            },
            'vllm_gpu': {
                'nginx': 'llm/nginx/llm.conf.j2',
                'systemd': 'llm/systemd/vllm.service.j2',
            },
            'vllm_cpu': {
                'nginx': 'llm/nginx/llm.conf.j2',
                'systemd': 'llm/systemd/vllm_cpu.service.j2',
            },
            'docker': {
                'systemd': 'app/systemd/docker.service.j2',
            },
            'llm': {
                'nginx': 'llm/nginx/llm.conf.j2',
                'systemd': 'unified/systemd/unified.service.j2',  # Use unified for more flexibility
            }
        }
    
    def get_template_path(self, deployment_type, service_type):
        """
        Get the appropriate template path for a given deployment type and service type.
        Falls back to unified templates if specific templates don't exist.
        """
        # First try to get the specific template
        if deployment_type in self.template_mappings:
            if service_type in self.template_mappings[deployment_type]:
                return self.template_mappings[deployment_type][service_type]
        
        # Fallback mapping to unified templates
        fallback_mapping = {
            ('app', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('app', 'systemd'): 'unified/systemd/unified.service.j2',
            ('django', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('django', 'systemd'): 'unified/systemd/unified.service.j2',
            ('vllm_gpu', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('vllm_gpu', 'systemd'): 'unified/systemd/unified.service.j2',
            ('vllm_cpu', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('vllm_cpu', 'systemd'): 'unified/systemd/unified.service.j2',
            ('docker', 'systemd'): 'unified/systemd/unified.service.j2',
            ('llm', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('llm', 'systemd'): 'unified/systemd/unified.service.j2',
        }
        
        fallback_key = (deployment_type, service_type)
        if fallback_key in fallback_mapping:
            return fallback_mapping[fallback_key]
        
        # If no specific or fallback template found, return None
        return None
    
    def get_available_types(self):
        """
        Get all available deployment types
        """
        return list(self.template_mappings.keys())
    
    def get_available_services(self, deployment_type):
        """
        Get all available service types for a given deployment type
        """
        if deployment_type in self.template_mappings:
            return list(self.template_mappings[deployment_type].keys())
        return []


# Singleton instance
template_registry = TemplateRegistry()
EOF

    # Create README
    cat > "$SYSTEM_TEMPLATES_DIR/README.md" <<'EOF'
# WebOps System Templates

This directory contains all system templates for WebOps deployments. The structure is organized to reduce duplication and improve maintainability.

## Directory Structure

```
system-templates/
├── app/                 # Templates for general applications
│   ├── nginx/
│   │   └── app.conf.j2
│   └── systemd/
│       ├── app.service.j2
│       └── docker.service.j2
├── llm/                 # Templates for LLM services
│   ├── nginx/
│   │   └── llm.conf.j2
│   └── systemd/
│       ├── vllm.service.j2
│       └── vllm_cpu.service.j2
├── control-panel/       # Templates for WebOps control panel
│   ├── nginx/
│   │   └── nginx-ssl-config.conf
│   └── env.j2
├── unified/             # Unified templates with parameterization
│   ├── nginx/
│   │   └── unified.conf.j2
│   └── systemd/
│       └── unified.service.j2
├── base/                # Base templates for inheritance (future use)
│   ├── nginx/
│   │   └── base.conf.j2
│   └── systemd/
│       └── base.service.j2
├── template_registry.py # Registry mapping deployment types to templates
└── README.md
```

## Template Types

### App Templates
- For general web applications (Django, Flask, etc.)
- Handles standard WSGI/ASGI deployments with Gunicorn

### LLM Templates
- For LLM services like vLLM
- Optimized for AI inference with appropriate resource settings

### Control Panel Templates
- For the WebOps control panel itself
- Includes SSL configuration for the main interface

### Unified Templates
- Single parameterized templates that can handle multiple deployment types
- Reduces code duplication by using conditional logic
- Preferred for new deployments

## Template Registry

The `template_registry.py` file defines which template to use for different deployment scenarios. This centralizes the template selection logic and makes it easier to maintain.

## Best Practices

1. Use unified templates when possible to reduce duplication
2. Add new functionality to unified templates rather than creating new specialized ones
3. Update the template registry when adding new template types
4. Keep templates parameterized rather than creating multiple similar templates
EOF

    # Create environment template
    cat > "$SYSTEM_TEMPLATES_DIR/control-panel/env.j2" <<'EOF'
# Environment configuration for {{ app_name }}
# Generated by WebOps

# Database
DATABASE_URL={{ database_url }}

# Django settings
SECRET_KEY={{ secret_key }}
DEBUG=False
ALLOWED_HOSTS={{ allowed_hosts }}

# Custom environment variables
{% for key, value in custom_env_vars.items() %}
{{ key }}={{ value }}
{% endfor %}
EOF

    # Create SSL config
    cat > "$SYSTEM_TEMPLATES_DIR/control-panel/nginx-ssl-config.conf" <<'EOF'
server {
    listen 80;
    server_name localhost;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name localhost;

    # SSL Configuration
    ssl_certificate /etc/ssl/webops/webops.crt;
    ssl_certificate_key /etc/ssl/webops/webops.key;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    # Consider adding CSP tuned to your app:
    # add_header Content-Security-Policy "default-src 'self'" always;

    client_max_body_size 100M;

    # Static files
    location /static/ {
        alias ${WEBOPS_DIR:-/opt/webops}/control-panel/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias ${WEBOPS_DIR:-/opt/webops}/control-panel/media/;
        expires 7d;
    }

    # Proxy to Gunicorn/ASGI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

    # Set ownership and permissions
    chown -R "$WEBOPS_USER:$WEBOPS_USER" "$SYSTEM_TEMPLATES_DIR"
    find "$SYSTEM_TEMPLATES_DIR" -type f -exec chmod 644 {} \;
    find "$SYSTEM_TEMPLATES_DIR" -type d -exec chmod 755 {} \;
    
    log_info "System templates with unified structure installed to $SYSTEM_TEMPLATES_DIR"
}

configure_control_panel() {
    log_step "Configuring control panel..."

    # Generate SECRET_KEY
    SECRET_KEY=$(python3 -c 'import secrets; import string; print("".join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(64)))')

    # Generate ENCRYPTION_KEY for database passwords using the virtual environment Python
    # This avoids issues with system Python missing cryptography dependencies
    ENCRYPTION_KEY=$(sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

    # Prompt for domain and email for SSL and hosts
    read -p "Control panel domain (leave blank to use server IP): " PANEL_DOMAIN
    read -p "Admin email for Let's Encrypt (optional, needed for SSL): " ADMIN_EMAIL

    server_ip=$(hostname -I | awk '{print $1}')
    if [[ -n "$PANEL_DOMAIN" ]]; then
        ALLOWED_HOSTS_VAL="$PANEL_DOMAIN,$server_ip,localhost,127.0.0.1"
        CSRF_TRUSTED_ORIGINS_VAL="https://$PANEL_DOMAIN,http://$PANEL_DOMAIN"
    else
        ALLOWED_HOSTS_VAL="$server_ip,localhost,127.0.0.1"
        CSRF_TRUSTED_ORIGINS_VAL="http://$server_ip,https://$server_ip,http://localhost:8000,https://localhost:8000"
    fi

    # Create .env file
    cat > "$CONTROL_PANEL_DIR/.env" <<EOF
# Django Settings
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${ALLOWED_HOSTS_VAL}
CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS_VAL}

# Database
DATABASE_URL=postgresql:///webops_control_panel

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Paths
DEPLOYMENTS_DIR=${DEPLOYMENTS_DIR}
SHARED_DIR=${SHARED_DIR}
BACKUPS_DIR=${BACKUPS_DIR}
EOF

    chown "$WEBOPS_USER:$WEBOPS_USER" "$CONTROL_PANEL_DIR/.env"
    chmod 600 "$CONTROL_PANEL_DIR/.env"

    # Run migrations
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" "$CONTROL_PANEL_DIR/manage.py" migrate

    # Create admin user with proper password
    log_info "Creating admin user..."
    read -p "Admin username [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}

    # Generate random password
    ADMIN_PASSWORD=$(openssl rand -base64 16)
    ADMIN_CREDS_FILE="/opt/webops/.secrets/admin_credentials.txt"

    # Create user using Django shell
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" "$CONTROL_PANEL_DIR/manage.py" shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()

# Check if user exists
if User.objects.filter(username='$ADMIN_USER').exists():
    print('Admin user $ADMIN_USER already exists')
    user = User.objects.get(username='$ADMIN_USER')
    user.set_password('$ADMIN_PASSWORD')
    user.save()
    print('Password updated for existing user')
else:
    User.objects.create_superuser(
        username='$ADMIN_USER',
        email='admin@webops.local',
        password='$ADMIN_PASSWORD'
    )
    print('Admin user $ADMIN_USER created successfully')
EOF

    # Save credentials securely
    cat > "$ADMIN_CREDS_FILE" <<EOF
WebOps Admin Credentials
========================
Generated: $(date)

Username: $ADMIN_USER
Password: $ADMIN_PASSWORD

IMPORTANT: Change this password after first login!

Control Panel URL: http://$(hostname -I | awk '{print $1}')/
EOF

    chmod 600 "$ADMIN_CREDS_FILE"
    chown "$WEBOPS_USER:$WEBOPS_USER" "$ADMIN_CREDS_FILE"

    log_info "Admin user created: $ADMIN_USER"
    log_info "Credentials saved to: $ADMIN_CREDS_FILE"

    # Collect static files
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" "$CONTROL_PANEL_DIR/manage.py" collectstatic --noinput

    log_info "Control panel configured ✓"
}

#=============================================================================
# Systemd Services
#=============================================================================

create_systemd_services() {
    log_step "Creating systemd services..."

    # WebOps Web Service
    cat > /etc/systemd/system/webops-web.service <<EOF
[Unit]
Description=WebOps Control Panel (Gunicorn)
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=simple
User=$WEBOPS_USER
Group=$WEBOPS_USER
WorkingDirectory=$CONTROL_PANEL_DIR
EnvironmentFile=$CONTROL_PANEL_DIR/.env

ExecStart=$CONTROL_PANEL_DIR/venv/bin/gunicorn config.wsgi:application \
    --workers 4 \
    --threads 2 \
    --bind 127.0.0.1:8000 \
    --access-logfile $LOGS_DIR/gunicorn-access.log \
    --error-logfile $LOGS_DIR/gunicorn-error.log \
    --log-level info

Restart=on-failure
RestartSec=5

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$WEBOPS_DIR

# Resources
MemoryMax=1G
CPUQuota=100%

[Install]
WantedBy=multi-user.target
EOF

    # WebOps Celery Worker
    cat > /etc/systemd/system/webops-celery.service <<EOF
[Unit]
Description=WebOps Celery Worker
After=network.target redis.service postgresql.service webops-web.service
Requires=redis.service

[Service]
Type=simple
User=$WEBOPS_USER
Group=$WEBOPS_USER
WorkingDirectory=$CONTROL_PANEL_DIR
EnvironmentFile=$CONTROL_PANEL_DIR/.env

# Set environment variables for Celery
Environment=PATH=$CONTROL_PANEL_DIR/venv/bin
Environment=DJANGO_SETTINGS_MODULE=config.settings
Environment=PYTHONPATH=$CONTROL_PANEL_DIR
Environment=CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=true

ExecStart=$CONTROL_PANEL_DIR/venv/bin/celery -A config.celery_app worker \
    --loglevel=info \
    --logfile=$LOGS_DIR/celery-worker.log \
    --pidfile=/var/run/webops/celery-worker.pid \
    --concurrency=2

ExecStop=/bin/kill -s TERM \$MAINPID

Restart=on-failure
RestartSec=5
TimeoutStartSec=60

# Security
NoNewPrivileges=true
PrivateTmp=true

# Resources
MemoryMax=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF

    # WebOps Celery Beat
    cat > /etc/systemd/system/webops-celerybeat.service <<EOF
[Unit]
Description=WebOps Celery Beat (Scheduler)
After=network.target redis.service webops-web.service webops-celery.service
Requires=redis.service

[Service]
Type=simple
User=$WEBOPS_USER
Group=$WEBOPS_USER
WorkingDirectory=$CONTROL_PANEL_DIR
EnvironmentFile=$CONTROL_PANEL_DIR/.env

# Set environment variables for Celery
Environment=PATH=$CONTROL_PANEL_DIR/venv/bin
Environment=DJANGO_SETTINGS_MODULE=config.settings
Environment=PYTHONPATH=$CONTROL_PANEL_DIR
Environment=CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=true

ExecStart=$CONTROL_PANEL_DIR/venv/bin/celery -A config.celery_app beat \
    --loglevel=info \
    --logfile=$LOGS_DIR/celery-beat.log \
    --pidfile=/var/run/webops/celery-beat.pid

Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF

    # Create PID directory
    mkdir -p /var/run/webops
    chown "$WEBOPS_USER:$WEBOPS_USER" /var/run/webops

    # Reload systemd
    systemctl daemon-reload

    # Enable services
    systemctl enable webops-web
    systemctl enable webops-celery
    systemctl enable webops-celerybeat

    # Start services
    systemctl start webops-web
    systemctl start webops-celery
    systemctl start webops-celerybeat

    log_info "Systemd services created and started ✓"
}

#=============================================================================
# Nginx Configuration
#=============================================================================

configure_nginx_control_panel() {
    log_step "Configuring Nginx for control panel..."

    cat > /etc/nginx/sites-available/webops-panel.conf <<'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    # Static files
    location /static/ {
        alias /opt/webops/control-panel/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /opt/webops/control-panel/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

    # Enable the site
    ln -sf /etc/nginx/sites-available/webops-panel.conf /etc/nginx/sites-enabled/

    # If a domain was provided, set it in server_name and obtain SSL
    if [[ -n "$PANEL_DOMAIN" ]]; then
        sed -i "s/server_name _;/server_name $PANEL_DOMAIN;/" /etc/nginx/sites-available/webops-panel.conf
    fi

    # Test configuration
    nginx -t

    # Reload Nginx
    systemctl reload nginx

    # Obtain SSL cert and enable redirect if domain provided and email present
    if [[ -n "$PANEL_DOMAIN" && -n "$ADMIN_EMAIL" ]]; then
        certbot --nginx --non-interactive --agree-tos -m "$ADMIN_EMAIL" -d "$PANEL_DOMAIN" --redirect || true
        systemctl reload nginx || true
    fi

    log_info "Nginx configured ✓"
}

#=============================================================================
# Finalization
#=============================================================================

run_diagnostics() {
#    Run comprehensive post-installation diagnostics.
    log_step "Running post-installation diagnostics..."

    local DIAG_FILE="/opt/webops/installation-diagnostics.txt"

    {
        echo "======================================================================"
        echo "WebOps Installation Diagnostics Report"
        echo "======================================================================"
        echo "Generated: $(date)"
        echo "Hostname: $(hostname)"
        echo ""

        echo "======================================================================"
        echo "SYSTEM INFORMATION"
        echo "======================================================================"
        echo ""
        echo "Kernel:"
        uname -a
        echo ""
        echo "OS Release:"
        cat /etc/os-release
        echo ""
        echo "Resources:"
        echo "  RAM: $(free -h | awk '/^Mem:/ {print $2}')"
        echo "  CPU Cores: $(nproc)"
        echo "  Disk: $(df -h / | awk 'NR==2 {print $2}')"
        echo ""

        echo "======================================================================"
        echo "SERVICE STATUS"
        echo "======================================================================"
        echo ""
        echo "PostgreSQL:"
        systemctl status postgresql --no-pager -l | head -10
        echo ""
        echo "Redis:"
        systemctl status redis-server --no-pager -l | head -10
        echo ""
        echo "Nginx:"
        systemctl status nginx --no-pager -l | head -10
        echo ""
        echo "WebOps Web (Gunicorn):"
        systemctl status webops-web --no-pager -l | head -10
        echo ""
        echo "WebOps Celery Worker:"
        systemctl status webops-celery --no-pager -l | head -10
        echo ""
        echo "WebOps Celery Beat:"
        systemctl status webops-celerybeat --no-pager -l | head -10
        echo ""

        echo "======================================================================"
        echo "PORT STATUS"
        echo "======================================================================"
        echo ""
        echo "Listening ports:"
        ss -tlnp | grep -E ':(22|80|443|5432|6379|8000) '
        echo ""

        echo "======================================================================"
        echo "DIRECTORY PERMISSIONS"
        echo "======================================================================"
        echo ""
        ls -la /opt/webops/
        echo ""
        echo "Secrets directory:"
        ls -la /opt/webops/.secrets/ 2>/dev/null || echo "  (not found)"
        echo ""

        echo "======================================================================"
        echo "PYTHON ENVIRONMENT"
        echo "======================================================================"
        echo ""
        echo "System Python:"
        python3 --version
        echo ""
        echo "Virtual Environment Python:"
        $CONTROL_PANEL_DIR/venv/bin/python --version
        echo ""
    echo "Installed Packages (top 20):"
    $CONTROL_PANEL_DIR/venv/bin/python -m pip list | head -20
        echo ""

        echo "======================================================================"
        echo "DATABASE CONNECTIVITY"
        echo "======================================================================"
        echo ""
        echo "PostgreSQL databases:"
        sudo -u postgres psql -l 2>&1 || echo "  ERROR: Cannot list databases"
        echo ""
        echo "Test connection as webops user:"
        sudo -u webops psql -d webops_control_panel -c "SELECT version();" 2>&1 || \
            echo "  INFO: Connection requires password (expected for md5 auth)"
        echo ""

        echo "======================================================================"
        echo "REDIS CONNECTIVITY"
        echo "======================================================================"
        echo ""
        echo "Redis PING:"
        redis-cli ping 2>&1
        echo ""
        echo "Redis INFO (server section):"
        redis-cli info server | head -20
        echo ""

        echo "======================================================================"
        echo "NGINX CONFIGURATION"
        echo "======================================================================"
        echo ""
        echo "Configuration test:"
        nginx -t 2>&1
        echo ""
        echo "Enabled sites:"
        ls -la /etc/nginx/sites-enabled/
        echo ""

        echo "======================================================================"
        echo "CELERY STATUS"
        echo "======================================================================"
        echo ""
        echo "Celery processes:"
        pgrep -fa celery || echo "  No celery processes found"
        echo ""
        echo "Recent Celery worker logs:"
        tail -20 $LOGS_DIR/celery-worker.log 2>/dev/null || echo "  Log file not found"
        echo ""

        echo "======================================================================"
        echo "FIREWALL STATUS"
        echo "======================================================================"
        echo ""
        ufw status verbose 2>&1 || echo "  UFW not configured"
        echo ""

        echo "======================================================================"
        echo "DISK USAGE"
        echo "======================================================================"
        echo ""
        df -h
        echo ""

        echo "======================================================================"
        echo "RECENT SYSTEM LOGS (last 20 lines)"
        echo "======================================================================"
        echo ""
        journalctl -n 20 --no-pager
        echo ""

        echo "======================================================================"
        echo "DIAGNOSTIC SUMMARY"
        echo "======================================================================"
        echo ""

        # Check for critical errors
        local errors=0

        if ! systemctl is-active --quiet postgresql; then
            echo "  ✗ PostgreSQL is not running"
            errors=$((errors + 1))
        else
            echo "  ✓ PostgreSQL is running"
        fi

        if ! systemctl is-active --quiet redis-server; then
            echo "  ✗ Redis is not running"
            errors=$((errors + 1))
        else
            echo "  ✓ Redis is running"
        fi

        if ! systemctl is-active --quiet nginx; then
            echo "  ✗ Nginx is not running"
            errors=$((errors + 1))
        else
            echo "  ✓ Nginx is running"
        fi

        if ! systemctl is-active --quiet webops-web; then
            echo "  ✗ WebOps Web is not running"
            errors=$((errors + 1))
        else
            echo "  ✓ WebOps Web is running"
        fi

        if ! systemctl is-active --quiet webops-celery; then
            echo "  ✗ WebOps Celery is not running"
            errors=$((errors + 1))
        else
            echo "  ✓ WebOps Celery is running"
        fi

        if ! systemctl is-active --quiet webops-celerybeat; then
            echo "  ✗ WebOps Celery Beat is not running"
            errors=$((errors + 1))
        else
            echo "  ✓ WebOps Celery Beat is running"
        fi

        echo ""
        if [[ $errors -eq 0 ]]; then
            echo "  ✓ All critical services are running"
        else
            echo "  ✗ $errors critical service(s) not running"
        fi

        echo ""
        echo "======================================================================"
        echo "END OF DIAGNOSTICS REPORT"
        echo "======================================================================"

    } > "$DIAG_FILE" 2>&1

    # Set ownership
    chown "$WEBOPS_USER:$WEBOPS_USER" "$DIAG_FILE"
    chmod 644 "$DIAG_FILE"

    log_info "Diagnostics report saved to: $DIAG_FILE"

    # Check for critical errors and warn user
    if grep -q "✗" "$DIAG_FILE"; then
        log_warn "Diagnostics detected some issues. Review: $DIAG_FILE"
    else
        log_info "All diagnostic checks passed ✓"
    fi
}

print_success_message() {
    local server_ip=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  🎉  WebOps Installation Complete!                           ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Control Panel URL:${NC} http://${server_ip}/"
    echo ""
    echo -e "${YELLOW}Admin Credentials:${NC}"
    echo "  Location: /opt/webops/.secrets/admin_credentials.txt"
    echo "  View with: sudo cat /opt/webops/.secrets/admin_credentials.txt"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Access the control panel in your browser"
    echo "  2. Login with the admin credentials"
    echo "  3. Change your password after first login"
    echo "  4. Deploy your first application!"
    echo ""
    echo -e "${YELLOW}Service Status:${NC}"
    systemctl status webops-web --no-pager -l | head -3
    echo ""
    echo -e "${BLUE}Diagnostics Report:${NC} /opt/webops/installation-diagnostics.txt"
    echo -e "${BLUE}Documentation:${NC} /opt/webops/docs/"
    echo ""
    
    # Final validation - ensure all critical services are running
    echo -e "${YELLOW}Final Validation:${NC}"
    local validation_errors=0
    
    if ! systemctl is-active --quiet postgresql; then
        echo "  ✗ PostgreSQL service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if ! systemctl is-active --quiet redis-server; then
        echo "  ✗ Redis service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if ! systemctl is-active --quiet nginx; then
        echo "  ✗ Nginx service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if ! systemctl is-active --quiet webops-web; then
        echo "  ✗ WebOps Web service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if [[ $validation_errors -eq 0 ]]; then
        echo "  ✓ All critical services validated successfully"
        echo ""
        echo -e "${GREEN}Installation completed successfully with no critical errors!${NC}"
        exit 0
    else
        echo "  ✗ $validation_errors critical service(s) failed validation"
        echo ""
        echo -e "${YELLOW}Warning: Installation completed but some services may need attention.${NC}"
        echo -e "${YELLOW}Check the diagnostics report for details.${NC}"
        exit 0  # Don't fail the installation for service issues that can be resolved post-install
    fi
}

#=============================================================================
# Main Installation Flow
#=============================================================================

main() {
    parse_cli_args "$@"
    echo -e "${BLUE}"
    cat <<'EOF'
╦ ╦┌─┐┌┐ ╔═╗┌─┐┌─┐
║║║├┤ ├┴┐║ ║├─┘└─┐
╚╩╝└─┘└─┘╚═╝┴  └─┘
VPS Hosting Platform Setup
EOF
    echo -e "${NC}"

    # Set trap for cleanup on failure
    trap cleanup_on_failure ERR

    log_info "Starting WebOps installation..."
    # If requested, only run recommendations and exit (safe non-destructive mode)
    if [[ "$RECOMMEND_ONLY" == true ]]; then
        recommend_python_default
        log_info "Recommend-only mode complete. Exiting."
        exit 0
    fi

    # Validation
    check_root
    check_os
    check_resources
    check_internet_connectivity
    check_dns_resolution
    check_package_manager
    check_existing_services
    check_disk_io
    # If requested, only run recommendations and exit (safe non-destructive mode)
    if [[ "$RECOMMEND_ONLY" == true ]]; then
        recommend_python_default
        log_info "Recommend-only mode complete. Exiting."
        exit 0
    fi

    # System setup
    update_system
    if [[ "$INSTALL_PYTHON" == true ]]; then
        install_python
    else
        log_info "Skipping Python installation (use --install-python to enable)."
        # Ensure there's a usable python3 on the system; fail early rather than silently continue
        ensure_python3_present_or_fail
    fi
    # Recommend default python handling and offer helper dry-run
    recommend_python_default
    install_postgresql
    verify_postgresql || exit 1
    install_redis
    verify_redis || exit 1
    install_nginx
    verify_nginx || exit 1
    install_certbot
    install_system_dependencies

    # WebOps setup
    create_webops_user
    create_directory_structure
    configure_sudo_access
    setup_postgresql

    # Security
    configure_firewall
    configure_fail2ban
    configure_logrotate

    # Control panel
    install_control_panel
    configure_control_panel
    create_systemd_services

    # Verify critical services
    verify_celery || exit 1

    configure_nginx_control_panel

    # Run diagnostics
    run_diagnostics

    # Done!
    print_success_message
}

# Run main function
main "$@"
