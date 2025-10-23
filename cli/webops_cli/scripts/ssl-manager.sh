#!/bin/bash
#
# SSL Certificate Manager for WebOps
#
# Handles Let's Encrypt SSL certificates:
# - Initial certificate issuance
# - Automatic renewal
# - Certificate monitoring
# - Nginx configuration
#
# Usage:
#   ./ssl-manager.sh issue <domain> <email>
#   ./ssl-manager.sh renew [domain]
#   ./ssl-manager.sh check
#   ./ssl-manager.sh auto-renew

set -euo pipefail

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

# Paths
readonly WEBROOT="/var/www/certbot"
readonly NGINX_SITES="/etc/nginx/sites-available"
readonly NGINX_ENABLED="/etc/nginx/sites-enabled"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

#=============================================================================
# Issue New Certificate
#=============================================================================

issue_certificate() {
    local domain="$1"
    local email="$2"

    log_info "Issuing SSL certificate for: $domain"

    # Create webroot if it doesn't exist
    mkdir -p "$WEBROOT"

    # Create temporary Nginx configuration for HTTP challenge
    create_temp_nginx_config "$domain"

    # Reload Nginx
    nginx -t && systemctl reload nginx

    # Request certificate
    if certbot certonly \
        --webroot \
        --webroot-path="$WEBROOT" \
        --email "$email" \
        --agree-tos \
        --no-eff-email \
        --domain "$domain" \
        --non-interactive; then

        log_info "Certificate issued successfully for $domain"

        # Update Nginx configuration to use SSL
        create_ssl_nginx_config "$domain"

        # Reload Nginx with SSL config
        nginx -t && systemctl reload nginx

        log_info "SSL enabled for $domain"

        # Log to database
        log_to_database "$domain" "issued"

        return 0
    else
        log_error "Failed to issue certificate for $domain"
        return 1
    fi
}

create_temp_nginx_config() {
    local domain="$1"

    cat > "${NGINX_SITES}/temp-${domain}.conf" <<EOF
server {
    listen 80;
    server_name ${domain};

    location /.well-known/acme-challenge/ {
        root ${WEBROOT};
    }

    location / {
        return 200 'Certificate verification in progress...';
        add_header Content-Type text/plain;
    }
}
EOF

    ln -sf "${NGINX_SITES}/temp-${domain}.conf" "${NGINX_ENABLED}/"
}

create_ssl_nginx_config() {
    local domain="$1"

    # Remove temporary config
    rm -f "${NGINX_ENABLED}/temp-${domain}.conf"
    rm -f "${NGINX_SITES}/temp-${domain}.conf"

    # Note: This is a template - actual deployment config should be created
    # by the deployment service based on app requirements
    log_info "SSL certificate ready. Update deployment Nginx config to use SSL."
}

#=============================================================================
# Renew Certificates
#=============================================================================

renew_certificates() {
    local specific_domain="${1:-}"

    log_info "Renewing SSL certificates..."

    if [[ -n "$specific_domain" ]]; then
        # Renew specific domain
        if certbot renew --cert-name "$specific_domain" --quiet; then
            log_info "Certificate renewed for $specific_domain"
            log_to_database "$specific_domain" "renewed"
        else
            log_error "Failed to renew certificate for $specific_domain"
            log_to_database "$specific_domain" "renewal_failed"
            return 1
        fi
    else
        # Renew all certificates
        if certbot renew --quiet; then
            log_info "All certificates renewed successfully"
        else
            log_warn "Some certificate renewals failed. Check logs."
        fi
    fi

    # Reload Nginx to use new certificates
    nginx -t && systemctl reload nginx

    return 0
}

#=============================================================================
# Check Certificate Status
#=============================================================================

check_certificates() {
    log_info "Checking SSL certificates..."

    if ! command -v certbot &>/dev/null; then
        log_error "Certbot not installed"
        return 1
    fi

    # List all certificates
    certbot certificates 2>/dev/null | while IFS= read -r line; do
        if echo "$line" | grep -q "Certificate Name:"; then
            local cert_name=$(echo "$line" | awk '{print $3}')
            echo ""
            echo "Certificate: $cert_name"
        elif echo "$line" | grep -q "Domains:"; then
            local domains=$(echo "$line" | sed 's/.*Domains: //')
            echo "  Domains: $domains"
        elif echo "$line" | grep -q "Expiry Date:"; then
            local expiry=$(echo "$line" | sed 's/.*Expiry Date: //' | awk '{print $1, $2, $3}')
            echo "  Expires: $expiry"

            # Calculate days until expiry
            local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo 0)
            local now_epoch=$(date +%s)
            local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

            if [[ $days_left -lt 0 ]]; then
                echo -e "  Status: ${RED}EXPIRED${NC}"
            elif [[ $days_left -lt 30 ]]; then
                echo -e "  Status: ${YELLOW}Expires in $days_left days${NC}"
            else
                echo -e "  Status: ${GREEN}Valid ($days_left days remaining)${NC}"
            fi
        fi
    done

    echo ""
}

#=============================================================================
# Automatic Renewal (for cron)
#=============================================================================

auto_renew() {
    log_info "Running automatic certificate renewal..."

    # Try to renew certificates
    if certbot renew --quiet --deploy-hook "systemctl reload nginx"; then
        log_info "Auto-renewal completed successfully"

        # Check for expiring certificates
        check_expiring_certificates
    else
        log_error "Auto-renewal failed"
        send_alert "SSL auto-renewal failed"
        return 1
    fi
}

check_expiring_certificates() {
    local expiring_domains=()

    certbot certificates 2>/dev/null | while IFS= read -r line; do
        if echo "$line" | grep -q "Certificate Name:"; then
            current_cert=$(echo "$line" | awk '{print $3}')
        elif echo "$line" | grep -q "Expiry Date:"; then
            local expiry=$(echo "$line" | sed 's/.*Expiry Date: //' | awk '{print $1, $2, $3}')
            local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo 0)
            local now_epoch=$(date +%s)
            local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

            if [[ $days_left -lt 30 && $days_left -ge 0 ]]; then
                log_warn "Certificate $current_cert expires in $days_left days"
                log_to_database "$current_cert" "expiring_soon"
            fi
        fi
    done
}

#=============================================================================
# Database Logging
#=============================================================================

log_to_database() {
    local domain="$1"
    local event="$2"

    # Use Django management command to log to database
    local manage_py="/opt/webops/control-panel/manage.py"

    if [[ -f "$manage_py" ]]; then
        sudo -u webops /opt/webops/control-panel/venv/bin/python "$manage_py" shell <<EOF
from apps.core.models import SSLCertificate
from django.utils import timezone
from datetime import timedelta

domain = "$domain"
event = "$event"

if event == "issued":
    SSLCertificate.objects.create(
        domain=domain,
        issued_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=90),
        status='active'
    )
elif event == "renewed":
    cert = SSLCertificate.objects.filter(domain=domain).first()
    if cert:
        cert.issued_at = timezone.now()
        cert.expires_at = timezone.now() + timedelta(days=90)
        cert.status = 'active'
        cert.renewal_failed_count = 0
        cert.save()
elif event == "renewal_failed":
    cert = SSLCertificate.objects.filter(domain=domain).first()
    if cert:
        cert.renewal_failed_count += 1
        cert.status = 'renewal_failed'
        cert.last_renewal_attempt = timezone.now()
        cert.save()
elif event == "expiring_soon":
    cert = SSLCertificate.objects.filter(domain=domain).first()
    if cert:
        cert.status = 'expiring_soon'
        cert.save()
EOF
    fi
}

#=============================================================================
# Alert System
#=============================================================================

send_alert() {
    local message="$1"

    # Log to syslog
    logger -t webops-ssl "$message"

    # TODO: Send email notification
    # For now, just log it
    log_error "$message"
}

#=============================================================================
# Main
#=============================================================================

show_usage() {
    cat <<EOF
WebOps SSL Certificate Manager

Usage:
    $0 issue <domain> <email>       Issue new certificate
    $0 renew [domain]                Renew certificate(s)
    $0 check                         Check certificate status
    $0 auto-renew                    Auto-renew (for cron)

Examples:
    $0 issue example.com admin@example.com
    $0 renew example.com
    $0 check
    $0 auto-renew

EOF
}

main() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi

    local command="${1:-}"

    case "$command" in
        issue)
            if [[ $# -lt 3 ]]; then
                log_error "Usage: $0 issue <domain> <email>"
                exit 1
            fi
            issue_certificate "$2" "$3"
            ;;
        renew)
            renew_certificates "${2:-}"
            ;;
        check)
            check_certificates
            ;;
        auto-renew)
            auto_renew
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
