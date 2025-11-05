#!/bin/bash
#
# WebOps Platform Repair Tool
# Diagnoses and repairs common WebOps platform issues
#
# Usage: sudo ./repair.sh [options]
#
# This script checks and repairs WebOps installations, services,
# configurations, and data integrity issues.
#

set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly WEBOPS_VERSION="v1.0.0"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly WEBOPS_VERSION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
readonly WEBOPS_PLATFORM_DIR="$(dirname "$(dirname "$WEBOPS_VERSION_DIR")")"
readonly WEBOPS_BIN="${WEBOPS_VERSION_DIR}/bin/webops"

# Default install root (will be overridden by config.env if exists)
WEBOPS_ROOT="/opt/webops"

# Repair options
AUTO_FIX=false
VERBOSE=false
DRY_RUN=false

#=============================================================================
# Configuration Functions
#=============================================================================

load_config() {
    local config_file="${WEBOPS_PLATFORM_DIR}/config.env"

    if [[ -f "$config_file" ]]; then
        # Load WEBOPS_ROOT from config
        WEBOPS_ROOT=$(grep "^WEBOPS_ROOT=" "$config_file" | cut -d'=' -f2) || WEBOPS_ROOT="/opt/webops"
        log_verbose "Loaded configuration from $config_file"
        log_verbose "Installation root: $WEBOPS_ROOT"
        return 0
    else
        log_verbose "Configuration file not found, using default paths"
        return 1
    fi
}

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

log_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

log_dry() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $1"
    fi
}

#=============================================================================
# Help and Usage
#=============================================================================

show_help() {
    cat <<EOF
WebOps Platform Repair Tool

USAGE:
    sudo $0 [options]

OPTIONS:
    --auto-fix           Automatically fix detected issues
    --verbose            Show detailed diagnostic information
    --dry-run            Show what would be fixed without executing
    --help, -h           Show this help message

REPAIR CATEGORIES:
    • System dependencies and packages
    • Service configuration and status
    • Database connectivity and integrity
    • File permissions and ownership
    • Network and firewall configuration
    • SSL certificates and security
    • Platform state and consistency

EXAMPLES:
    $0                    # Diagnose issues without fixing
    $0 --auto-fix         # Diagnose and automatically fix issues
    $0 --verbose          # Show detailed diagnostics
    $0 --dry-run          # Preview what would be fixed

This tool will check your WebOps installation for common issues and
provide guidance on how to resolve them. Use --auto-fix to automatically
apply recommended fixes.
EOF
}

#=============================================================================
# Parse Arguments
#=============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --auto-fix)
                AUTO_FIX=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

#=============================================================================
# Validation Functions
#=============================================================================

validate_environment() {
    log_step "Validating repair environment..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Check if WebOps platform exists
    if [[ ! -d "${WEBOPS_VERSION_DIR}" ]]; then
        log_error "WebOps platform version ${WEBOPS_VERSION} not found"
        exit 1
    fi
    
    # Check if webops binary exists
    if [[ ! -x "${WEBOPS_BIN}" ]]; then
        log_error "WebOps binary not found: ${WEBOPS_BIN}"
        exit 1
    fi
    
    log_info "Environment validation passed ✓"
}

#=============================================================================
# Diagnostic Functions
#=============================================================================

check_system_dependencies() {
    log_step "Checking system dependencies..."
    
    local missing_packages=()
    local packages=(
        "postgresql"
        "postgresql-contrib"
        "redis-server"
        "nginx"
        "python3"
        "python3-pip"
        "python3-venv"
        "certbot"
        "python3-certbot-nginx"
    )
    
    for package in "${packages[@]}"; do
        if ! dpkg -l | grep -q "^ii  $package "; then
            missing_packages+=("$package")
            log_verbose "Missing package: $package"
        fi
    done
    
    if [[ ${#missing_packages[@]} -gt 0 ]]; then
        log_warn "Missing packages: ${missing_packages[*]}"
        
        if [[ "$AUTO_FIX" == "true" ]]; then
            log_dry "Would install missing packages: ${missing_packages[*]}"
            if [[ "$DRY_RUN" != "true" ]]; then
                log_info "Installing missing packages..."
                apt-get update
                apt-get install -y "${missing_packages[@]}"
                log_info "Packages installed ✓"
            fi
        else
            log_warn "Run with --auto-fix to install missing packages"
        fi
    else
        log_info "All required packages are installed ✓"
    fi
}

check_webops_user() {
    log_step "Checking WebOps user..."
    
    if ! id "webops" &>/dev/null; then
        log_warn "WebOps user does not exist"
        
        if [[ "$AUTO_FIX" == "true" ]]; then
            log_dry "Would create webops user"
            if [[ "$DRY_RUN" != "true" ]]; then
                log_info "Creating webops user..."
                useradd -r -s /bin/bash -d ${WEBOPS_ROOT} webops
                mkdir -p ${WEBOPS_ROOT}
                chown webops:webops ${WEBOPS_ROOT}
                log_info "WebOps user created ✓"
            fi
        else
            log_warn "Run with --auto-fix to create webops user"
        fi
    else
        log_info "WebOps user exists ✓"
    fi
}

check_service_status() {
    log_step "Checking service status..."
    
    local services=(
        "postgresql"
        "redis-server"
        "nginx"
        "webops-web"
        "webops-worker"
        "webops-beat"
    )
    
    local failed_services=()
    
    for service in "${services[@]}"; do
        if systemctl list-unit-files | grep -q "^${service}.service"; then
            if ! systemctl is-active --quiet "$service"; then
                failed_services+=("$service")
                log_verbose "Service not active: $service"
            fi
            
            if ! systemctl is-enabled --quiet "$service"; then
                log_verbose "Service not enabled: $service"
            fi
        else
            log_verbose "Service not found: $service"
        fi
    done
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        log_warn "Failed services: ${failed_services[*]}"
        
        if [[ "$AUTO_FIX" == "true" ]]; then
            log_dry "Would attempt to start failed services"
            if [[ "$DRY_RUN" != "true" ]]; then
                for service in "${failed_services[@]}"; do
                    log_info "Starting service: $service"
                    systemctl start "$service" || log_warn "Failed to start $service"
                    systemctl enable "$service" || log_warn "Failed to enable $service"
                done
                log_info "Service recovery attempted ✓"
            fi
        else
            log_warn "Run with --auto-fix to attempt service recovery"
        fi
    else
        log_info "All services are running ✓"
    fi
}

check_database_connectivity() {
    log_step "Checking database connectivity..."
    
    if command -v psql &>/dev/null; then
        if sudo -u postgres psql -c "SELECT 1;" &>/dev/null; then
            log_info "PostgreSQL is accessible ✓"
            
            # Check if webops database exists
            if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw webops; then
                log_info "WebOps database exists ✓"
            else
                log_warn "WebOps database does not exist"
                
                if [[ "$AUTO_FIX" == "true" ]]; then
                    log_dry "Would create webops database"
                    if [[ "$DRY_RUN" != "true" ]]; then
                        log_info "Creating webops database..."
                        sudo -u postgres createdb webops
                        log_info "WebOps database created ✓"
                    fi
                else
                    log_warn "Run with --auto-fix to create webops database"
                fi
            fi
        else
            log_warn "Cannot connect to PostgreSQL"
        fi
    else
        log_warn "PostgreSQL client not available"
    fi
}

check_file_permissions() {
    log_step "Checking file permissions..."

    local permission_issues=()

    # Check WebOps directories
    local directories=(
        "${WEBOPS_ROOT}"
        "${WEBOPS_ROOT}/logs"
        "${WEBOPS_ROOT}/deployments"
        "${WEBOPS_ROOT}/backups"
        "${WEBOPS_ROOT}/shared"
    )
    
    for dir in "${directories[@]}"; do
        if [[ -d "$dir" ]]; then
            local owner=$(stat -c "%U:%G" "$dir")
            if [[ "$owner" != "webops:webops" ]]; then
                permission_issues+=("$dir:$owner")
                log_verbose "Incorrect ownership for $dir: $owner"
            fi
        fi
    done
    
    if [[ ${#permission_issues[@]} -gt 0 ]]; then
        log_warn "Permission issues found:"
        for issue in "${permission_issues[@]}"; do
            local dir="${issue%:*}"
            local owner="${issue#*:}"
            log_verbose "  $dir (owner: $owner)"
        done
        
        if [[ "$AUTO_FIX" == "true" ]]; then
            log_dry "Would fix file permissions"
            if [[ "$DRY_RUN" != "true" ]]; then
                log_info "Fixing file permissions..."
                for dir in "${directories[@]}"; do
                    if [[ -d "$dir" ]]; then
                        chown -R webops:webops "$dir" || log_warn "Failed to fix ownership for $dir"
                        chmod 755 "$dir" || log_warn "Failed to fix permissions for $dir"
                    fi
                done
                log_info "File permissions fixed ✓"
            fi
        else
            log_warn "Run with --auto-fix to fix file permissions"
        fi
    else
        log_info "File permissions are correct ✓"
    fi
}

check_network_configuration() {
    log_step "Checking network configuration..."
    
    # Check if firewall is active
    if command -v ufw &>/dev/null; then
        if ufw status | grep -q "Status: active"; then
            log_info "UFW firewall is active ✓"
            
            # Check if required ports are allowed
            local ports=("80" "443" "8000" "5432" "6379")
            local blocked_ports=()
            
            for port in "${ports[@]}"; do
                if ! ufw status | grep -q "$port"; then
                    blocked_ports+=("$port")
                    log_verbose "Port $port not explicitly allowed"
                fi
            done
            
            if [[ ${#blocked_ports[@]} -gt 0 ]]; then
                log_warn "Some ports may be blocked: ${blocked_ports[*]}"
                
                if [[ "$AUTO_FIX" == "true" ]]; then
                    log_dry "Would allow required firewall ports"
                    if [[ "$DRY_RUN" != "true" ]]; then
                        log_info "Configuring firewall rules..."
                        ufw allow 80/tcp
                        ufw allow 443/tcp
                        ufw allow 8000/tcp
                        ufw allow from 127.0.0.1 to any port 5432
                        ufw allow from 127.0.0.1 to any port 6379
                        log_info "Firewall rules configured ✓"
                    fi
                else
                    log_warn "Run with --auto-fix to configure firewall rules"
                fi
            else
                log_info "Required ports are allowed ✓"
            fi
        else
            log_warn "UFW firewall is not active"
        fi
    else
        log_warn "UFW firewall not available"
    fi
}

check_ssl_certificates() {
    log_step "Checking SSL certificates..."
    
    # Check if Let's Encrypt certificates exist
    local cert_dir="/etc/letsencrypt/live"
    if [[ -d "$cert_dir" ]]; then
        local cert_count=$(find "$cert_dir" -maxdepth 2 -name "fullchain.pem" | wc -l)
        if [[ $cert_count -gt 0 ]]; then
            log_info "Found $cert_count SSL certificate(s) ✓"
            
            # Check certificate expiry
            local expiring_certs=()
            for cert in $(find "$cert_dir" -maxdepth 2 -name "fullchain.pem"); do
                local expiry=$(openssl x509 -in "$cert" -noout -enddate | cut -d= -f2)
                local expiry_epoch=$(date -d "$expiry" +%s)
                local current_epoch=$(date +%s)
                local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
                
                if [[ $days_until_expiry -lt 30 ]]; then
                    expiring_certs+=("$cert (expires in $days_until_expiry days)")
                    log_verbose "Certificate expiring soon: $cert"
                fi
            done
            
            if [[ ${#expiring_certs[@]} -gt 0 ]]; then
                log_warn "Certificates expiring soon:"
                for cert in "${expiring_certs[@]}"; do
                    log_verbose "  $cert"
                done
                
                if [[ "$AUTO_FIX" == "true" ]]; then
                    log_dry "Would attempt to renew certificates"
                    if [[ "$DRY_RUN" != "true" ]]; then
                        log_info "Attempting certificate renewal..."
                        certbot renew --dry-run || log_warn "Certificate renewal test failed"
                        log_info "Certificate renewal check completed ✓"
                    fi
                else
                    log_warn "Run with --auto-fix to attempt certificate renewal"
                fi
            else
                log_info "All certificates are valid ✓"
            fi
        else
            log_info "No SSL certificates found (normal for HTTP-only setup)"
        fi
    else
        log_info "Let's Encrypt not configured (normal for HTTP-only setup)"
    fi
}

check_platform_state() {
    log_step "Checking platform state consistency..."
    
    if [[ -x "${WEBOPS_BIN}" ]]; then
        log_info "Running platform state check..."
        
        if [[ "$DRY_RUN" != "true" ]]; then
            "${WEBOPS_BIN}" state || log_warn "Platform state check failed"
        else
            log_dry "Would run platform state check"
        fi
    else
        log_warn "WebOps binary not available for state check"
    fi
}

#=============================================================================
# Main Repair Flow
#=============================================================================

main() {
    # Parse arguments
    parse_args "$@"

    # Load configuration
    load_config

    # Show welcome message
    echo -e "${BLUE}"
    cat <<'EOF'
╦ ╦┌─┐┌┐ ╔═╗┌─┐┌─┐
║║║├┤ ├┴┐║ ║├─┘└─┐
╚╩╝└─┘└─┘╚═╝┴  └─┘
VPS Hosting Platform Repair Tool
EOF
    echo -e "${NC}"
    
    # Validate environment
    validate_environment
    
    # Run diagnostic checks
    check_system_dependencies
    check_webops_user
    check_service_status
    check_database_connectivity
    check_file_permissions
    check_network_configuration
    check_ssl_certificates
    check_platform_state
    
    # Show completion message
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  🔧  WebOps Platform Repair Complete                        ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [[ "$AUTO_FIX" == "true" ]]; then
        echo -e "${GREEN}Automatic fixes have been applied where possible.${NC}"
    else
        echo -e "${YELLOW}Issues have been identified. Run with --auto-fix to apply repairs.${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}For additional diagnostics, run:${NC}"
    echo "  ${WEBOPS_BIN} validate"
    echo "  ${WEBOPS_BIN} state"
    echo ""
    echo -e "${GREEN}Platform repair completed! 🚀${NC}"
}

# Run main function with all arguments
main "$@"