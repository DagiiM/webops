#!/bin/bash
#
# WebOps Administration Helper Script
# Provides common administrative tasks for the webops user
#
# Usage: sudo ./scripts/webops-admin.sh [command]
#

set -euo pipefail

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly WEBOPS_USER="webops"
readonly WEBOPS_DIR="/opt/webops"

#=============================================================================
# Helper Functions
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

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

#=============================================================================
# Command Functions
#=============================================================================

cmd_status() {
    echo -e "${BLUE}═══ WebOps User Status ═══${NC}"
    echo ""

    # User info
    echo -e "${BLUE}User Information:${NC}"
    id "$WEBOPS_USER"
    echo ""

    # Processes
    echo -e "${BLUE}Running Processes:${NC}"
    local count=$(ps aux | grep -v grep | grep "^$WEBOPS_USER" | wc -l)
    echo "  Total: $count processes"
    ps aux | grep -v grep | grep "^$WEBOPS_USER" | head -10
    echo ""

    # Services
    echo -e "${BLUE}SystemD Services:${NC}"
    systemctl status 'webops-*' --no-pager -l | head -20 || true
    echo ""

    # Disk usage
    echo -e "${BLUE}Disk Usage:${NC}"
    du -sh "$WEBOPS_DIR"/* 2>/dev/null | sort -h
    echo ""

    # Recent sudo commands
    echo -e "${BLUE}Recent Sudo Commands (last 10):${NC}"
    grep "webops.*sudo.*COMMAND" /var/log/auth.log 2>/dev/null | tail -10 || echo "  No sudo commands found in logs"
}

cmd_shell() {
    log_info "Starting shell as $WEBOPS_USER user..."
    echo ""
    sudo -u "$WEBOPS_USER" -i
}

cmd_run() {
    if [[ $# -eq 0 ]]; then
        log_error "No command specified"
        echo "Usage: $0 run <command>"
        exit 1
    fi

    log_info "Running as $WEBOPS_USER: $*"
    sudo -u "$WEBOPS_USER" bash -c "$*"
}

cmd_fix_permissions() {
    log_info "Fixing file ownership and permissions..."

    # Fix ownership
    log_info "Setting ownership to $WEBOPS_USER:$WEBOPS_USER..."
    chown -R "$WEBOPS_USER:$WEBOPS_USER" "$WEBOPS_DIR"

    # Fix directory permissions
    log_info "Setting directory permissions..."
    chmod 750 "$WEBOPS_DIR"
    chmod 750 "$WEBOPS_DIR/control-panel" 2>/dev/null || true
    chmod 750 "$WEBOPS_DIR/deployments" 2>/dev/null || true
    chmod 700 "$WEBOPS_DIR/backups" 2>/dev/null || true
    chmod 700 "$WEBOPS_DIR/.secrets" 2>/dev/null || true

    # Fix .env file permissions
    log_info "Setting .env file permissions to 600..."
    find "$WEBOPS_DIR" -name ".env" -type f -exec chmod 600 {} \;

    # Fix tmp directory
    if [[ -d "$WEBOPS_DIR/control-panel/tmp" ]]; then
        chmod 1777 "$WEBOPS_DIR/control-panel/tmp"
    fi

    log_info "Permissions fixed ✓"
}

cmd_logs() {
    local service="${1:-}"

    if [[ -z "$service" ]]; then
        echo -e "${BLUE}Available logs:${NC}"
        echo ""
        echo "  Application Logs:"
        ls -1 "$WEBOPS_DIR/logs/" 2>/dev/null | sed 's/^/    /' || echo "    (none)"
        echo ""
        echo "  Service Logs (use: $0 logs <service>):"
        echo "    webops-web"
        echo "    webops-celery"
        echo "    webops-celerybeat"
        echo ""
        echo "  Deployment Logs:"
        find "$WEBOPS_DIR/deployments" -name "*.log" 2>/dev/null | sed 's/^/    /' | head -10
        echo ""
        return
    fi

    # Check if it's a systemd service
    if systemctl list-unit-files | grep -q "^${service}.service"; then
        log_info "Showing logs for $service.service (Ctrl+C to exit)..."
        journalctl -u "$service" -f
    # Check if it's a log file
    elif [[ -f "$WEBOPS_DIR/logs/$service" ]]; then
        log_info "Showing $WEBOPS_DIR/logs/$service (Ctrl+C to exit)..."
        tail -f "$WEBOPS_DIR/logs/$service"
    else
        log_error "Service or log file not found: $service"
        exit 1
    fi
}

cmd_sudo_audit() {
    echo -e "${BLUE}═══ Sudo Command Audit ═══${NC}"
    echo ""

    # Last 24 hours
    echo -e "${BLUE}Last 24 hours:${NC}"
    grep "webops.*sudo.*COMMAND" /var/log/auth.log 2>/dev/null | \
        grep "$(date +%b\ %d)" | \
        tail -20 || echo "  No commands found"
    echo ""

    # Summary
    echo -e "${BLUE}Command Summary (all time):${NC}"
    grep "webops.*sudo.*COMMAND" /var/log/auth.log* 2>/dev/null | \
        awk '{for(i=1;i<=NF;i++) if($i=="COMMAND=") {for(j=i+1;j<=NF;j++) printf "%s ", $j; print ""}}' | \
        sort | uniq -c | sort -rn | head -10 || echo "  No commands found"
    echo ""

    # Failed attempts (security concern)
    echo -e "${BLUE}Failed Sudo Attempts:${NC}"
    local failed=$(grep "webops.*sudo.*NOT in sudoers" /var/log/auth.log* 2>/dev/null | wc -l)
    if [[ $failed -gt 0 ]]; then
        echo -e "${RED}  WARNING: $failed failed sudo attempts detected!${NC}"
        grep "webops.*sudo.*NOT in sudoers" /var/log/auth.log* 2>/dev/null | tail -5
    else
        echo -e "${GREEN}  No failed attempts ✓${NC}"
    fi
}

cmd_validate() {
    local validate_script="/home/douglas/webops/scripts/validate-user-setup.sh"

    if [[ -f "$validate_script" ]]; then
        log_info "Running validation script..."
        bash "$validate_script"
    else
        log_error "Validation script not found: $validate_script"
        exit 1
    fi
}

cmd_list_deployments() {
    echo -e "${BLUE}═══ Deployed Applications ═══${NC}"
    echo ""

    if [[ ! -d "$WEBOPS_DIR/deployments" ]]; then
        log_warn "Deployments directory does not exist"
        return
    fi

    local count=0
    for app_dir in "$WEBOPS_DIR/deployments"/*; do
        if [[ -d "$app_dir" ]]; then
            local app_name=$(basename "$app_dir")
            local size=$(du -sh "$app_dir" 2>/dev/null | cut -f1)
            local service_status="unknown"

            # Check if systemd service exists
            if systemctl list-unit-files | grep -q "^app-${app_name}.service"; then
                if systemctl is-active --quiet "app-${app_name}"; then
                    service_status="${GREEN}running${NC}"
                else
                    service_status="${RED}stopped${NC}"
                fi
            else
                service_status="${YELLOW}no service${NC}"
            fi

            echo -e "  ${BLUE}$app_name${NC}"
            echo "    Path: $app_dir"
            echo "    Size: $size"
            echo -e "    Status: $service_status"
            echo ""

            count=$((count + 1))
        fi
    done

    if [[ $count -eq 0 ]]; then
        log_info "No deployments found"
    else
        log_info "Total: $count deployment(s)"
    fi
}

cmd_backup() {
    local backup_dir="$WEBOPS_DIR/backups/manual"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    mkdir -p "$backup_dir"

    log_info "Creating backup of WebOps directory..."

    # Backup control panel (excluding venv and cache)
    log_info "Backing up control panel..."
    tar -czf "$backup_dir/control-panel-${timestamp}.tar.gz" \
        --exclude="venv" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude="staticfiles" \
        -C "$WEBOPS_DIR" control-panel

    # Backup .secrets
    log_info "Backing up secrets..."
    tar -czf "$backup_dir/secrets-${timestamp}.tar.gz" \
        -C "$WEBOPS_DIR" .secrets

    # Set permissions
    chmod 600 "$backup_dir"/*.tar.gz
    chown "$WEBOPS_USER:$WEBOPS_USER" "$backup_dir"/*.tar.gz

    log_info "Backup complete:"
    ls -lh "$backup_dir"/*-${timestamp}.tar.gz
}

cmd_help() {
    cat << EOF
${BLUE}WebOps Administration Helper${NC}

Usage: sudo $0 <command> [options]

${BLUE}Commands:${NC}

  ${GREEN}status${NC}
    Show webops user status, running processes, and recent activity

  ${GREEN}shell${NC}
    Start interactive shell as webops user

  ${GREEN}run <command>${NC}
    Run a command as webops user
    Example: $0 run "python manage.py shell"

  ${GREEN}fix-permissions${NC}
    Fix file ownership and permissions in /opt/webops

  ${GREEN}logs [service|file]${NC}
    View logs (systemd service or application log file)
    Without argument: list available logs
    Examples:
      $0 logs webops-web      # View webops-web service logs
      $0 logs celery-worker.log  # View celery log file

  ${GREEN}sudo-audit${NC}
    Audit sudo command usage by webops user

  ${GREEN}validate${NC}
    Run comprehensive validation of webops user setup

  ${GREEN}deployments${NC}
    List all deployed applications and their status

  ${GREEN}backup${NC}
    Create manual backup of control panel and secrets

  ${GREEN}help${NC}
    Show this help message

${BLUE}Examples:${NC}

  # Check status
  sudo $0 status

  # Open shell as webops user
  sudo $0 shell

  # Run Django management command
  sudo $0 run "cd /opt/webops/control-panel && source venv/bin/activate && python manage.py migrate"

  # View application logs
  sudo $0 logs webops-web

  # Audit sudo usage
  sudo $0 sudo-audit

  # Fix permissions after manual changes
  sudo $0 fix-permissions

${BLUE}Security:${NC}

  All commands run with appropriate user context.
  Sudo access is limited to specific operations.
  All sudo commands are logged to /var/log/auth.log

${BLUE}Documentation:${NC}

  /home/douglas/webops/docs/WEBOPS-USER-GUIDE.md
  /home/douglas/webops/docs/SECURITY-FEATURES.md

EOF
}

#=============================================================================
# Main Execution
#=============================================================================

main() {
    check_root

    local command="${1:-help}"
    shift || true

    case "$command" in
        status)
            cmd_status "$@"
            ;;
        shell)
            cmd_shell "$@"
            ;;
        run)
            cmd_run "$@"
            ;;
        fix-permissions|fix-perms|perms)
            cmd_fix_permissions "$@"
            ;;
        logs|log)
            cmd_logs "$@"
            ;;
        sudo-audit|audit)
            cmd_sudo_audit "$@"
            ;;
        validate|check)
            cmd_validate "$@"
            ;;
        deployments|apps|list)
            cmd_list_deployments "$@"
            ;;
        backup)
            cmd_backup "$@"
            ;;
        help|-h|--help)
            cmd_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
