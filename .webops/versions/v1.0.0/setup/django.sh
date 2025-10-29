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
    log_step "Configuring Django environment..."

    local env_file="${CONTROL_PANEL_DIR}/.env"

    # Create .env file if it doesn't exist
    if [[ ! -f "$env_file" ]]; then
        log_info "Creating Django .env file"

        cat > "$env_file" <<EOF
# Django Configuration
DEBUG=False
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
ALLOWED_HOSTS=localhost,127.0.0.1,$(hostname -I | awk '{print $1}')

# Database
DATABASE_URL=postgresql://webops:webops@localhost:5432/webops

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Channels
REDIS_URL=redis://localhost:6379/3

# Security
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# WebOps
WEBOPS_INSTALL_PATH=${WEBOPS_ROOT}
MIN_PORT=8001
MAX_PORT=9000
EOF

        chown "$WEBOPS_USER:$WEBOPS_USER" "$env_file"
        chmod 600 "$env_file"

        log_success "Django .env file created"
    else
        log_info "Django .env file already exists"
    fi
}

#=============================================================================
# Database Setup
#=============================================================================

setup_django_database() {
    log_step "Setting up Django database..."

    local venv_dir="${CONTROL_PANEL_DIR}/venv"

    # Check if PostgreSQL is running
    if ! systemctl is-active --quiet postgresql; then
        log_info "Starting PostgreSQL..."
        systemctl start postgresql
        systemctl enable postgresql
    fi

    # Create database if it doesn't exist
    if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw webops; then
        log_info "Creating webops database..."
        sudo -u postgres createdb webops
        sudo -u postgres psql -c "CREATE USER webops WITH PASSWORD 'webops';" 2>/dev/null || true
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE webops TO webops;"
    else
        log_info "Database 'webops' already exists"
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
    local services=(webops-web webops-worker webops-beat)

    for service in "${services[@]}"; do
        if [[ -f "/etc/systemd/system/${service}.service" ]]; then
            log_info "Enabling and starting $service..."
            systemctl enable "$service"
            systemctl restart "$service"

            # Wait a moment and check status
            sleep 2
            if systemctl is-active --quiet "$service"; then
                log_success "$service started successfully ✓"
            else
                log_warn "$service failed to start - check logs with: journalctl -xeu $service"
            fi
        fi
    done
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

    # Configure Django
    configure_django_env

    # Setup database
    setup_django_database

    # Collect static files
    collect_static_files

    # Install systemd services
    install_systemd_services

    # Start services
    start_services

    # Prompt for superuser
    prompt_create_superuser

    # Mark as installed
    mark_component_installed "django-control-panel" "1.0.0"

    log_success "Django control panel installation completed ✓"

    # Print access information
    local server_ip=$(hostname -I | awk '{print $1}')
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Django Control Panel Installed Successfully                 ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Access URL:${NC} http://${server_ip}:${CONTROL_PANEL_PORT}/"
    echo ""
    echo -e "${BLUE}Service Management:${NC}"
    echo "  systemctl status webops-web"
    echo "  systemctl status webops-worker"
    echo "  systemctl status webops-beat"
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
