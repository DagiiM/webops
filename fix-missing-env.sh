#!/bin/bash
#
# WebOps Environment Fix Script
# Quick fix for missing .env files on existing installations
#
# Usage: sudo ./fix-missing-env.sh
#

set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  WebOps Environment Fix                                       ║${NC}"
    echo -e "${BLUE}║  Fixes missing .env files on existing installations           ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    # Detect WebOps installation
    local webops_root="/opt/webops"

    if [[ ! -d "$webops_root" ]]; then
        log_error "WebOps installation not found at: $webops_root"
        log_error "Please ensure WebOps is installed"
        exit 1
    fi

    log_info "Found WebOps installation at: $webops_root"

    # Find and run env-setup script
    local env_setup_script="${webops_root}/provisioning/versions/v1.0.0/setup/env-setup.sh"

    if [[ ! -f "$env_setup_script" ]]; then
        log_error "Environment setup script not found at: $env_setup_script"
        log_error "Your WebOps installation may be incomplete or from an older version"
        exit 1
    fi

    log_info "Running environment setup script..."
    echo ""

    # Export configuration
    export WEBOPS_ROOT="$webops_root"
    export CONTROL_PANEL_DIR="${webops_root}/control-panel"

    # Run the env-setup script
    if bash "$env_setup_script"; then
        echo ""
        log_success "╔════════════════════════════════════════════════════════════════╗"
        log_success "║  Environment fix completed successfully!                      ║"
        log_success "╚════════════════════════════════════════════════════════════════╝"
        echo ""
        log_info "Next steps:"
        log_info "  1. Verify .env file: cat ${webops_root}/control-panel/.env"
        log_info "  2. Restart services: systemctl restart webops-web webops-worker webops-beat"
        log_info "  3. Check service status: systemctl status webops-web"
        echo ""
        exit 0
    else
        echo ""
        log_error "Environment setup failed"
        log_error "Please check the error messages above and try again"
        exit 1
    fi
}

main "$@"
