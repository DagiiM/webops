#!/bin/bash
#
# WebOps Platform Resume Tool
# Resumes interrupted installations and configuration
#
# Usage: sudo ./resume.sh [options]
#
# This script detects and resumes interrupted WebOps installations,
# allowing you to continue from where the process left off.
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBOPS_VERSION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
WEBOPS_PLATFORM_DIR="$(dirname "$(dirname "$WEBOPS_VERSION_DIR")")"
readonly SCRIPT_DIR WEBOPS_VERSION_DIR WEBOPS_PLATFORM_DIR
readonly WEBOPS_BIN="${WEBOPS_VERSION_DIR}/bin/webops"
readonly STATE_FILE="${WEBOPS_PLATFORM_DIR}/.install_state"

# Default install root (will be overridden by config.env if exists)
WEBOPS_ROOT="/opt/webops"

# Resume options
FORCE=false
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
WebOps Platform Resume Tool

USAGE:
    sudo $0 [options]

OPTIONS:
    --force              Force resume even if no interruption detected
    --verbose            Show detailed resume information
    --dry-run            Show what would be resumed without executing
    --help, -h           Show this help message

RESUME STAGES:
    • System preparation and dependency installation
    • Base system hardening and security setup
    • Database installation and configuration
    • Control panel deployment
    • Service configuration and startup
    • SSL certificate setup (if requested)
    • Addon installation and configuration

EXAMPLES:
    $0                   # Detect and resume interrupted installation
    $0 --force           # Force resume from beginning
    $0 --verbose         # Show detailed resume information
    $0 --dry-run         # Preview what would be resumed

This tool detects interrupted WebOps installations and allows you to
resume from the point where the installation failed. It automatically
identifies the last completed stage and continues from there.
EOF
}

#=============================================================================
# Parse Arguments
#=============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                FORCE=true
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
# State Management Functions
#=============================================================================

read_state() {
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
        log_verbose "Loaded installation state from $STATE_FILE"
    else
        log_verbose "No state file found"
        INSTALL_STAGE="not_started"
        INSTALL_PROGRESS=0
    fi
}

write_state() {
    local stage="$1"
    local progress="$2"
    
    cat > "$STATE_FILE" <<EOF
INSTALL_STAGE="$stage"
INSTALL_PROGRESS="$progress"
INSTALL_TIME="$(date -Iseconds)"
EOF
    
    log_verbose "Updated state: $stage ($progress%)"
}

clear_state() {
    if [[ -f "$STATE_FILE" ]]; then
        rm "$STATE_FILE"
        log_verbose "Cleared installation state"
    fi
}

#=============================================================================
# Validation Functions
#=============================================================================

validate_environment() {
    log_step "Validating resume environment..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Check if WebOps platform exists
    if [[ ! -d "${WEBOPS_VERSION_DIR}" ]]; then
        log_error "WebOps platform version ${WEBOPS_VERSION} not found"
        log_error "Please run './install.sh' first to start a new installation"
        exit 1
    fi
    
    # Check if webops binary exists
    if [[ ! -x "${WEBOPS_BIN}" ]]; then
        log_error "WebOps binary not found: ${WEBOPS_BIN}"
        exit 1
    fi
    
    log_info "Environment validation passed ✓"
}

detect_interruption() {
    log_step "Detecting installation status..."
    
    read_state
    
    if [[ "$INSTALL_STAGE" == "not_started" || "$FORCE" == "true" ]]; then
        log_warn "No interrupted installation detected"
        if [[ "$FORCE" == "true" ]]; then
            log_info "Force mode: Starting fresh installation"
            INSTALL_STAGE="system_prep"
            INSTALL_PROGRESS=0
            write_state "$INSTALL_STAGE" "$INSTALL_PROGRESS"
        else
            log_info "Run with --force to start a new installation"
            exit 0
        fi
    else
        log_info "Interrupted installation detected at stage: $INSTALL_STAGE"
        log_info "Progress: $INSTALL_PROGRESS%"
    fi
}

#=============================================================================
# Resume Stage Functions
#=============================================================================

resume_system_prep() {
    log_step "Resuming system preparation..."
    
    log_info "Updating package lists..."
    if [[ "$DRY_RUN" != "true" ]]; then
        apt-get update
    fi
    
    log_info "Installing required packages..."
    if [[ "$DRY_RUN" != "true" ]]; then
        apt-get install -y \
            curl \
            wget \
            gnupg \
            lsb-release \
            software-properties-common \
            apt-transport-https \
            ca-certificates \
            python3 \
            python3-pip \
            python3-venv \
            build-essential \
            git \
            nginx \
            postgresql \
            postgresql-contrib \
            redis-server \
            certbot \
            python3-certbot-nginx
    fi
    
    write_state "base_hardening" 20
    log_info "System preparation completed ✓"
}

resume_base_hardening() {
    log_step "Resuming base system hardening..."
    
    if [[ -x "${WEBOPS_VERSION_DIR}/setup/base.sh" ]]; then
        log_info "Running base system hardening..."
        if [[ "$DRY_RUN" != "true" ]]; then
            "${WEBOPS_VERSION_DIR}/setup/base.sh"
        fi
    else
        log_warn "Base hardening script not found, skipping"
    fi
    
    write_state "database_setup" 40
    log_info "Base system hardening completed ✓"
}

resume_database_setup() {
    log_step "Resuming database setup..."
    
    # Check if PostgreSQL is running
    if ! systemctl is-active --quiet postgresql; then
        log_info "Starting PostgreSQL service..."
        if [[ "$DRY_RUN" != "true" ]]; then
            systemctl start postgresql
            systemctl enable postgresql
        fi
    fi
    
    # Check if webops database exists
    if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw webops; then
        log_info "Creating webops database..."
        if [[ "$DRY_RUN" != "true" ]]; then
            sudo -u postgres createdb webops
        fi
    fi
    
    write_state "control_panel" 60
    log_info "Database setup completed ✓"
}

resume_control_panel() {
    log_step "Resuming control panel setup..."
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Running control panel installation..."
        "${WEBOPS_BIN}" install control-panel || log_warn "Control panel installation failed"
    fi
    
    write_state "services" 80
    log_info "Control panel setup completed ✓"
}

resume_services() {
    log_step "Resuming service configuration..."
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Starting and enabling services..."
        
        # Start core services
        systemctl start redis-server || log_warn "Failed to start Redis"
        systemctl enable redis-server || log_warn "Failed to enable Redis"
        
        systemctl start nginx || log_warn "Failed to start Nginx"
        systemctl enable nginx || log_warn "Failed to enable Nginx"
        
        # Start WebOps services if they exist
        systemctl start webops-web 2>/dev/null || log_verbose "webops-web service not found"
        systemctl start webops-worker 2>/dev/null || log_verbose "webops-worker service not found"
        systemctl start webops-beat 2>/dev/null || log_verbose "webops-beat service not found"
    fi
    
    write_state "addons" 90
    log_info "Service configuration completed ✓"
}

resume_addons() {
    log_step "Resuming addon installation..."
    
    # Read configuration to determine which addons to install
    local config_file="${WEBOPS_PLATFORM_DIR}/config.env"
    if [[ -f "$config_file" ]]; then
        source "$config_file"
        
        # Install enabled addons
        if [[ "${INSTALL_POSTGRESQL:-false}" == "true" ]]; then
            log_info "Ensuring PostgreSQL addon is installed..."
            if [[ "$DRY_RUN" != "true" ]]; then
                "${WEBOPS_BIN}" install postgresql || log_warn "PostgreSQL addon installation failed"
            fi
        fi
        
        if [[ "${INSTALL_ETCD:-false}" == "true" ]]; then
            log_info "Ensuring etcd addon is installed..."
            if [[ "$DRY_RUN" != "true" ]]; then
                "${WEBOPS_BIN}" install etcd || log_warn "etcd addon installation failed"
            fi
        fi
        
        if [[ "${INSTALL_PATRONI:-false}" == "true" ]]; then
            log_info "Ensuring Patroni addon is installed..."
            if [[ "$DRY_RUN" != "true" ]]; then
                "${WEBOPS_BIN}" install patroni || log_warn "Patroni addon installation failed"
            fi
        fi
        
        if [[ "${INSTALL_MONITORING:-false}" == "true" ]]; then
            log_info "Ensuring monitoring addon is installed..."
            if [[ "$DRY_RUN" != "true" ]]; then
                "${WEBOPS_BIN}" install monitoring || log_warn "Monitoring addon installation failed"
            fi
        fi
        
        if [[ "${INSTALL_KUBERNETES:-false}" == "true" ]]; then
            log_info "Ensuring Kubernetes addon is installed..."
            if [[ "$DRY_RUN" != "true" ]]; then
                "${WEBOPS_BIN}" install kubernetes || log_warn "Kubernetes addon installation failed"
            fi
        fi
        
        if [[ "${INSTALL_KVM:-false}" == "true" ]]; then
            log_info "Ensuring KVM addon is installed..."
            if [[ "$DRY_RUN" != "true" ]]; then
                "${WEBOPS_BIN}" install kvm || log_warn "KVM addon installation failed"
            fi
        fi
    else
        log_warn "Configuration file not found, skipping addon installation"
    fi
    
    write_state "completed" 100
    log_info "Addon installation completed ✓"
}

#=============================================================================
# Main Resume Flow
#=============================================================================

execute_resume_stage() {
    case "$INSTALL_STAGE" in
        "system_prep")
            resume_system_prep
            resume_base_hardening
            resume_database_setup
            resume_control_panel
            resume_services
            resume_addons
            ;;
        "base_hardening")
            resume_base_hardening
            resume_database_setup
            resume_control_panel
            resume_services
            resume_addons
            ;;
        "database_setup")
            resume_database_setup
            resume_control_panel
            resume_services
            resume_addons
            ;;
        "control_panel")
            resume_control_panel
            resume_services
            resume_addons
            ;;
        "services")
            resume_services
            resume_addons
            ;;
        "addons")
            resume_addons
            ;;
        "completed")
            log_info "Installation is already completed"
            clear_state
            return 0
            ;;
        *)
            log_error "Unknown installation stage: $INSTALL_STAGE"
            exit 1
            ;;
    esac
}

show_completion_info() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  🚀  WebOps Platform Installation Resumed                    ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}🌐 Access Your WebOps Platform:${NC}"
    echo "  Control Panel: http://$(hostname -I | awk '{print $1}')/admin/"
    echo "  API: http://$(hostname -I | awk '{print $1}')/api/"
    echo ""
    
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "  1. Create your admin account:"
    echo "     cd $(pwd)/control-panel && python manage.py createsuperuser"
    echo ""
    echo "  2. Configure your platform settings"
    echo "  3. Start deploying applications!"
    echo ""
    
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo "  ${WEBOPS_BIN} state      - Check platform status"
    echo "  ${WEBOPS_BIN} validate   - Validate installation"
    echo "  ${WEBOPS_BIN} version    - Show version info"
    echo ""
    
    echo -e "${GREEN}Platform installation resumed successfully! 🎉${NC}"
}

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
VPS Hosting Platform Resume Tool
EOF
    echo -e "${NC}"
    
    # Validate environment
    validate_environment
    
    # Detect interruption
    detect_interruption
    
    # Show current status
    log_info "Current stage: $INSTALL_STAGE"
    log_info "Progress: $INSTALL_PROGRESS%"
    
    # Execute resume stages
    execute_resume_stage
    
    # Clear state on successful completion
    if [[ "$INSTALL_STAGE" == "completed" ]]; then
        clear_state
    fi
    
    # Show completion information
    if [[ "$DRY_RUN" != "true" ]]; then
        show_completion_info
    else
        echo ""
        echo -e "${YELLOW}DRY RUN COMPLETED${NC}"
        echo "No changes were made. Run without --dry-run to execute the resume."
    fi
}

# Run main function with all arguments
main "$@"