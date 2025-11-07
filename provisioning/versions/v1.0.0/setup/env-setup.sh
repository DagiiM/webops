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
    log_step "Creating main .env file..."

    local env_file="${WEBOPS_ROOT}/.env"
    local env_example="${WEBOPS_ROOT}/.env.example"

    if [[ -f "$env_file" ]]; then
        log_info "Main .env file already exists at: $env_file"
        return 0
    fi

    if [[ ! -f "$env_example" ]]; then
        log_error ".env.example not found at: $env_example"
        log_error "Cannot create .env without template"
        return 1
    fi

    log_info "Creating main .env file from .env.example..."

    # Copy .env.example to .env
    cp "$env_example" "$env_file"

    # Generate secure values for sensitive fields
    log_info "Generating secure credentials..."

    # Generate SECRET_KEY (Django)
    local secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
                       openssl rand -base64 50 | tr -d '\n')
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${secret_key}|g" "$env_file"

    # Generate ENCRYPTION_KEY (for encrypting sensitive data)
    local encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
                          openssl rand -base64 32 | tr -d '\n')
    sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${encryption_key}|g" "$env_file"

    # Generate REDIS_PASSWORD
    local redis_password=$(openssl rand -base64 32 | tr -d '\n')
    sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${redis_password}|g" "$env_file"

    # Generate PostgreSQL password for webops user
    local db_password=$(openssl rand -base64 24 | tr -d '\n' | tr -d '/+=' | cut -c1-24)
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://webops:${db_password}@localhost:5432/webops_db|g" "$env_file"

    # Update ALLOWED_HOSTS with current server info
    local server_ip=$(hostname -I | awk '{print $1}' || echo "localhost")
    local hostname_val=$(hostname)
    sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1,${server_ip},${hostname_val}|g" "$env_file"

    # Set DEBUG to False for production
    sed -i "s|^DEBUG=.*|DEBUG=False|g" "$env_file"

    # Set WEBOPS_INSTALL_PATH
    sed -i "s|^WEBOPS_INSTALL_PATH=.*|WEBOPS_INSTALL_PATH=${WEBOPS_ROOT}|g" "$env_file"

    # Set proper permissions and ownership
    chmod 600 "$env_file"
    if id "webops" &>/dev/null 2>&1; then
        chown webops:webops "$env_file"
    fi

    log_success "Main .env file created at: $env_file ✓"
    log_info ""
    log_info "Generated credentials (stored in .env):"
    log_info "  ✓ SECRET_KEY (Django session security)"
    log_info "  ✓ ENCRYPTION_KEY (Data encryption)"
    log_info "  ✓ REDIS_PASSWORD (Redis authentication)"
    log_info "  ✓ DATABASE_URL (PostgreSQL connection with password)"
    log_info ""
}

create_control_panel_env_link() {
    log_step "Setting up control panel .env link..."

    local env_link="${CONTROL_PANEL_DIR}/.env"
    local main_env="${WEBOPS_ROOT}/.env"

    if [[ ! -d "$CONTROL_PANEL_DIR" ]]; then
        log_warn "Control panel directory not found: $CONTROL_PANEL_DIR"
        log_warn "Skipping control panel .env setup"
        return 0
    fi

    # Check if main .env exists
    if [[ ! -f "$main_env" ]]; then
        log_error "Main .env file not found at: $main_env"
        log_error "Please run create_root_env_file first"
        return 1
    fi

    # If .env already exists and is not a symlink, back it up
    if [[ -f "$env_link" ]] && [[ ! -L "$env_link" ]]; then
        local backup="${env_link}.backup-$(date +%Y%m%d-%H%M%S)"
        log_warn "Existing .env found, backing up to: $backup"
        mv "$env_link" "$backup"
    fi

    # Remove existing symlink if it exists
    if [[ -L "$env_link" ]]; then
        log_info "Removing existing .env symlink"
        rm "$env_link"
    fi

    # Create symlink to main .env
    log_info "Creating symlink: $env_link -> $main_env"
    ln -s "$main_env" "$env_link"

    # Verify symlink was created
    if [[ -L "$env_link" ]]; then
        log_success "Control panel now uses main .env file ✓"
        log_info "  Symlink: $env_link -> $main_env"
    else
        log_error "Failed to create symlink"
        return 1
    fi
}

configure_redis_password() {
    log_step "Configuring Redis authentication..."

    local env_file="${WEBOPS_ROOT}/.env"

    if [[ ! -f "$env_file" ]]; then
        log_warn "Main .env not found, skipping Redis configuration"
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
    local main_env="${WEBOPS_ROOT}/.env"

    # Check main .env exists
    if [[ -f "$main_env" ]]; then
        log_success "✓ Main .env file exists at: $main_env"

        # Verify critical settings exist
        local required_vars=("SECRET_KEY" "DATABASE_URL" "CELERY_BROKER_URL" "ENCRYPTION_KEY" "REDIS_PASSWORD")
        for var in "${required_vars[@]}"; do
            if grep -q "^${var}=" "$main_env"; then
                log_success "  ✓ ${var} configured"
            else
                log_error "  ✗ ${var} missing"
                ((errors++))
            fi
        done
    else
        log_error "✗ Main .env file missing at: $main_env"
        ((errors++))
    fi

    # Check control panel symlink
    if [[ -L "${CONTROL_PANEL_DIR}/.env" ]]; then
        log_success "✓ Control panel .env symlink exists"
        local link_target=$(readlink "${CONTROL_PANEL_DIR}/.env")
        log_info "  Links to: $link_target"
    elif [[ -f "${CONTROL_PANEL_DIR}/.env" ]]; then
        log_warn "⚠ Control panel has a regular .env file (should be symlink)"
        log_warn "  Consider recreating as symlink to main .env"
    else
        log_info "  Control panel .env not found (will be created during installation)"
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
    echo "  1. Review main environment configuration:"
    echo "     ${WEBOPS_ROOT}/.env"
    echo ""
    echo "  2. If Redis is installed, ensure it's using the generated password:"
    echo "     grep requirepass /etc/redis/redis.conf"
    echo "     systemctl restart redis-server"
    echo ""
    echo "  3. When installing PostgreSQL, use the password from .env:"
    echo "     grep DATABASE_URL ${WEBOPS_ROOT}/.env"
    echo ""
    echo "  4. If services are installed, restart them to apply new configuration:"
    echo "     systemctl restart webops-web webops-worker webops-beat webops-channels"
    echo ""
    echo "  5. Test the application:"
    echo "     http://$(hostname -I | awk '{print $1}'):8000/"
    echo ""
}

#=============================================================================
# Main Execution
#=============================================================================

main() {
    log_info "WebOps Environment Setup v1.0.0"
    log_info "================================"
    log_info "Creating main .env from .env.example with generated credentials"
    echo ""

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    # Create main environment file
    create_root_env_file
    echo ""

    # Create control panel symlink to main .env
    create_control_panel_env_link
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
