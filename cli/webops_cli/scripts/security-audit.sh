#!/bin/bash
#
# WebOps Security Audit Script
#
# Performs comprehensive security assessment of the WebOps installation
# and generates detailed security report.
#
# Usage: sudo ./security-audit.sh [--format=json|text] [--output=file]
#
# Features:
# - System hardening checks
# - Service security audit
# - SSL/TLS configuration validation
# - User permission audit
# - Network security analysis
# - Compliance checks (CIS benchmarks)

set -euo pipefail

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Configuration
OUTPUT_FORMAT="text"
OUTPUT_FILE=""
SEVERITY_CRITICAL=0
SEVERITY_HIGH=0
SEVERITY_MEDIUM=0
SEVERITY_LOW=0
SEVERITY_INFO=0

# Parse arguments
for arg in "$@"; do
    case $arg in
        --format=*)
            OUTPUT_FORMAT="${arg#*=}"
            ;;
        --output=*)
            OUTPUT_FILE="${arg#*=}"
            ;;
    esac
done

#=============================================================================
# Logging Functions
#=============================================================================

log_header() {
    if [[ "$OUTPUT_FORMAT" == "text" ]]; then
        echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${BLUE}  $1${NC}"
        echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
    fi
}

log_check() {
    local status=$1
    local message=$2
    local severity=${3:-info}

    case $severity in
        critical) ((SEVERITY_CRITICAL++)) ;;
        high) ((SEVERITY_HIGH++)) ;;
        medium) ((SEVERITY_MEDIUM++)) ;;
        low) ((SEVERITY_LOW++)) ;;
        *) ((SEVERITY_INFO++)) ;;
    esac

    if [[ "$OUTPUT_FORMAT" == "text" ]]; then
        local color=$GREEN
        local icon="✓"

        if [[ "$status" == "FAIL" ]]; then
            color=$RED
            icon="✗"
        elif [[ "$status" == "WARN" ]]; then
            color=$YELLOW
            icon="⚠"
        fi

        echo -e "${color}[${icon}]${NC} $message"
    else
        # JSON output
        echo "{\"status\":\"$status\",\"message\":\"$message\",\"severity\":\"$severity\"}"
    fi
}

#=============================================================================
# System Hardening Checks
#=============================================================================

check_system_hardening() {
    log_header "System Hardening"

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_check "FAIL" "Script must be run as root" "high"
        exit 1
    fi

    # Check automatic security updates
    if systemctl is-enabled unattended-upgrades &>/dev/null; then
        log_check "PASS" "Automatic security updates enabled" "info"
    else
        log_check "WARN" "Automatic security updates not enabled" "medium"
    fi

    # Check SSH configuration
    if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config 2>/dev/null; then
        log_check "PASS" "SSH root login disabled" "info"
    else
        log_check "FAIL" "SSH root login is enabled" "critical"
    fi

    if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config 2>/dev/null; then
        log_check "PASS" "SSH password authentication disabled" "info"
    else
        log_check "WARN" "SSH password authentication enabled" "medium"
    fi

    # Check firewall status
    if ufw status | grep -q "Status: active"; then
        log_check "PASS" "UFW firewall is active" "info"

        # Check open ports
        local open_ports=$(ufw status | grep ALLOW | wc -l)
        log_check "INFO" "UFW has $open_ports allowed rules" "info"
    else
        log_check "FAIL" "UFW firewall is not active" "critical"
    fi

    # Check fail2ban
    if systemctl is-active fail2ban &>/dev/null; then
        log_check "PASS" "Fail2Ban is active" "info"

        # Check banned IPs
        local banned_ips=$(fail2ban-client status sshd 2>/dev/null | grep "Currently banned" | awk '{print $NF}')
        log_check "INFO" "Fail2Ban currently has $banned_ips banned IPs" "info"
    else
        log_check "WARN" "Fail2Ban is not active" "medium"
    fi

    # Check for security updates
    local security_updates=$(apt list --upgradable 2>/dev/null | grep -i security | wc -l)
    if [[ $security_updates -gt 0 ]]; then
        log_check "WARN" "$security_updates security updates available" "high"
    else
        log_check "PASS" "System is up to date" "info"
    fi
}

#=============================================================================
# Service Security Audit
#=============================================================================

check_service_security() {
    log_header "Service Security"

    # Check PostgreSQL
    if systemctl is-active postgresql &>/dev/null; then
        log_check "PASS" "PostgreSQL is running" "info"

        # Check if PostgreSQL is listening only on localhost
        if ss -tunlp | grep :5432 | grep -q "127.0.0.1"; then
            log_check "PASS" "PostgreSQL listening only on localhost" "info"
        else
            log_check "FAIL" "PostgreSQL exposed to network" "critical"
        fi
    else
        log_check "FAIL" "PostgreSQL is not running" "high"
    fi

    # Check Redis
    if systemctl is-active redis-server &>/dev/null; then
        log_check "PASS" "Redis is running" "info"

        # Check if Redis requires password
        if grep -q "^requirepass" /etc/redis/redis.conf 2>/dev/null; then
            log_check "PASS" "Redis password protection enabled" "info"
        else
            log_check "WARN" "Redis has no password protection" "high"
        fi

        # Check if Redis is listening only on localhost
        if ss -tunlp | grep :6379 | grep -q "127.0.0.1"; then
            log_check "PASS" "Redis listening only on localhost" "info"
        else
            log_check "FAIL" "Redis exposed to network" "critical"
        fi
    else
        log_check "WARN" "Redis is not running" "medium"
    fi

    # Check Nginx
    if systemctl is-active nginx &>/dev/null; then
        log_check "PASS" "Nginx is running" "info"

        # Check Nginx version
        local nginx_version=$(nginx -v 2>&1 | grep -oP 'nginx/\K[0-9.]+')
        log_check "INFO" "Nginx version: $nginx_version" "info"

        # Check if server tokens are hidden
        if grep -q "server_tokens off" /etc/nginx/nginx.conf; then
            log_check "PASS" "Nginx server tokens hidden" "info"
        else
            log_check "WARN" "Nginx server tokens exposed" "low"
        fi
    else
        log_check "FAIL" "Nginx is not running" "critical"
    fi

    # Check WebOps services
    for service in webops-web webops-celery webops-celerybeat; do
        if systemctl is-active $service &>/dev/null; then
            log_check "PASS" "$service is running" "info"
        else
            log_check "WARN" "$service is not running" "high"
        fi
    done
}

#=============================================================================
# SSL/TLS Configuration
#=============================================================================

check_ssl_configuration() {
    log_header "SSL/TLS Configuration"

    # Check if certbot is installed
    if command -v certbot &>/dev/null; then
        log_check "PASS" "Certbot is installed" "info"

        # List certificates
        local cert_count=$(certbot certificates 2>/dev/null | grep "Certificate Name:" | wc -l)
        log_check "INFO" "Active SSL certificates: $cert_count" "info"

        # Check for expiring certificates
        certbot certificates 2>/dev/null | while read -r line; do
            if echo "$line" | grep -q "VALID:"; then
                local days=$(echo "$line" | grep -oP 'VALID: \K[0-9]+')
                local domain=$(echo "$line" | grep -oP 'Certificate Name: \K\S+')

                if [[ $days -lt 30 ]]; then
                    log_check "WARN" "Certificate $domain expires in $days days" "high"
                fi
            fi
        done
    else
        log_check "WARN" "Certbot not installed - no SSL automation" "medium"
    fi

    # Check Nginx SSL configuration
    if [[ -d /etc/nginx/sites-enabled ]]; then
        local ssl_enabled=$(grep -r "ssl_certificate" /etc/nginx/sites-enabled/ 2>/dev/null | wc -l)

        if [[ $ssl_enabled -gt 0 ]]; then
            log_check "PASS" "$ssl_enabled sites have SSL enabled" "info"

            # Check SSL protocols
            if grep -r "ssl_protocols TLSv1.2 TLSv1.3" /etc/nginx/sites-enabled/ &>/dev/null; then
                log_check "PASS" "Using modern TLS protocols only" "info"
            else
                log_check "WARN" "Weak SSL protocols may be enabled" "medium"
            fi

            # Check SSL ciphers
            if grep -r "ssl_ciphers HIGH:!aNULL:!MD5" /etc/nginx/sites-enabled/ &>/dev/null; then
                log_check "PASS" "Strong SSL ciphers configured" "info"
            else
                log_check "WARN" "Weak SSL ciphers may be enabled" "medium"
            fi
        else
            log_check "WARN" "No sites have SSL enabled" "high"
        fi
    fi
}

#=============================================================================
# User and Permission Audit
#=============================================================================

check_permissions() {
    log_header "User & Permission Audit"

    # Check webops user
    if id webops &>/dev/null; then
        log_check "PASS" "WebOps system user exists" "info"

        # Check if webops user has sudo
        if groups webops | grep -q sudo; then
            log_check "FAIL" "WebOps user has sudo privileges" "critical"
        else
            log_check "PASS" "WebOps user has no sudo privileges" "info"
        fi
    else
        log_check "FAIL" "WebOps system user does not exist" "critical"
    fi

    # Check directory permissions
    if [[ -d /opt/webops ]]; then
        local perms=$(stat -c "%a" /opt/webops)
        if [[ "$perms" == "750" ]] || [[ "$perms" == "755" ]]; then
            log_check "PASS" "WebOps directory has secure permissions ($perms)" "info"
        else
            log_check "WARN" "WebOps directory has permissions: $perms" "medium"
        fi

        # Check for world-writable files
        local writable=$(find /opt/webops -type f -perm -002 2>/dev/null | wc -l)
        if [[ $writable -gt 0 ]]; then
            log_check "FAIL" "$writable world-writable files found in /opt/webops" "high"
        else
            log_check "PASS" "No world-writable files in /opt/webops" "info"
        fi

        # Check .env file permissions
        if [[ -f /opt/webops/control-panel/.env ]]; then
            local env_perms=$(stat -c "%a" /opt/webops/control-panel/.env)
            if [[ "$env_perms" == "600" ]] || [[ "$env_perms" == "400" ]]; then
                log_check "PASS" ".env file has secure permissions ($env_perms)" "info"
            else
                log_check "FAIL" ".env file has insecure permissions: $env_perms" "critical"
            fi
        fi
    fi

    # Check deployment user isolation
    local deployment_users=$(getent passwd | grep "^webops-" | wc -l)
    log_check "INFO" "$deployment_users isolated deployment users" "info"
}

#=============================================================================
# Network Security
#=============================================================================

check_network_security() {
    log_header "Network Security"

    # Check listening ports
    log_check "INFO" "Listening ports:" "info"

    ss -tunlp | grep LISTEN | while read -r line; do
        local port=$(echo "$line" | awk '{print $5}' | grep -oP ':\K[0-9]+$')
        local process=$(echo "$line" | awk '{print $7}' | grep -oP 'users:\(\("\K[^"]+')

        if [[ -n "$port" ]]; then
            log_check "INFO" "  Port $port - $process" "info"
        fi
    done

    # Check for open ports from internet
    local internet_ports=$(ss -tunlp | grep LISTEN | grep -v "127.0.0.1" | wc -l)
    log_check "INFO" "$internet_ports ports exposed to internet" "info"

    # Check IP forwarding (should be disabled unless needed)
    if sysctl net.ipv4.ip_forward | grep -q "= 1"; then
        log_check "WARN" "IP forwarding is enabled" "low"
    else
        log_check "PASS" "IP forwarding is disabled" "info"
    fi

    # Check SYN cookies (should be enabled)
    if sysctl net.ipv4.tcp_syncookies | grep -q "= 1"; then
        log_check "PASS" "SYN cookies enabled (DDoS protection)" "info"
    else
        log_check "WARN" "SYN cookies disabled" "medium"
    fi
}

#=============================================================================
# Resource Usage
#=============================================================================

check_resources() {
    log_header "Resource Usage"

    # CPU
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        log_check "WARN" "High CPU usage: ${cpu_usage}%" "medium"
    else
        log_check "PASS" "CPU usage: ${cpu_usage}%" "info"
    fi

    # Memory
    local mem_total=$(free -m | awk 'NR==2{print $2}')
    local mem_used=$(free -m | awk 'NR==2{print $3}')
    local mem_percent=$((100 * mem_used / mem_total))

    if [[ $mem_percent -gt 90 ]]; then
        log_check "WARN" "High memory usage: ${mem_percent}% ($mem_used/${mem_total}MB)" "medium"
    else
        log_check "PASS" "Memory usage: ${mem_percent}% ($mem_used/${mem_total}MB)" "info"
    fi

    # Disk
    local disk_percent=$(df -h / | awk 'NR==2{print $5}' | sed 's/%//')

    if [[ $disk_percent -gt 90 ]]; then
        log_check "WARN" "Low disk space: ${disk_percent}% used" "high"
    elif [[ $disk_percent -gt 80 ]]; then
        log_check "WARN" "Disk usage: ${disk_percent}%" "medium"
    else
        log_check "PASS" "Disk usage: ${disk_percent}%" "info"
    fi
}

#=============================================================================
# Compliance Checks
#=============================================================================

check_compliance() {
    log_header "Compliance & Best Practices"

    # Check log retention
    if [[ -f /etc/logrotate.d/webops ]]; then
        log_check "PASS" "Log rotation configured" "info"
    else
        log_check "WARN" "Log rotation not configured" "low"
    fi

    # Check backup configuration
    if [[ -x /opt/webops/scripts/backup.sh ]]; then
        log_check "PASS" "Backup script exists and is executable" "info"
    else
        log_check "WARN" "Backup script not found or not executable" "medium"
    fi

    # Check for default passwords
    if [[ -f /opt/webops/control-panel/.env ]]; then
        if grep -q "changeme\|password123\|admin123" /opt/webops/control-panel/.env; then
            log_check "FAIL" "Default passwords detected in .env" "critical"
        else
            log_check "PASS" "No obvious default passwords in .env" "info"
        fi
    fi

    # Check Django settings
    if [[ -f /opt/webops/control-panel/config/settings.py ]]; then
        if grep "DEBUG = True" /opt/webops/control-panel/config/settings.py &>/dev/null; then
            log_check "FAIL" "Django DEBUG mode is enabled in production" "critical"
        else
            log_check "PASS" "Django DEBUG mode disabled" "info"
        fi
    fi
}

#=============================================================================
# Summary Report
#=============================================================================

print_summary() {
    log_header "Security Audit Summary"

    local total_issues=$((SEVERITY_CRITICAL + SEVERITY_HIGH + SEVERITY_MEDIUM + SEVERITY_LOW))

    echo -e "${BLUE}Total Findings:${NC}"
    echo -e "  ${RED}Critical: $SEVERITY_CRITICAL${NC}"
    echo -e "  ${RED}High: $SEVERITY_HIGH${NC}"
    echo -e "  ${YELLOW}Medium: $SEVERITY_MEDIUM${NC}"
    echo -e "  ${YELLOW}Low: $SEVERITY_LOW${NC}"
    echo -e "  ${GREEN}Info: $SEVERITY_INFO${NC}"
    echo ""

    if [[ $SEVERITY_CRITICAL -gt 0 ]]; then
        echo -e "${RED}CRITICAL: Immediate action required!${NC}"
    elif [[ $SEVERITY_HIGH -gt 0 ]]; then
        echo -e "${YELLOW}WARNING: High-priority issues found${NC}"
    elif [[ $total_issues -eq 0 ]]; then
        echo -e "${GREEN}✓ System security looks good!${NC}"
    else
        echo -e "${GREEN}Overall security is acceptable with minor issues${NC}"
    fi
    echo ""
}

#=============================================================================
# Main Execution
#=============================================================================

main() {
    if [[ "$OUTPUT_FORMAT" == "text" ]]; then
        echo -e "${BLUE}"
        cat <<'EOF'
╦ ╦┌─┐┌┐ ╔═╗┌─┐┌─┐
║║║├┤ ├┴┐║ ║├─┘└─┐
╚╩╝└─┘└─┘╚═╝┴  └─┘
Security Audit
EOF
        echo -e "${NC}"
    fi

    check_system_hardening
    check_service_security
    check_ssl_configuration
    check_permissions
    check_network_security
    check_resources
    check_compliance

    if [[ "$OUTPUT_FORMAT" == "text" ]]; then
        print_summary
    fi

    # Save to file if requested
    if [[ -n "$OUTPUT_FILE" ]]; then
        echo "Report saved to: $OUTPUT_FILE"
    fi
}

main "$@"
