#!/bin/bash
#
# WebOps User Security Audit Script
# Performs security checks specific to the webops user configuration
#
# Usage: sudo ./scripts/webops-security-check.sh
#

set -euo pipefail

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly NC='\033[0m' # No Color

# Configuration
readonly WEBOPS_USER="webops"
readonly WEBOPS_DIR="${WEBOPS_DIR:-/opt/webops}"
readonly REPORT_FILE="/var/log/webops-security-check-$(date +%Y%m%d_%H%M%S).log"

# Severity counters
CRITICAL=0
HIGH=0
MEDIUM=0
LOW=0
INFO=0

#=============================================================================
# Logging Functions
#=============================================================================

log_critical() {
    echo -e "${RED}[CRITICAL]${NC} $1" | tee -a "$REPORT_FILE"
    CRITICAL=$((CRITICAL + 1))
}

log_high() {
    echo -e "${RED}[HIGH]${NC} $1" | tee -a "$REPORT_FILE"
    HIGH=$((HIGH + 1))
}

log_medium() {
    echo -e "${YELLOW}[MEDIUM]${NC} $1" | tee -a "$REPORT_FILE"
    MEDIUM=$((MEDIUM + 1))
}

log_low() {
    echo -e "${YELLOW}[LOW]${NC} $1" | tee -a "$REPORT_FILE"
    LOW=$((LOW + 1))
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$REPORT_FILE"
    INFO=$((INFO + 1))
}

log_section() {
    echo "" | tee -a "$REPORT_FILE"
    echo -e "${BLUE}═══ $1 ═══${NC}" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"
}

#=============================================================================
# Security Checks
#=============================================================================

check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}ERROR: This script must be run as root${NC}"
        exit 1
    fi
}

check_user_password() {
    log_section "User Password Security"

    # Check if password is set
    local passwd_status=$(passwd -S "$WEBOPS_USER" 2>/dev/null | awk '{print $2}')

    if [[ "$passwd_status" == "NP" || "$passwd_status" == "L" ]]; then
        log_info "User has no password (NP) or locked password (L) - SECURE ✓"
    elif [[ "$passwd_status" == "P" ]]; then
        log_critical "User has a password set - security risk! Should have no password."
        echo "  Fix: sudo passwd -l $WEBOPS_USER"
    else
        log_medium "Unable to determine password status: $passwd_status"
    fi

    # Check if user can login
    if sudo -u "$WEBOPS_USER" -i echo "test" &>/dev/null; then
        log_high "User can login interactively - potential security risk"
        echo "  Fix: sudo passwd -l $WEBOPS_USER"
    else
        log_info "User cannot login interactively - SECURE ✓"
    fi
}

check_ssh_access() {
    log_section "SSH Access"

    # Check if SSH key exists
    if [[ -f "$WEBOPS_DIR/.ssh/authorized_keys" ]]; then
        local key_count=$(wc -l < "$WEBOPS_DIR/.ssh/authorized_keys")
        log_high "SSH authorized_keys file exists with $key_count key(s)"
        echo "  Location: $WEBOPS_DIR/.ssh/authorized_keys"
        echo "  Review keys and remove if not needed"
    else
        log_info "No SSH authorized_keys file - SECURE ✓"
    fi

    # Check SSH daemon configuration
    if grep -q "^AllowUsers.*$WEBOPS_USER" /etc/ssh/sshd_config 2>/dev/null; then
        log_medium "User explicitly allowed in SSH configuration"
    fi

    if grep -q "^DenyUsers.*$WEBOPS_USER" /etc/ssh/sshd_config 2>/dev/null; then
        log_info "User explicitly denied in SSH configuration - SECURE ✓"
    fi
}

check_sudo_configuration() {
    log_section "Sudo Configuration Security"

    local sudoers_file="/etc/sudoers.d/webops"

    if [[ ! -f "$sudoers_file" ]]; then
        log_critical "Sudoers file missing: $sudoers_file"
        return
    fi

    # Check file permissions
    local perms=$(stat -c '%a' "$sudoers_file")
    if [[ "$perms" == "440" || "$perms" == "400" ]]; then
        log_info "Sudoers file permissions correct: $perms ✓"
    else
        log_high "Sudoers file permissions incorrect: $perms (should be 440)"
    fi

    # Check ownership
    local owner=$(stat -c '%U:%G' "$sudoers_file")
    if [[ "$owner" == "root:root" ]]; then
        log_info "Sudoers file ownership correct: $owner ✓"
    else
        log_critical "Sudoers file ownership incorrect: $owner (should be root:root)"
    fi

    # Check for dangerous patterns
    if grep -q "NOPASSWD.*ALL" "$sudoers_file"; then
        log_critical "Sudoers contains 'NOPASSWD: ALL' - full root access!"
        grep "NOPASSWD.*ALL" "$sudoers_file" | sed 's/^/  /'
    fi

    if grep -q "$WEBOPS_USER.*ALL.*ALL" "$sudoers_file"; then
        log_critical "Sudoers grants unrestricted sudo access!"
    fi

    # Check for specific commands
    local allowed_commands=$(grep "^$WEBOPS_USER.*NOPASSWD:" "$sudoers_file" | wc -l)
    log_info "Sudoers allows $allowed_commands specific commands"

    # Validate syntax
    if ! visudo -c -f "$sudoers_file" &>/dev/null; then
        log_critical "Sudoers file has syntax errors!"
        visudo -c -f "$sudoers_file"
    else
        log_info "Sudoers syntax valid ✓"
    fi
}

check_file_permissions() {
    log_section "File Permissions"

    # Check for world-readable .env files
    local env_count=$(find "$WEBOPS_DIR" -name ".env" -type f -perm /o+r 2>/dev/null | wc -l)
    if [[ $env_count -gt 0 ]]; then
        log_high "Found $env_count .env files with world-readable permissions"
        find "$WEBOPS_DIR" -name ".env" -type f -perm /o+r 2>/dev/null | sed 's/^/  /'
    else
        log_info "No world-readable .env files ✓"
    fi

    # Check .secrets directory
    if [[ -d "$WEBOPS_DIR/.secrets" ]]; then
        local secrets_perms=$(stat -c '%a' "$WEBOPS_DIR/.secrets")
        if [[ "$secrets_perms" == "700" ]]; then
            log_info ".secrets directory permissions: $secrets_perms ✓"
        else
            log_high ".secrets directory permissions: $secrets_perms (should be 700)"
        fi
    fi

    # Check for setuid/setgid binaries
    local setuid_count=$(find "$WEBOPS_DIR" -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | wc -l)
    if [[ $setuid_count -gt 0 ]]; then
        log_high "Found $setuid_count setuid/setgid files (privilege escalation risk)"
        find "$WEBOPS_DIR" -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | sed 's/^/  /'
    else
        log_info "No setuid/setgid files ✓"
    fi

    # Check for world-writable files (excluding tmp)
    local writable_count=$(find "$WEBOPS_DIR" -type f -perm -o+w ! -path "*/tmp/*" 2>/dev/null | wc -l)
    if [[ $writable_count -gt 0 ]]; then
        log_medium "Found $writable_count world-writable files"
        find "$WEBOPS_DIR" -type f -perm -o+w ! -path "*/tmp/*" 2>/dev/null | head -10 | sed 's/^/  /'
    else
        log_info "No world-writable files ✓"
    fi
}

check_process_security() {
    log_section "Process Security"

    # Check if processes are running as webops
    local process_count=$(ps aux | grep -v grep | grep "^$WEBOPS_USER" | wc -l)
    log_info "Found $process_count processes running as $WEBOPS_USER"

    # Check if any processes are running as root that shouldn't be
    if ps aux | grep -v grep | grep webops | grep "^root" | grep -v "sudo\|systemctl" &>/dev/null; then
        log_high "Found webops-related processes running as root:"
        ps aux | grep -v grep | grep webops | grep "^root" | sed 's/^/  /'
    else
        log_info "No webops processes running as root ✓"
    fi

    # Check systemd service user configuration
    for service in webops-web webops-celery webops-celerybeat; do
        if systemctl list-unit-files | grep -q "${service}.service"; then
            local service_user=$(systemctl show "$service" -p User --value 2>/dev/null)
            if [[ "$service_user" == "$WEBOPS_USER" ]]; then
                log_info "Service $service runs as $WEBOPS_USER ✓"
            elif [[ "$service_user" == "root" || -z "$service_user" ]]; then
                log_high "Service $service runs as root (should be $WEBOPS_USER)"
            fi
        fi
    done
}

check_sudo_usage() {
    log_section "Sudo Usage Audit"

    # Check recent sudo commands
    local sudo_count=$(grep "webops.*sudo.*COMMAND" /var/log/auth.log 2>/dev/null | wc -l)
    log_info "Found $sudo_count sudo commands in auth.log"

    # Check for failed sudo attempts
    local failed_count=$(grep "webops.*NOT in sudoers" /var/log/auth.log 2>/dev/null | wc -l)
    if [[ $failed_count -gt 0 ]]; then
        log_high "Found $failed_count failed sudo attempts (unauthorized commands)"
        grep "webops.*NOT in sudoers" /var/log/auth.log 2>/dev/null | tail -5 | sed 's/^/  /'
    else
        log_info "No failed sudo attempts ✓"
    fi

    # Check for unusual commands
    if grep "webops.*sudo.*COMMAND" /var/log/auth.log 2>/dev/null | grep -v "systemctl\|nginx\|certbot\|cp\|ln\|rm" &>/dev/null; then
        log_medium "Found unusual sudo commands:"
        grep "webops.*sudo.*COMMAND" /var/log/auth.log 2>/dev/null | \
            grep -v "systemctl\|nginx\|certbot\|cp\|ln\|rm" | \
            tail -5 | sed 's/^/  /'
    else
        log_info "All sudo commands appear standard ✓"
    fi
}

check_network_exposure() {
    log_section "Network Exposure"

    # Check if webops services are listening on external interfaces
    if ss -tlnp | grep "$WEBOPS_USER" | grep -v "127.0.0.1\|localhost\|::1" &>/dev/null; then
        log_medium "Webops services listening on external interfaces:"
        ss -tlnp | grep "$WEBOPS_USER" | grep -v "127.0.0.1\|localhost\|::1" | sed 's/^/  /'
    else
        log_info "No services listening on external interfaces ✓"
    fi
}

check_credential_storage() {
    log_section "Credential Storage"

    # Check for plain text credentials in .env files
    if find "$WEBOPS_DIR" -name ".env" -type f -exec grep -l "PASSWORD\|SECRET\|KEY\|TOKEN" {} \; 2>/dev/null | head -1 &>/dev/null; then
        log_info "Found .env files with credentials (expected)"
        local env_file_count=$(find "$WEBOPS_DIR" -name ".env" -type f | wc -l)
        echo "  Count: $env_file_count files"

        # Check if they're readable by others
        if find "$WEBOPS_DIR" -name ".env" -type f -perm /o+r 2>/dev/null | head -1 &>/dev/null; then
            log_critical "Some .env files are world-readable!"
        else
            log_info ".env files have restricted permissions ✓"
        fi
    fi

    # Check .secrets directory
    if [[ -d "$WEBOPS_DIR/.secrets" ]]; then
        local secrets_count=$(find "$WEBOPS_DIR/.secrets" -type f 2>/dev/null | wc -l)
        log_info "Found $secrets_count files in .secrets directory"

        # Check permissions
        if find "$WEBOPS_DIR/.secrets" -type f -perm /o+r 2>/dev/null | head -1 &>/dev/null; then
            log_critical "Some secrets files are world-readable!"
        else
            log_info "Secrets files have restricted permissions ✓"
        fi
    fi
}

check_cron_jobs() {
    log_section "Cron Jobs"

    # Check webops user crontab
    if crontab -u "$WEBOPS_USER" -l &>/dev/null; then
        log_info "User has crontab configured"
        echo "  Contents:"
        crontab -u "$WEBOPS_USER" -l 2>/dev/null | grep -v "^#" | sed 's/^/    /'
    else
        log_info "No user crontab configured"
    fi

    # Check system cron for webops tasks
    if grep -r "webops" /etc/cron.* 2>/dev/null | head -1 &>/dev/null; then
        log_info "Found webops tasks in system cron:"
        grep -r "webops" /etc/cron.* 2>/dev/null | sed 's/^/  /'
    fi
}

check_group_memberships() {
    log_section "Group Memberships"

    local groups=$(id -Gn "$WEBOPS_USER")
    log_info "User groups: $groups"

    # Check for dangerous groups
    local dangerous_groups="sudo wheel adm admin"
    for group in $dangerous_groups; do
        if id -Gn "$WEBOPS_USER" | grep -qw "$group"; then
            log_critical "User is member of privileged group: $group"
        fi
    done

    # Check expected groups
    if id -Gn "$WEBOPS_USER" | grep -qw "www-data"; then
        log_info "Member of www-data group ✓"
    else
        log_low "Not member of www-data group (may affect nginx)"
    fi

    if id -Gn "$WEBOPS_USER" | grep -qw "postgres"; then
        log_info "Member of postgres group ✓"
    else
        log_low "Not member of postgres group (may affect database operations)"
    fi
}

generate_summary() {
    log_section "SECURITY AUDIT SUMMARY"

    local total=$((CRITICAL + HIGH + MEDIUM + LOW + INFO))

    echo -e "${MAGENTA}Severity Breakdown:${NC}" | tee -a "$REPORT_FILE"
    echo -e "  ${RED}Critical:${NC} $CRITICAL" | tee -a "$REPORT_FILE"
    echo -e "  ${RED}High:${NC}     $HIGH" | tee -a "$REPORT_FILE"
    echo -e "  ${YELLOW}Medium:${NC}   $MEDIUM" | tee -a "$REPORT_FILE"
    echo -e "  ${YELLOW}Low:${NC}      $LOW" | tee -a "$REPORT_FILE"
    echo -e "  ${GREEN}Info:${NC}     $INFO" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"

    # Overall assessment
    if [[ $CRITICAL -gt 0 ]]; then
        echo -e "${RED}OVERALL: CRITICAL ISSUES FOUND${NC}" | tee -a "$REPORT_FILE"
        echo "Action required immediately!" | tee -a "$REPORT_FILE"
    elif [[ $HIGH -gt 0 ]]; then
        echo -e "${RED}OVERALL: HIGH PRIORITY ISSUES FOUND${NC}" | tee -a "$REPORT_FILE"
        echo "Address high priority issues as soon as possible" | tee -a "$REPORT_FILE"
    elif [[ $MEDIUM -gt 0 ]]; then
        echo -e "${YELLOW}OVERALL: MEDIUM PRIORITY ISSUES FOUND${NC}" | tee -a "$REPORT_FILE"
        echo "Review and address medium priority issues" | tee -a "$REPORT_FILE"
    else
        echo -e "${GREEN}OVERALL: SECURITY POSTURE GOOD${NC}" | tee -a "$REPORT_FILE"
        echo "No critical or high priority issues found" | tee -a "$REPORT_FILE"
    fi

    echo "" | tee -a "$REPORT_FILE"
    echo "Full report saved to: $REPORT_FILE" | tee -a "$REPORT_FILE"
}

#=============================================================================
# Main Execution
#=============================================================================

main() {
    check_root

    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║          WebOps User Security Audit                        ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Initialize report file
    {
        echo "WebOps User Security Audit Report"
        echo "Generated: $(date)"
        echo "Hostname: $(hostname)"
        echo "User: $WEBOPS_USER"
        echo ""
    } > "$REPORT_FILE"

    # Run all checks
    check_user_password
    check_ssh_access
    check_sudo_configuration
    check_file_permissions
    check_process_security
    check_sudo_usage
    check_network_exposure
    check_credential_storage
    check_cron_jobs
    check_group_memberships

    # Generate summary
    generate_summary

    # Exit with error code if critical issues found
    if [[ $CRITICAL -gt 0 ]]; then
        exit 2
    elif [[ $HIGH -gt 0 ]]; then
        exit 1
    fi
}

main "$@"
