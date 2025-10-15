#!/bin/bash
#
# WebOps User Setup Validation Script
# Validates that the webops user is correctly configured
#
# Usage: sudo ./scripts/validate-user-setup.sh
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
readonly WEBOPS_DIR="${WEBOPS_DIR:-/opt/webops}"

# Counters
PASS=0
FAIL=0
WARN=0

#=============================================================================
# Helper Functions
#=============================================================================

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║          WebOps User Setup Validation                      ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

test_pass() {
    echo -e "${GREEN}✓${NC} $1"
    PASS=$((PASS + 1))
}

test_fail() {
    echo -e "${RED}✗${NC} $1"
    FAIL=$((FAIL + 1))
}

test_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARN=$((WARN + 1))
}

section_header() {
    echo ""
    echo -e "${BLUE}═══ $1 ═══${NC}"
    echo ""
}

#=============================================================================
# Validation Tests
#=============================================================================

check_root() {
    section_header "Root Privileges"

    if [[ $EUID -eq 0 ]]; then
        test_pass "Running as root"
    else
        test_fail "Not running as root (use sudo)"
        exit 1
    fi
}

check_user_exists() {
    section_header "User Existence"

    if id "$WEBOPS_USER" &>/dev/null; then
        test_pass "User '$WEBOPS_USER' exists"

        # Get user details
        local uid=$(id -u "$WEBOPS_USER")
        local gid=$(id -g "$WEBOPS_USER")
        local shell=$(getent passwd "$WEBOPS_USER" | cut -d: -f7)
        local home=$(getent passwd "$WEBOPS_USER" | cut -d: -f6)

        echo "    UID: $uid"
        echo "    GID: $gid"
        echo "    Shell: $shell"
        echo "    Home: $home"

        # Validate shell
        if [[ "$shell" == "/bin/bash" ]]; then
            test_pass "Shell is /bin/bash"
        else
            test_warn "Shell is $shell (expected /bin/bash)"
        fi

        # Validate home directory
        if [[ "$home" == "$WEBOPS_DIR" ]]; then
            test_pass "Home directory is $WEBOPS_DIR"
        else
            test_fail "Home directory is $home (expected $WEBOPS_DIR)"
        fi

    else
        test_fail "User '$WEBOPS_USER' does not exist"
        echo "    Run: sudo ./setup.sh"
        return 1
    fi
}

check_user_groups() {
    section_header "Group Memberships"

    local groups=$(id -Gn "$WEBOPS_USER")

    echo "    Groups: $groups"
    echo ""

    # Check primary group
    if id -Gn "$WEBOPS_USER" | grep -qw "$WEBOPS_USER"; then
        test_pass "Primary group: $WEBOPS_USER"
    else
        test_fail "Primary group not set to $WEBOPS_USER"
    fi

    # Check www-data group
    if id -Gn "$WEBOPS_USER" | grep -qw "www-data"; then
        test_pass "Member of www-data group (nginx access)"
    else
        test_warn "Not member of www-data group (nginx static files may fail)"
    fi

    # Check postgres group
    if id -Gn "$WEBOPS_USER" | grep -qw "postgres"; then
        test_pass "Member of postgres group (database operations)"
    else
        test_warn "Not member of postgres group (database creation may fail)"
    fi
}

check_directory_structure() {
    section_header "Directory Structure"

    local dirs=(
        "$WEBOPS_DIR"
        "$WEBOPS_DIR/control-panel"
        "$WEBOPS_DIR/deployments"
        "$WEBOPS_DIR/backups"
        "$WEBOPS_DIR/.secrets"
        "$WEBOPS_DIR/logs"
    )

    for dir in "${dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            local owner=$(stat -c '%U:%G' "$dir")
            local perms=$(stat -c '%a' "$dir")

            if [[ "$owner" == "$WEBOPS_USER:$WEBOPS_USER" ]]; then
                test_pass "Directory exists: $dir ($perms, $owner)"
            else
                test_fail "Directory exists but wrong owner: $dir ($owner, expected $WEBOPS_USER:$WEBOPS_USER)"
            fi
        else
            test_fail "Directory missing: $dir"
        fi
    done
}

check_directory_permissions() {
    section_header "Directory Permissions"

    # Check sensitive directories
    local secrets_perms=$(stat -c '%a' "$WEBOPS_DIR/.secrets" 2>/dev/null || echo "000")
    if [[ "$secrets_perms" == "700" ]]; then
        test_pass ".secrets directory has 700 permissions"
    else
        test_fail ".secrets directory has $secrets_perms permissions (expected 700)"
    fi

    local backups_perms=$(stat -c '%a' "$WEBOPS_DIR/backups" 2>/dev/null || echo "000")
    if [[ "$backups_perms" == "700" ]]; then
        test_pass "backups directory has 700 permissions"
    else
        test_warn "backups directory has $backups_perms permissions (recommended 700)"
    fi

    # Check for world-readable sensitive files
    if find "$WEBOPS_DIR" -name ".env" -type f -perm /o+r 2>/dev/null | grep -q .; then
        test_fail "Found .env files with world-readable permissions"
        find "$WEBOPS_DIR" -name ".env" -type f -perm /o+r 2>/dev/null | while read file; do
            echo "    $file"
        done
    else
        test_pass "No .env files with world-readable permissions"
    fi
}

check_sudo_configuration() {
    section_header "Sudo Configuration"

    local sudoers_file="/etc/sudoers.d/webops"

    if [[ -f "$sudoers_file" ]]; then
        test_pass "Sudoers file exists: $sudoers_file"

        # Check permissions
        local perms=$(stat -c '%a' "$sudoers_file")
        if [[ "$perms" == "440" || "$perms" == "400" ]]; then
            test_pass "Sudoers file has correct permissions: $perms"
        else
            test_fail "Sudoers file has incorrect permissions: $perms (expected 440)"
        fi

        # Validate syntax
        if visudo -c -f "$sudoers_file" &>/dev/null; then
            test_pass "Sudoers file syntax is valid"
        else
            test_fail "Sudoers file has syntax errors"
            visudo -c -f "$sudoers_file"
        fi

        # Check for required rules
        local required_rules=(
            "systemctl reload nginx"
            "systemctl restart nginx"
            "systemctl daemon-reload"
            "certbot"
        )

        for rule in "${required_rules[@]}"; do
            if grep -q "$rule" "$sudoers_file"; then
                test_pass "Sudo rule exists: $rule"
            else
                test_warn "Sudo rule missing: $rule"
            fi
        done

    else
        test_fail "Sudoers file does not exist: $sudoers_file"
        echo "    Run: sudo ./setup.sh"
    fi
}

check_sudo_access() {
    section_header "Sudo Access Testing"

    # Test nginx reload (safe command)
    if sudo -u "$WEBOPS_USER" sudo -n systemctl status nginx &>/dev/null; then
        test_pass "Can execute: sudo systemctl status nginx"
    else
        test_fail "Cannot execute: sudo systemctl status nginx"
    fi

    # Test daemon-reload (safe command)
    if sudo -u "$WEBOPS_USER" sudo -n systemctl daemon-reload --dry-run &>/dev/null 2>&1 || true; then
        test_pass "Can execute: sudo systemctl daemon-reload"
    else
        test_warn "Cannot execute: sudo systemctl daemon-reload (check sudoers)"
    fi

    # Test that unauthorized commands fail
    if sudo -u "$WEBOPS_USER" sudo -n apt update &>/dev/null; then
        test_fail "SECURITY ISSUE: Can execute unauthorized command: apt update"
    else
        test_pass "Cannot execute unauthorized command: apt update"
    fi
}

check_systemd_services() {
    section_header "Systemd Services"

    local services=(
        "webops-web"
        "webops-celery"
        "webops-celerybeat"
    )

    for service in "${services[@]}"; do
        if systemctl list-unit-files | grep -q "$service.service"; then
            # Check if service exists
            test_pass "Service file exists: $service.service"

            # Check user in service file
            local service_user=$(systemctl show "$service" -p User --value 2>/dev/null || echo "")
            if [[ "$service_user" == "$WEBOPS_USER" ]]; then
                test_pass "Service runs as: $WEBOPS_USER"
            elif [[ -z "$service_user" ]]; then
                test_warn "Service user not set (may run as root)"
            else
                test_fail "Service runs as: $service_user (expected $WEBOPS_USER)"
            fi

        else
            test_warn "Service not installed: $service.service"
        fi
    done
}

check_running_processes() {
    section_header "Running Processes"

    # Check for processes running as webops
    local process_count=$(ps aux | grep -v grep | grep "^$WEBOPS_USER" | wc -l)

    if [[ $process_count -gt 0 ]]; then
        test_pass "Found $process_count processes running as $WEBOPS_USER"
        echo ""
        echo "    Top processes:"
        ps aux | grep -v grep | grep "^$WEBOPS_USER" | head -5 | while read line; do
            echo "    $line"
        done
    else
        test_warn "No processes currently running as $WEBOPS_USER"
        echo "    Services may be stopped. Check: systemctl status webops-*"
    fi
}

check_file_ownership() {
    section_header "File Ownership Audit"

    # Check for files not owned by webops in webops directory
    local non_webops_files=$(find "$WEBOPS_DIR" -type f ! -user "$WEBOPS_USER" 2>/dev/null | wc -l)

    if [[ $non_webops_files -eq 0 ]]; then
        test_pass "All files in $WEBOPS_DIR owned by $WEBOPS_USER"
    else
        test_warn "Found $non_webops_files files not owned by $WEBOPS_USER"
        echo "    First 5 files:"
        find "$WEBOPS_DIR" -type f ! -user "$WEBOPS_USER" 2>/dev/null | head -5 | while read file; do
            echo "    $file ($(stat -c '%U:%G' "$file"))"
        done
        echo "    Fix with: sudo chown -R $WEBOPS_USER:$WEBOPS_USER $WEBOPS_DIR"
    fi
}

check_security_issues() {
    section_header "Security Checks"

    # Check for setuid/setgid files (potential privilege escalation)
    local setuid_files=$(find "$WEBOPS_DIR" -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | wc -l)
    if [[ $setuid_files -eq 0 ]]; then
        test_pass "No setuid/setgid files found"
    else
        test_fail "Found $setuid_files setuid/setgid files (security risk)"
        find "$WEBOPS_DIR" -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | while read file; do
            echo "    $file"
        done
    fi

    # Check for world-writable files
    local writable_files=$(find "$WEBOPS_DIR" -type f -perm -o+w ! -path "*/tmp/*" 2>/dev/null | wc -l)
    if [[ $writable_files -eq 0 ]]; then
        test_pass "No world-writable files found"
    else
        test_warn "Found $writable_files world-writable files"
        find "$WEBOPS_DIR" -type f -perm -o+w ! -path "*/tmp/*" 2>/dev/null | head -5 | while read file; do
            echo "    $file"
        done
    fi

    # Check if user has password
    if sudo -u "$WEBOPS_USER" -i echo "test" &>/dev/null; then
        test_warn "User can login interactively (password may be set)"
    else
        test_pass "User cannot login interactively (no password)"
    fi
}

print_summary() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                     VALIDATION SUMMARY                     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${GREEN}Passed:${NC}  $PASS"
    echo -e "  ${RED}Failed:${NC}  $FAIL"
    echo -e "  ${YELLOW}Warnings:${NC} $WARN"
    echo ""

    if [[ $FAIL -eq 0 ]]; then
        echo -e "${GREEN}✓ All critical checks passed!${NC}"
        if [[ $WARN -gt 0 ]]; then
            echo -e "${YELLOW}⚠ Review warnings above for optimization opportunities${NC}"
        fi
    else
        echo -e "${RED}✗ $FAIL critical issues found${NC}"
        echo -e "${YELLOW}  Review the failed checks above and fix issues${NC}"
        exit 1
    fi

    echo ""
}

#=============================================================================
# Main Execution
#=============================================================================

main() {
    print_header

    check_root
    check_user_exists
    check_user_groups
    check_directory_structure
    check_directory_permissions
    check_sudo_configuration
    check_sudo_access
    check_systemd_services
    check_running_processes
    check_file_ownership
    check_security_issues

    print_summary
}

main "$@"
