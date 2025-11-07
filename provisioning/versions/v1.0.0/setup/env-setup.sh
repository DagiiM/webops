#!/bin/bash
#
# WebOps Environment Setup
# Ensures all required .env files are created with proper configuration
#
# This script can be run standalone or as part of the installation process
# to fix missing environment configuration files.
#

set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"

# Configuration
readonly WEBOPS_ROOT="${WEBOPS_ROOT:-/opt/webops}"
readonly CONTROL_PANEL_DIR="${CONTROL_PANEL_DIR:-${WEBOPS_ROOT}/control-panel}"

#=============================================================================
# Environment File Creation Functions
#=============================================================================

create_root_env_file() {
    log_step "Checking root-level .env file..."

    local env_file="${WEBOPS_ROOT}/.env"
    local env_example="${WEBOPS_ROOT}/.env.example"

    if [[ -f "$env_file" ]]; then
        log_info "Root .env file already exists at: $env_file"
        return 0
    fi

    if [[ ! -f "$env_example" ]]; then
        log_warn ".env.example not found at: $env_example"
        log_warn "Skipping root .env file creation"
        return 0
    fi

    log_info "Creating root .env file from .env.example..."

    # Copy .env.example to .env
    cp "$env_example" "$env_file"

    # Generate secure values for sensitive fields
    log_info "Generating secure credentials..."

    # Generate SECRET_KEY
    local secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
                       openssl rand -base64 50 | tr -d '\n')
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=${secret_key}|g" "$env_file"

    # Generate ENCRYPTION_KEY
    local encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
                          openssl rand -base64 32 | tr -d '\n')
    sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${encryption_key}|g" "$env_file"

    # Generate REDIS_PASSWORD
    local redis_password=$(openssl rand -base64 32 | tr -d '\n')
    sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=${redis_password}|g" "$env_file"

    # Update ALLOWED_HOSTS with current server IP
    local server_ip=$(hostname -I | awk '{print $1}' || echo "localhost")
    local hostname=$(hostname)
    sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1,${server_ip},${hostname}|g" "$env_file"

    # Set DEBUG to False for production
    sed -i "s|DEBUG=.*|DEBUG=False|g" "$env_file"

    # Set proper permissions
    chmod 600 "$env_file"

    log_success "Root .env file created at: $env_file ✓"
    log_warn "IMPORTANT: Review and update the following in $env_file:"
    log_warn "  - DATABASE_URL (PostgreSQL password)"
    log_warn "  - REDIS_PASSWORD (should match Redis configuration)"
    log_warn "  - GITHUB_OAUTH_* (if using GitHub integration)"
    log_warn "  - EMAIL_* (if using email notifications)"
}

create_control_panel_env_file() {
    log_step "Checking control panel .env file..."

    local env_file="${CONTROL_PANEL_DIR}/.env"

    if [[ ! -d "$CONTROL_PANEL_DIR" ]]; then
        log_warn "Control panel directory not found: $CONTROL_PANEL_DIR"
        log_warn "Skipping control panel .env creation"
        return 0
    fi

    if [[ -f "$env_file" ]]; then
        log_info "Control panel .env file already exists at: $env_file"
        return 0
    fi

    log_info "Creating control panel .env file..."

    # Get current server info
    local server_ip=$(hostname -I | awk '{print $1}' || echo "127.0.0.1")
    local hostname=$(hostname)

    # Generate secure credentials
    local secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
                       openssl rand -base64 50 | tr -d '\n')
    local encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
                          openssl rand -base64 32 | tr -d '\n')
    local redis_password=$(openssl rand -base64 32 | tr -d '\n')

    # Create .env file with all required settings
    cat > "$env_file" <<EOF
# Django Configuration
DEBUG=False
SECRET_KEY=${secret_key}
ALLOWED_HOSTS=localhost,127.0.0.1,${server_ip},${hostname}

# Database
# Default: Uses PostgreSQL with webops user
# Update password if you changed the PostgreSQL webops user password
DATABASE_URL=postgresql://webops:webops@localhost:5432/webops

# Celery / Redis
# IMPORTANT: Update REDIS_PASSWORD to match your Redis requirepass setting
REDIS_PASSWORD=${redis_password}
CELERY_BROKER_URL=redis://:${redis_password}@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:${redis_password}@localhost:6379/1

# Channels (WebSocket support)
REDIS_URL=redis://:${redis_password}@localhost:6379/3

# Security
# Encryption key for sensitive data (credentials, tokens, etc.)
ENCRYPTION_KEY=${encryption_key}

# WebOps Configuration
WEBOPS_INSTALL_PATH=${WEBOPS_ROOT}
WEBOPS_USER=webops
MIN_PORT=8001
MAX_PORT=9000

# GitHub OAuth Integration (Optional)
# Create OAuth App at: https://github.com/settings/developers
# GITHUB_OAUTH_CLIENT_ID=
# GITHUB_OAUTH_CLIENT_SECRET=
# GITHUB_OAUTH_REDIRECT_URI=http://${server_ip}:8000/integrations/github/callback

# Email Configuration (Optional - for notifications)
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=
# EMAIL_HOST_PASSWORD=
# EMAIL_USE_TLS=True
# DEFAULT_FROM_EMAIL=noreply@${hostname}
EOF

    # Set proper permissions
    chmod 600 "$env_file"

    # Set ownership if WEBOPS_USER exists
    if id "webops" &>/dev/null; then
        chown webops:webops "$env_file"
    fi

    log_success "Control panel .env file created at: $env_file ✓"
    log_info ""
    log_info "Configuration notes:"
    log_info "  1. Redis password generated: Configure Redis to use this password"
    log_info "     Edit /etc/redis/redis.conf and set: requirepass ${redis_password}"
    log_info "     Then restart Redis: systemctl restart redis-server"
    log_info ""
    log_info "  2. Database password: Update DATABASE_URL if PostgreSQL password differs"
    log_info ""
    log_info "  3. Optional integrations: Uncomment and configure GitHub OAuth or Email if needed"
}

configure_redis_password() {
    log_step "Configuring Redis authentication..."

    local env_file="${CONTROL_PANEL_DIR}/.env"

    if [[ ! -f "$env_file" ]]; then
        log_warn "Control panel .env not found, skipping Redis configuration"
        return 0
    fi

    # Extract Redis password from .env file
    local redis_password=$(grep "^REDIS_PASSWORD=" "$env_file" | cut -d'=' -f2)

    if [[ -z "$redis_password" ]]; then
        log_warn "REDIS_PASSWORD not found in .env file"
        return 0
    fi

    # Check if Redis is installed
    if ! command -v redis-cli &>/dev/null; then
        log_info "Redis not installed, skipping Redis password configuration"
        return 0
    fi

    local redis_conf="/etc/redis/redis.conf"

    if [[ ! -f "$redis_conf" ]]; then
        log_warn "Redis configuration file not found: $redis_conf"
        return 0
    fi

    # Backup Redis configuration
    local backup_file="${redis_conf}.backup-$(date +%Y%m%d-%H%M%S)"
    cp "$redis_conf" "$backup_file"
    log_info "Redis config backed up to: $backup_file"

    # Update or add requirepass directive
    if grep -q "^requirepass" "$redis_conf"; then
        sed -i "s|^requirepass.*|requirepass ${redis_password}|g" "$redis_conf"
        log_info "Updated existing requirepass in Redis configuration"
    else
        echo "" >> "$redis_conf"
        echo "# WebOps: Redis password authentication" >> "$redis_conf"
        echo "requirepass ${redis_password}" >> "$redis_conf"
        log_info "Added requirepass to Redis configuration"
    fi

    # Restart Redis to apply changes
    if systemctl is-active --quiet redis-server; then
        log_info "Restarting Redis to apply password..."
        systemctl restart redis-server

        # Wait for Redis to start
        sleep 2

        # Test Redis connection with new password
        if redis-cli -a "$redis_password" ping 2>/dev/null | grep -q "PONG"; then
            log_success "Redis authentication configured successfully ✓"
        else
            log_error "Redis authentication test failed"
            log_error "Restoring backup configuration..."
            cp "$backup_file" "$redis_conf"
            systemctl restart redis-server
            return 1
        fi
    else
        log_info "Redis is not running, password will be applied on next start"
    fi
}

verify_environment_files() {
    log_step "Verifying environment configuration..."

    local errors=0

    # Check root .env
    if [[ -f "${WEBOPS_ROOT}/.env" ]]; then
        log_success "✓ Root .env file exists"
    else
        log_info "  Root .env file not found (optional)"
    fi

    # Check control panel .env
    if [[ -f "${CONTROL_PANEL_DIR}/.env" ]]; then
        log_success "✓ Control panel .env file exists"

        # Verify critical settings exist
        local required_vars=("SECRET_KEY" "DATABASE_URL" "CELERY_BROKER_URL" "ENCRYPTION_KEY")
        for var in "${required_vars[@]}"; do
            if grep -q "^${var}=" "${CONTROL_PANEL_DIR}/.env"; then
                log_success "  ✓ ${var} configured"
            else
                log_error "  ✗ ${var} missing"
                ((errors++))
            fi
        done
    else
        log_error "✗ Control panel .env file missing"
        ((errors++))
    fi

    if [[ $errors -eq 0 ]]; then
        log_success "Environment verification passed ✓"
        return 0
    else
        log_error "Environment verification failed with $errors error(s)"
        return 1
    fi
}

show_next_steps() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Environment Setup Complete                                   ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo ""
    echo "  1. Review environment configuration:"
    echo "     ${CONTROL_PANEL_DIR}/.env"
    echo ""
    echo "  2. If Redis is installed, ensure it's using the generated password:"
    echo "     grep requirepass /etc/redis/redis.conf"
    echo "     systemctl restart redis-server"
    echo ""
    echo "  3. If services are installed, restart them to apply new configuration:"
    echo "     systemctl restart webops-web webops-worker webops-beat webops-channels"
    echo ""
    echo "  4. Test the application:"
    echo "     http://$(hostname -I | awk '{print $1}'):8000/"
    echo ""
}

#=============================================================================
# Main Execution
#=============================================================================

main() {
    log_info "WebOps Environment Setup v1.0.0"
    log_info "================================"
    echo ""

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    # Create environment files
    create_root_env_file
    echo ""

    create_control_panel_env_file
    echo ""

    # Configure Redis (optional, will skip if Redis not installed)
    if [[ "${CONFIGURE_REDIS:-yes}" == "yes" ]]; then
        configure_redis_password
        echo ""
    fi

    # Verify setup
    verify_environment_files
    echo ""

    # Show next steps
    show_next_steps

    log_success "Environment setup completed successfully!"
}

# Run main function
main "$@"
