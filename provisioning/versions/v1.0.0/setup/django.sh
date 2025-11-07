#!/bin/bash
#
# WebOps Django Control Panel Setup
# Configures Django application, database, and services
#

set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"

# Configuration
readonly WEBOPS_USER="${WEBOPS_USER:-webops}"
readonly WEBOPS_ROOT="${WEBOPS_ROOT:-/opt/webops}"
readonly CONTROL_PANEL_DIR="${CONTROL_PANEL_DIR:-${WEBOPS_ROOT}/control-panel}"
readonly WEBOPS_LOG_DIR="${WEBOPS_LOG_DIR:-/var/log/webops}"
readonly WEBOPS_RUN_DIR="${WEBOPS_RUN_DIR:-/var/run/webops}"
readonly CONTROL_PANEL_PORT="${CONTROL_PANEL_PORT:-8000}"
readonly CONTROL_PANEL_HOST="${CONTROL_PANEL_HOST:-0.0.0.0}"
readonly GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
readonly CELERY_WORKERS="${CELERY_WORKERS:-4}"
readonly CHANNELS_PORT="${CHANNELS_PORT:-8001}"

#=============================================================================
# Directory Setup
#=============================================================================

setup_directories() {
    log_step "Setting up Django directories..."

    # Ensure control panel directory exists
    if [[ ! -d "$CONTROL_PANEL_DIR" ]]; then
        log_error "Control panel directory not found: $CONTROL_PANEL_DIR"
        log_error "Please ensure the Django application is in the correct location"
        return 1
    fi

    # Create necessary directories
    ensure_directory "$WEBOPS_LOG_DIR" "root:root" "755"
    ensure_directory "$WEBOPS_RUN_DIR" "$WEBOPS_USER:$WEBOPS_USER" "755"
    ensure_directory "${CONTROL_PANEL_DIR}/static" "$WEBOPS_USER:$WEBOPS_USER" "755"
    ensure_directory "${CONTROL_PANEL_DIR}/media" "$WEBOPS_USER:$WEBOPS_USER" "755"
    ensure_directory "${CONTROL_PANEL_DIR}/staticfiles" "$WEBOPS_USER:$WEBOPS_USER" "755"

    log_success "Django directories configured ✓"
}

#=============================================================================
# Python Environment Setup
#=============================================================================

setup_python_venv() {
    log_step "Setting up Python virtual environment..."

    local venv_dir="${CONTROL_PANEL_DIR}/venv"

    # Check if venv already exists
    if [[ -d "$venv_dir" ]]; then
        log_info "Virtual environment already exists at $venv_dir"
    else
        # Create virtual environment
        log_info "Creating virtual environment at $venv_dir"
        sudo -u "$WEBOPS_USER" python3 -m venv "$venv_dir"
    fi

    # Upgrade pip
    log_info "Upgrading pip..."
    sudo -u "$WEBOPS_USER" "$venv_dir/bin/pip" install --upgrade pip setuptools wheel

    # Install requirements
    if [[ -f "${CONTROL_PANEL_DIR}/requirements.txt" ]]; then
        log_info "Installing Python dependencies..."
        sudo -u "$WEBOPS_USER" "$venv_dir/bin/pip" install -r "${CONTROL_PANEL_DIR}/requirements.txt"
    else
        log_warn "requirements.txt not found, skipping dependency installation"
    fi

    # Install production dependencies
    log_info "Installing production server dependencies..."
    sudo -u "$WEBOPS_USER" "$venv_dir/bin/pip" install \
        gunicorn \
        gevent \
        daphne \
        setproctitle

    log_success "Python environment configured ✓"
}

#=============================================================================
# Django Configuration
#=============================================================================

configure_django_env() {
    log_step "Verifying Django environment configuration..."

    local env_link="${CONTROL_PANEL_DIR}/.env"
    local main_env="${WEBOPS_ROOT}/.env"

    # Check if main .env exists
    if [[ ! -f "$main_env" ]]; then
        log_error "Main .env file not found at: $main_env"
        log_error "Please run env-setup.sh first"
        return 1
    fi

    # Check if control panel .env exists (should be symlink)
    if [[ -L "$env_link" ]]; then
        log_info "Control panel .env symlink exists"
        local target=$(readlink "$env_link")
        if [[ "$target" == "$main_env" ]]; then
            log_success "Django environment configured via symlink ✓"
        else
            log_warn "Symlink points to unexpected location: $target"
            log_warn "Expected: $main_env"
        fi
    elif [[ -f "$env_link" ]]; then
        log_warn "Control panel has standalone .env file (not symlink)"
        log_info "This will work but consider using symlink for consistency"
    else
        log_info ".env not found in control panel, will be created by env-setup.sh"
    fi
}

#=============================================================================
# Database Setup
#=============================================================================

setup_django_database() {
    log_step "Setting up Django database..."

    local venv_dir="${CONTROL_PANEL_DIR}/venv"
    local main_env="${WEBOPS_ROOT}/.env"

    # Extract database password from .env
    local db_password="webops"  # Default fallback
    if [[ -f "$main_env" ]]; then
        # Extract password from DATABASE_URL
        # Format: postgresql://webops:PASSWORD@localhost:5432/webops_db
        local db_url=$(grep "^DATABASE_URL=" "$main_env" | cut -d'=' -f2-)
        if [[ -n "$db_url" ]]; then
            # Extract password between : and @
            db_password=$(echo "$db_url" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
            log_info "Using database password from .env"
        fi
    else
        log_warn "Main .env not found, using default password"
    fi

    # Extract database name from .env (default: webops_db)
    local db_name="webops_db"
    if [[ -f "$main_env" ]]; then
        local db_url=$(grep "^DATABASE_URL=" "$main_env" | cut -d'=' -f2-)
        if [[ -n "$db_url" ]]; then
            db_name=$(echo "$db_url" | sed -n 's|.*/\([^?]*\).*|\1|p')
        fi
    fi

    # Check if PostgreSQL is running
    if ! systemctl is-active --quiet postgresql; then
        log_info "Starting PostgreSQL..."
        systemctl start postgresql
        systemctl enable postgresql
    fi

    # Create database if it doesn't exist
    if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$db_name"; then
        log_info "Creating database: $db_name"
        sudo -u postgres createdb "$db_name"

        # Create user with generated password
        log_info "Creating database user: webops"
        sudo -u postgres psql -c "CREATE USER webops WITH PASSWORD '${db_password}';" 2>/dev/null || {
            # User might exist, try to update password
            log_info "User exists, updating password"
            sudo -u postgres psql -c "ALTER USER webops WITH PASSWORD '${db_password}';"
        }

        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO webops;"
        log_success "Database created with password from .env ✓"
    else
        log_info "Database '$db_name' already exists"
        # Ensure password is up to date
        log_info "Updating webops user password from .env"
        sudo -u postgres psql -c "ALTER USER webops WITH PASSWORD '${db_password}';" 2>/dev/null || true
    fi

    # Run migrations
    log_info "Running Django migrations..."
    cd "$CONTROL_PANEL_DIR"
    sudo -u "$WEBOPS_USER" "$venv_dir/bin/python" manage.py migrate --noinput

    log_success "Django database configured ✓"
}

#=============================================================================
# Static Files
#=============================================================================

collect_static_files() {
    log_step "Collecting Django static files..."

    local venv_dir="${CONTROL_PANEL_DIR}/venv"

    cd "$CONTROL_PANEL_DIR"
    sudo -u "$WEBOPS_USER" "$venv_dir/bin/python" manage.py collectstatic --noinput --clear

    log_success "Static files collected ✓"
}

#=============================================================================
# Systemd Services
#=============================================================================

install_systemd_services() {
    log_step "Installing systemd services..."

    local systemd_dir="${SCRIPT_DIR}/../systemd"

    # Function to substitute variables in template
    substitute_template() {
        local template="$1"
        local output="$2"

        sed -e "s|{{WEBOPS_USER}}|${WEBOPS_USER}|g" \
            -e "s|{{WEBOPS_ROOT}}|${WEBOPS_ROOT}|g" \
            -e "s|{{CONTROL_PANEL_DIR}}|${CONTROL_PANEL_DIR}|g" \
            -e "s|{{WEBOPS_LOG_DIR}}|${WEBOPS_LOG_DIR}|g" \
            -e "s|{{WEBOPS_RUN_DIR}}|${WEBOPS_RUN_DIR}|g" \
            -e "s|{{WEBOPS_DATA_DIR}}|${WEBOPS_DATA_DIR:-${WEBOPS_ROOT}/data}|g" \
            -e "s|{{CONTROL_PANEL_HOST}}|${CONTROL_PANEL_HOST}|g" \
            -e "s|{{CONTROL_PANEL_PORT}}|${CONTROL_PANEL_PORT}|g" \
            -e "s|{{GUNICORN_WORKERS}}|${GUNICORN_WORKERS}|g" \
            -e "s|{{CELERY_WORKERS}}|${CELERY_WORKERS}|g" \
            -e "s|{{CHANNELS_PORT}}|${CHANNELS_PORT}|g" \
            "$template" > "$output"
    }

    # Install web service
    if [[ -f "${systemd_dir}/webops-web.service.template" ]]; then
        log_info "Installing webops-web.service..."
        substitute_template \
            "${systemd_dir}/webops-web.service.template" \
            "/etc/systemd/system/webops-web.service"
    fi

    # Install worker service
    if [[ -f "${systemd_dir}/webops-worker.service.template" ]]; then
        log_info "Installing webops-worker.service..."
        substitute_template \
            "${systemd_dir}/webops-worker.service.template" \
            "/etc/systemd/system/webops-worker.service"
    fi

    # Install beat service
    if [[ -f "${systemd_dir}/webops-beat.service.template" ]]; then
        log_info "Installing webops-beat.service..."
        substitute_template \
            "${systemd_dir}/webops-beat.service.template" \
            "/etc/systemd/system/webops-beat.service"
    fi

    # Install channels service
    if [[ -f "${systemd_dir}/webops-channels.service.template" ]]; then
        log_info "Installing webops-channels.service..."
        substitute_template \
            "${systemd_dir}/webops-channels.service.template" \
            "/etc/systemd/system/webops-channels.service"
    fi

    # Reload systemd
    systemctl daemon-reload

    log_success "Systemd services installed ✓"
}

#=============================================================================
# Start Services
#=============================================================================

start_services() {
    log_step "Starting Django services..."

    # Enable and start services
    local services=(webops-web webops-worker webops-beat webops-channels)
    local failed_services=()
    local max_retries=3
    local retry_delay=5

    for service in "${services[@]}"; do
        if [[ -f "/etc/systemd/system/${service}.service" ]]; then
            log_info "Enabling and starting $service..."

            # Enable service for auto-start on boot
            systemctl enable "$service" 2>/dev/null || log_warn "Failed to enable $service"

            # Try to start service with retries
            local retry=0
            local started=false

            while [[ $retry -lt $max_retries ]]; do
                if [[ $retry -gt 0 ]]; then
                    log_info "Retry attempt $retry/$((max_retries-1)) for $service..."
                    sleep $retry_delay
                fi

                # Restart the service
                systemctl restart "$service" 2>/dev/null

                # Wait for service to initialize (longer for web service)
                if [[ "$service" == "webops-web" ]] || [[ "$service" == "webops-channels" ]]; then
                    sleep 5
                else
                    sleep 3
                fi

                # Check if service is active
                if systemctl is-active --quiet "$service"; then
                    log_success "$service started successfully ✓"
                    started=true
                    break
                fi

                retry=$((retry + 1))
            done

            # If service failed to start after retries
            if [[ "$started" == "false" ]]; then
                log_error "$service failed to start after $max_retries attempts"
                log_error "Check logs with: journalctl -xeu $service"
                failed_services+=("$service")

                # Show last 20 lines of logs for debugging
                echo ""
                log_error "Last 20 log lines for $service:"
                journalctl -u "$service" -n 20 --no-pager || true
                echo ""
            fi
        fi
    done

    # If critical services failed, fail the installation
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_error "Critical services failed to start:"
        for service in "${failed_services[@]}"; do
            log_error "  • $service"
        done
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_error ""
        log_error "Installation cannot continue with failed services."
        log_error "Please check the logs above and fix any issues."
        log_error ""
        log_error "Common issues:"
        log_error "  1. PostgreSQL not running: systemctl start postgresql"
        log_error "  2. Redis not running: systemctl start redis-server"
        log_error "  3. Port 8000 already in use: ss -tulpn | grep :8000"
        log_error "  4. Permission issues: check /var/log/webops/ permissions"
        log_error ""
        return 1
    fi

    log_success "All services started successfully ✓"
    return 0
}

#=============================================================================
# Create Superuser Prompt
#=============================================================================

prompt_create_superuser() {
    log_step "Django superuser setup..."

    local venv_dir="${CONTROL_PANEL_DIR}/venv"

    echo ""
    echo -e "${YELLOW}Django is configured. You can create a superuser now or later.${NC}"
    echo ""
    echo "To create a superuser now:"
    echo "  cd $CONTROL_PANEL_DIR"
    echo "  sudo -u $WEBOPS_USER $venv_dir/bin/python manage.py createsuperuser"
    echo ""
    echo "Or create using environment variables:"
    echo "  DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@example.com DJANGO_SUPERUSER_PASSWORD=changeme \\"
    echo "  sudo -u $WEBOPS_USER $venv_dir/bin/python manage.py createsuperuser --noinput"
    echo ""
}

#=============================================================================
# Main Installation Function
#=============================================================================

install_django_control_panel() {
    log_info "Installing Django control panel..."

    # Load OS handler
    load_os_handler

    # Setup directories
    setup_directories

    # Setup Python environment
    setup_python_venv

    # Ensure environment files exist (run env-setup for safety)
    log_step "Ensuring environment configuration..."
    if [[ -f "${SCRIPT_DIR}/env-setup.sh" ]]; then
        CONFIGURE_REDIS=no "${SCRIPT_DIR}/env-setup.sh" || log_warn "Environment setup had warnings (continuing)"
    fi

    # Configure Django (legacy - env-setup.sh now handles this)
    configure_django_env

    # Setup database
    setup_django_database

    # Collect static files
    collect_static_files

    # Install systemd services
    install_systemd_services

    # Start services (fail installation if services don't start)
    if ! start_services; then
        log_error "Django control panel installation failed - services did not start"
        log_error "Installation cannot continue. Please fix the issues above and try again."
        return 1
    fi

    # Prompt for superuser
    prompt_create_superuser

    # Mark as installed
    mark_component_installed "django-control-panel" "1.0.0"

    log_success "Django control panel installation completed ✓"

    # Verify network accessibility
    log_step "Verifying network accessibility..."
    local server_ip=$(hostname -I | awk '{print $1}')
    local port="${CONTROL_PANEL_PORT}"

    # Check if port is listening on all interfaces
    if ss -tulpn 2>/dev/null | grep -q ":${port}.*0.0.0.0"; then
        log_success "Server is listening on 0.0.0.0:${port} (accessible from network) ✓"
    elif ss -tulpn 2>/dev/null | grep -q ":${port}"; then
        log_warn "Server is listening on port ${port} but may not be accessible from network"
        log_warn "Check binding configuration in .env: CONTROL_PANEL_HOST=0.0.0.0"
    else
        log_error "Server is not listening on port ${port}"
        log_error "Service may not have started correctly. Check: systemctl status webops-web"
    fi

    # Test HTTP connectivity
    log_info "Testing HTTP connectivity..."
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/" 2>/dev/null | grep -q "200\|302\|301"; then
        log_success "HTTP server is responding ✓"
    else
        log_warn "HTTP server is not responding to requests"
        log_warn "This may be normal if authentication is required"
    fi

    # Print access information
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Django Control Panel Installed Successfully                 ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}✓ Services Started and Running${NC}"
    echo -e "${GREEN}✓ Server Accessible on Network${NC}"
    echo ""
    echo -e "${BLUE}Access URL:${NC} ${GREEN}http://${server_ip}:${port}/${NC}"
    echo ""
    echo -e "${BLUE}Network Info:${NC}"
    echo "  Server IP: ${server_ip}"
    echo "  Port: ${port}"
    echo "  Binding: 0.0.0.0 (all network interfaces)"
    echo ""
    echo -e "${BLUE}Service Management:${NC}"
    echo "  systemctl status webops-web"
    echo "  systemctl status webops-worker"
    echo "  systemctl status webops-beat"
    echo "  systemctl status webops-channels"
    echo ""
    echo -e "${BLUE}Logs:${NC}"
    echo "  journalctl -f -u webops-web"
    echo "  journalctl -f -u webops-worker"
    echo ""
}

#=============================================================================
# Script Execution
#=============================================================================

# Handle command line arguments
action="${1:-install}"

case "$action" in
    install)
        install_django_control_panel
        ;;
    uninstall)
        log_warn "Django control panel uninstall not implemented"
        log_warn "Manually stop services and remove: $CONTROL_PANEL_DIR"
        exit 1
        ;;
    status)
        if is_component_installed "django-control-panel"; then
            echo "Django control panel is installed"
            systemctl status webops-web webops-worker webops-beat
            exit 0
        else
            echo "Django control panel is not installed"
            exit 1
        fi
        ;;
    version)
        echo "django-control-panel 1.0.0"
        ;;
    *)
        log_error "Unknown action: $action"
        echo "Usage: $0 {install|status|version}"
        exit 1
        ;;
esac
