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
readonly WEBOPS_DIR="/opt/webops"
readonly CONTROL_PANEL_DIR="${WEBOPS_DIR}/control-panel"
readonly DEPLOYMENTS_DIR="${WEBOPS_DIR}/deployments"
readonly SHARED_DIR="${WEBOPS_DIR}/shared"
readonly BACKUPS_DIR="${WEBOPS_DIR}/backups"
readonly LOGS_DIR="${WEBOPS_DIR}/logs"

# Python version
readonly PYTHON_VERSION="3.11"

# PostgreSQL version
readonly POSTGRES_VERSION="14"

#=============================================================================
# Logging Functions
#=============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
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

    apt-get update -qq
    apt-get upgrade -y -qq
    apt-get install -y -qq \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common

    log_info "System updated ✓"
}

install_python() {
    log_step "Installing Python ${PYTHON_VERSION}..."

    # Add deadsnakes PPA for Ubuntu (latest Python versions)
    if [[ "$ID" == "ubuntu" ]]; then
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq
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

    apt-get update -qq
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
#    Verify Celery worker is running and processing tasks.
    log_step "Verifying Celery worker..."

    local max_attempts=5
    local attempt=1
    local wait_time=10

    while [[ $attempt -le $max_attempts ]]; do
        # Check systemd status
        if ! systemctl is-active --quiet webops-celery; then
            log_warn "Celery worker not active (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Waiting ${wait_time}s before retry..."
                sleep $wait_time
                systemctl restart webops-celery
                attempt=$((attempt + 1))
                continue
            else
                log_error "Celery worker failed to start after $max_attempts attempts"
                systemctl status webops-celery --no-pager -l
                return 1
            fi
        fi

        # Check process is running
        if ! pgrep -f "celery.*worker" &> /dev/null; then
            log_warn "Celery worker process not found (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                sleep $wait_time
                attempt=$((attempt + 1))
                continue
            else
                log_error "Celery worker process not running"
                return 1
            fi
        fi

        log_info "Celery worker process running ✓"

        # Test worker responsiveness
        log_info "Pinging Celery worker..."
        if sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/celery" -A config.celery_app inspect ping 2>&1 | grep -q "pong"; then
            log_info "Celery: Worker responded to ping ✓"
            return 0
        else
            log_warn "Celery ping failed (attempt $attempt/$max_attempts)"

            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Restarting Celery worker..."
                systemctl restart webops-celery
                sleep $wait_time
                attempt=$((attempt + 1))
            else
                log_error "Celery worker not responding after $max_attempts attempts"
                log_error "Check logs: journalctl -u webops-celery -n 50"
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
    chmod 750 "$CONTROL_PANEL_DIR"
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

    # Create virtual environment
    sudo -u "$WEBOPS_USER" python3 -m venv "$CONTROL_PANEL_DIR/venv"

    # Install Python dependencies
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/pip" install -r "$CONTROL_PANEL_DIR/requirements.txt"

    log_info "Control panel installed ✓"
}

configure_control_panel() {
    log_step "Configuring control panel..."

    # Generate SECRET_KEY
    SECRET_KEY=$(python3 -c 'import secrets; import string; print("".join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(64)))')

    # Generate ENCRYPTION_KEY for database passwords
    ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

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
After=network.target redis.service postgresql.service
Requires=redis.service

[Service]
Type=simple
User=$WEBOPS_USER
Group=$WEBOPS_USER
WorkingDirectory=$CONTROL_PANEL_DIR
EnvironmentFile=$CONTROL_PANEL_DIR/.env

ExecStart=$CONTROL_PANEL_DIR/venv/bin/celery -A config.celery_app worker \
    --loglevel=info \
    --logfile=$LOGS_DIR/celery-worker.log

ExecStop=/bin/kill -s TERM \$MAINPID

Restart=on-failure
RestartSec=10

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
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=$WEBOPS_USER
Group=$WEBOPS_USER
WorkingDirectory=$CONTROL_PANEL_DIR
EnvironmentFile=$CONTROL_PANEL_DIR/.env

ExecStart=$CONTROL_PANEL_DIR/venv/bin/celery -A config.celery_app beat \
    --loglevel=info \
    --logfile=$LOGS_DIR/celery-beat.log

Restart=on-failure
RestartSec=10

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

    log_info "Nginx configured \u2713"
EOF

    ln -sf /etc/nginx/sites-available/webops-panel.conf /etc/nginx/sites-enabled/

    # Test configuration
    nginx -t

    # Reload Nginx
    systemctl reload nginx

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
        $CONTROL_PANEL_DIR/venv/bin/pip list | head -20
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
}

#=============================================================================
# Main Installation Flow
#=============================================================================

main() {
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

    # Validation
    check_root
    check_os
    check_resources
    check_internet_connectivity
    check_dns_resolution
    check_package_manager
    check_existing_services
    check_disk_io

    # System setup
    update_system
    install_python
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
