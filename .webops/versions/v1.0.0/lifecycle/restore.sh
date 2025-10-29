#!/bin/sh

###############################################################################
# WebOps Secure Restore Script
# 
# Purpose: Safe, dependency-free restore of WebOps backups with rollback capability
# Author: Douglas Mutethia, Eleso Solutions
# Version: 1.0.0
# License: MIT
#
# Philosophy: Minimal dependencies, security-first design, POSIX compliance
###############################################################################

set -euo pipefail

# Script configuration
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly WEBOPS_ROOT="$(dirname "$SCRIPT_DIR" | xargs dirname | xargs dirname)"

# Restore configuration
readonly RESTORE_DATE="$(date +%Y%m%d_%H%M%S)"
readonly RESTORE_LOG="${WEBOPS_ROOT}/logs/restore_${RESTORE_DATE}.log"
readonly ROLLBACK_DIR="${WEBOPS_ROOT}/backups/rollback_${RESTORE_DATE}"
readonly TEMP_DIR="$(mktemp -d -t webops-restore-XXXXXXXXXX)"

# Security settings
umask 077

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly NC='\033[0m' # No Color

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_INVALID_ARGS=1
readonly EXIT_PERMISSION_DENIED=2
readonly EXIT_BACKUP_NOT_FOUND=3
readonly EXIT_VERIFICATION_FAILED=4
readonly EXIT_RESTORE_FAILED=5
readonly EXIT_ROLLBACK_FAILED=6

###############################################################################
# Utility Functions
###############################################################################

# Enhanced logging with syslog integration
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    
    # Ensure log directory exists
    mkdir -p "$(dirname "${RESTORE_LOG}")" 2>/dev/null || true
    
    # Log to file
    echo "[${timestamp}] [${level}] ${message}" >> "${RESTORE_LOG}" 2>/dev/null || true
    
    # Log to syslog if available
    if command -v logger >/dev/null 2>&1; then
        logger -t "webops-restore" -p "user.${level}" "${message}" 2>/dev/null || true
    fi
    
    # Output to console with colors
    case "${level}" in
        ERROR)
            echo "${RED}[ERROR]${NC} ${message}" >&2
            ;;
        WARN)
            echo "${YELLOW}[WARN]${NC} ${message}" >&2
            ;;
        INFO)
            echo "${GREEN}[INFO]${NC} ${message}"
            ;;
        DEBUG)
            echo "${BLUE}[DEBUG]${NC} ${message}"
            ;;
        *)
            echo "${message}"
            ;;
    esac
}

# Check system requirements
check_requirements() {
    log "INFO" "Checking system requirements..."
    
    # Check for required commands
    local required_commands="tar gzip md5sum find ls mkdir rmdir rm sqlite3"
    for cmd in ${required_commands}; do
        if ! command -v "${cmd}" >/dev/null 2>&1; then
            log "ERROR" "Required command not found: ${cmd}"
            exit "${EXIT_INVALID_ARGS}"
        fi
    done
    
    # Check permissions
    if [ ! -w "${WEBOPS_ROOT}" ]; then
        log "ERROR" "Insufficient permissions to write to ${WEBOPS_ROOT}"
        exit "${EXIT_PERMISSION_DENIED}"
    fi
    
    # Check for PostgreSQL utilities if needed
    if [ -f "${1}/backup_metadata.json" ]; then
        local db_type
        db_type="$(grep -o '"database_type": "[^"]*"' "${1}/backup_metadata.json" 2>/dev/null | cut -d'"' -f4)" || db_type="unknown"
        
        if [ "${db_type}" = "postgresql" ]; then
            if ! command -v pg_restore >/dev/null 2>&1; then
                log "WARN" "PostgreSQL restore utilities not found - may not be able to restore PostgreSQL database"
            fi
        fi
    fi
    
    log "INFO" "System requirements check completed"
}

# Verify backup integrity
verify_backup_integrity() {
    local backup_dir="$1"
    local manifest_file="${backup_dir}/backup_manifest.txt"
    local metadata_file="${backup_dir}/backup_metadata.json"
    
    log "INFO" "Verifying backup integrity..."
    
    # Check if backup directory exists and has required files
    if [ ! -d "${backup_dir}" ]; then
        log "ERROR" "Backup directory not found: ${backup_dir}"
        return 1
    fi
    
    # Verify manifest file exists
    if [ ! -f "${manifest_file}" ]; then
        log "ERROR" "Backup manifest not found: ${manifest_file}"
        return 1
    fi
    
    # Verify metadata file exists
    if [ ! -f "${metadata_file}" ]; then
        log "ERROR" "Backup metadata not found: ${metadata_file}"
        return 1
    fi
    
    # Verify all component files exist and match checksums
    local failed_verifications=0
    
    while IFS=': ' read -r component checksum; do
        # Skip comments and empty lines
        case "${component}" in
            \#*|'') continue ;;
        esac
        
        local component_file="${backup_dir}/${component}.tar.gz"
        local checksum_file="${backup_dir}/${component}.md5"
        
        if [ ! -f "${component_file}" ]; then
            log "ERROR" "Component file missing: ${component_file}"
            failed_verifications=$((failed_verifications + 1))
            continue
        fi
        
        if [ ! -f "${checksum_file}" ]; then
            log "ERROR" "Component checksum missing: ${checksum_file}"
            failed_verifications=$((failed_verifications + 1))
            continue
        fi
        
        local expected_checksum
        expected_checksum="$(cat "${checksum_file}")"
        local actual_checksum
        
        if ! actual_checksum="$(md5sum "${component_file}" 2>/dev/null | cut -d' ' -f1)"; then
            log "ERROR" "Failed to calculate checksum for: ${component_file}"
            failed_verifications=$((failed_verifications + 1))
            continue
        fi
        
        if [ "${expected_checksum}" != "${actual_checksum}" ]; then
            log "ERROR" "Checksum verification failed for: ${component}"
            log "ERROR" "Expected: ${expected_checksum}, Got: ${actual_checksum}"
            failed_verifications=$((failed_verifications + 1))
        else
            log "INFO" "Checksum verified: ${component}"
        fi
        
    done < "${manifest_file}"
    
    if [ "${failed_verifications}" -gt 0 ]; then
        log "ERROR" "Backup verification failed: ${failed_verifications} component(s)"
        return 1
    else
        log "INFO" "Backup verification completed successfully"
        return 0
    fi
}

# Display backup metadata
display_backup_metadata() {
    local backup_dir="$1"
    local metadata_file="${backup_dir}/backup_metadata.json"
    
    log "DEBUG" "Displaying backup metadata..."
    
    # Extract metadata from backup
    if [ -f "${metadata_file}" ]; then
        local backup_version timestamp hostname webops_root backup_dir_path
        
        eval "$(grep -o '"[^"]*": "[^"]*"' "${metadata_file}" | sed 's/: /="/' | sed 's/$/"/')"
        
        echo "Backup Information:"
        echo "  Version: ${backup_version:-unknown}"
        echo "  Date: ${timestamp:-unknown}"
        echo "  Host: ${hostname:-unknown}"
        echo "  WebOps Root: ${webops_root:-unknown}"
        echo "  Backup Dir: ${backup_dir_path:-unknown}"
        
        # Check version compatibility
        if [ "${backup_version:-unknown}" != "${SCRIPT_VERSION}" ]; then
            log "WARN" "Backup version (${backup_version}) differs from restore script version (${SCRIPT_VERSION})"
        fi
    else
        log "WARN" "No metadata file found - backup may be from older version"
    fi
}

# Create rollback backup
create_rollback_backup() {
    log "INFO" "Creating rollback backup..."
    
    # Create rollback directory
    if ! mkdir -p "${ROLLBACK_DIR}"; then
        log "ERROR" "Failed to create rollback directory: ${ROLLBACK_DIR}"
        return 1
    fi
    
    # Create rollback manifest
    echo "# WebOps Rollback Backup Manifest" > "${ROLLBACK_DIR}/rollback_manifest.txt"
    echo "# Created: $(date)" >> "${ROLLBACK_DIR}/rollback_manifest.txt"
    echo "# Version: ${SCRIPT_VERSION}" >> "${ROLLBACK_DIR}/rollback_manifest.txt"
    echo "" >> "${ROLLBACK_DIR}/rollback_manifest.txt"
    
    # Backup current state for rollback capability
    local components="control_panel cli config database media logs"
    
    for component in ${components}; do
        local source_dir=""
        local component_name="${component}"
        
        case "${component}" in
            control_panel)
                source_dir="${WEBOPS_ROOT}/control-panel"
                component_name="control_panel"
                ;;
            cli)
                source_dir="${WEBOPS_ROOT}/cli"
                component_name="cli"
                ;;
            config)
                source_dir="${WEBOPS_ROOT}/control-panel/config"
                component_name="config"
                ;;
            database)
                source_dir="${WEBOPS_ROOT}/control-panel"
                component_name="database"
                ;;
            media)
                source_dir="${WEBOPS_ROOT}/control-panel/media"
                component_name="media"
                ;;
            logs)
                source_dir="${WEBOPS_ROOT}/control-panel/logs"
                component_name="logs"
                ;;
        esac
        
        if [ -d "${source_dir}" ]; then
            log "DEBUG" "Backing up current ${component} for rollback..."
            
            local backup_file="${ROLLBACK_DIR}/${component_name}_rollback.tar.gz"
            
            if tar czf "${backup_file}" -C "$(dirname "${source_dir}")" "$(basename "${source_dir}")" 2>/dev/null; then
                local checksum
                if checksum="$(md5sum "${backup_file}" 2>/dev/null | cut -d' ' -f1)"; then
                    echo "${component_name}: ${checksum}" >> "${ROLLBACK_DIR}/rollback_manifest.txt"
                    log "INFO" "Rollback backup created: ${component}"
                fi
            else
                log "WARN" "Failed to create rollback backup for: ${component}"
            fi
        fi
    done
    
    # Create rollback info file
    echo "WebOps Rollback Backup Created" > "${ROLLBACK_DIR}/rollback_info.txt"
    echo "Date: $(date)" >> "${ROLLBACK_DIR}/rollback_info.txt"
    echo "Version: ${SCRIPT_VERSION}" >> "${ROLLBACK_DIR}/rollback_info.txt"
    echo "Rollback Directory: ${ROLLBACK_DIR}" >> "${ROLLBACK_DIR}/rollback_info.txt"
    
    log "INFO" "Rollback backup created in: ${ROLLBACK_DIR}"
    return 0
}

###############################################################################
# Restore Component Functions
###############################################################################

# Restore control panel
restore_control_panel() {
    local backup_file="$1"
    local target_dir="${WEBOPS_ROOT}/control-panel"
    
    log "INFO" "Restoring control panel application..."
    
    if [ ! -d "${target_dir}" ]; then
        log "WARN" "Control panel directory not found: ${target_dir}"
        return 0
    fi
    
    # Remove old control panel directory and restore from backup
    if rm -rf "${target_dir}" && tar xzf "${backup_file}" -C "$(dirname "${target_dir}")" 2>/dev/null; then
        log "INFO" "Control panel restored successfully"
        return 0
    else
        log "ERROR" "Failed to restore control panel"
        return 1
    fi
}

# Restore CLI
restore_cli() {
    local backup_file="$1"
    local target_dir="${WEBOPS_ROOT}/cli"
    
    log "INFO" "Restoring CLI interface..."
    
    if [ ! -d "${target_dir}" ]; then
        log "WARN" "CLI directory not found: ${target_dir}"
        return 0
    fi
    
    # Remove old CLI directory and restore from backup
    if rm -rf "${target_dir}" && tar xzf "${backup_file}" -C "$(dirname "${target_dir}")" 2>/dev/null; then
        log "INFO" "CLI restored successfully"
        return 0
    else
        log "ERROR" "Failed to restore CLI"
        return 1
    fi
}

# Restore configuration
restore_configurations() {
    local backup_file="$1"
    
    log "INFO" "Restoring configuration files..."
    
    # Create temporary directory for config extraction
    local temp_config_dir="${TEMP_DIR}/config_restore"
    mkdir -p "${temp_config_dir}"
    
    # Extract config files
    if tar xzf "${backup_file}" -C "${temp_config_dir}" 2>/dev/null; then
        # Restore control-panel/config
        local control_panel_config="${temp_config_dir}/config"
        if [ -d "${control_panel_config}" ]; then
            if [ -d "${WEBOPS_ROOT}/control-panel/config" ]; then
                rm -rf "${WEBOPS_ROOT}/control-panel/config"
            fi
            cp -r "${control_panel_config}" "${WEBOPS_ROOT}/control-panel/config"
        fi
        
        # Restore .webops config
        local webops_config="${temp_config_dir}/.webops"
        if [ -d "${webops_config}" ]; then
            if [ -d "${WEBOPS_ROOT}/.webops" ]; then
                rm -rf "${WEBOPS_ROOT}/.webops"
            fi
            cp -r "${webops_config}" "${WEBOPS_ROOT}/.webops"
        fi
        
        # Cleanup
        rm -rf "${temp_config_dir}"
        
        log "INFO" "Configuration files restored successfully"
        return 0
    else
        log "ERROR" "Failed to restore configuration files"
        rm -rf "${temp_config_dir}"
        return 1
    fi
}

# Restore database
restore_database() {
    local backup_file="$1"
    local metadata_file="$2"
    
    log "INFO" "Restoring database..."
    
    # Extract database type from metadata
    local db_type
    db_type="$(grep -o '"database_type": "[^"]*"' "${metadata_file}" 2>/dev/null | cut -d'"' -f4)" || db_type="unknown"
    
    # Extract database backup to temporary location
    local temp_db_file="${TEMP_DIR}/database_temp.sql"
    if ! gunzip -c "${backup_file}" > "${temp_db_file}" 2>/dev/null; then
        log "ERROR" "Failed to extract database backup"
        return 1
    fi
    
    # Determine database restoration method
    case "${db_type}" in
        postgresql)
            log "INFO" "Restoring PostgreSQL database..."
            
            # For PostgreSQL, we need connection details from environment
            if [ -f "${WEBOPS_ROOT}/control-panel/.env" ]; then
                local db_url
                db_url="$(grep -E '^DATABASE_URL=' "${WEBOPS_ROOT}/control-panel/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"')" || db_url=""
                
                if [ -n "${db_url}" ] && echo "${db_url}" | grep -q 'postgresql'; then
                    # Extract connection parameters
                    local pg_host pg_port pg_user pg_password pg_db
                    eval "$(echo "${db_url}" | sed 's|postgresql://||' | sed 's|:|=|g' | sed 's|/.*||' | sed 's|@||')"
                    pg_db="$(echo "${db_url}" | sed 's|.*/||')"
                    
                    # Drop and recreate database
                    if PGPASSWORD="${pg_password}" dropdb -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" "${pg_db}" 2>/dev/null; then
                        if PGPASSWORD="${pg_password}" createdb -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" "${pg_db}" 2>/dev/null; then
                            if PGPASSWORD="${pg_password}" psql -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" -d "${pg_db}" < "${temp_db_file}" 2>/dev/null; then
                                log "INFO" "PostgreSQL database restored successfully"
                                rm -f "${temp_db_file}"
                                return 0
                            else
                                log "ERROR" "Failed to restore PostgreSQL database data"
                            fi
                        else
                            log "ERROR" "Failed to recreate PostgreSQL database"
                        fi
                    else
                        log "WARN" "Failed to drop existing PostgreSQL database - may need manual intervention"
                    fi
                else
                    log "WARN" "PostgreSQL connection details not found in environment"
                fi
            fi
            
            # Fallback: restore to SQLite location with PostgreSQL warning
            log "WARN" "Cannot restore PostgreSQL database - connection details missing or insufficient permissions"
            log "WARN" "Please restore PostgreSQL database manually using the backup file: ${TEMP_DIR}/database_temp.sql"
            ;;
            
        sqlite|"")
            log "INFO" "Restoring SQLite database..."
            
            local sqlite_db="${WEBOPS_ROOT}/control-panel/db.sqlite3"
            
            # Backup existing database if it exists
            if [ -f "${sqlite_db}" ]; then
                cp "${sqlite_db}" "${sqlite_db}.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
            fi
            
            # Restore SQLite database
            if mv "${temp_db_file}" "${sqlite_db}" 2>/dev/null; then
                chmod 644 "${sqlite_db}" 2>/dev/null || true
                log "INFO" "SQLite database restored successfully"
                return 0
            else
                log "ERROR" "Failed to restore SQLite database"
                return 1
            fi
            ;;
            
        *)
            log "ERROR" "Unknown database type: ${db_type}"
            return 1
            ;;
    esac
    
    rm -f "${temp_db_file}"
    return 1
}

# Restore media files
restore_media() {
    local backup_file="$1"
    local target_dir="${WEBOPS_ROOT}/control-panel/media"
    
    log "INFO" "Restoring media files..."
    
    if [ -f "${backup_file}" ]; then
        # Remove old media directory and restore from backup
        if [ -d "${target_dir}" ]; then
            rm -rf "${target_dir}"
        fi
        
        if tar xzf "${backup_file}" -C "$(dirname "${target_dir}")" 2>/dev/null; then
            log "INFO" "Media files restored successfully"
            return 0
        else
            log "ERROR" "Failed to restore media files"
            return 1
        fi
    else
        log "WARN" "No media backup found - skipping media restoration"
        return 0
    fi
}

# Restore log files
restore_logs() {
    local backup_file="$1"
    
    log "INFO" "Restoring log files..."
    
    if [ -f "${backup_file}" ]; then
        # Create temporary directory for log extraction
        local temp_log_dir="${TEMP_DIR}/logs_restore"
        mkdir -p "${temp_log_dir}"
        
        # Extract log files
        if tar xzf "${backup_file}" -C "${temp_log_dir}" 2>/dev/null; then
            # Restore control-panel/logs
            local control_panel_logs="${temp_log_dir}/logs"
            if [ -d "${control_panel_logs}" ]; then
                if [ -d "${WEBOPS_ROOT}/control-panel/logs" ]; then
                    rm -rf "${WEBOPS_ROOT}/control-panel/logs"
                fi
                cp -r "${control_panel_logs}" "${WEBOPS_ROOT}/control-panel/logs"
            fi
            
            # Cleanup
            rm -rf "${temp_log_dir}"
            
            log "INFO" "Log files restored successfully"
            return 0
        else
            log "ERROR" "Failed to restore log files"
            rm -rf "${temp_log_dir}"
            return 1
        fi
    else
        log "WARN" "No logs backup found - skipping logs restoration"
        return 0
    fi
}

###############################################################################
# Post-Restore Verification and Cleanup
###############################################################################

# Verify restore integrity
verify_restore() {
    log "INFO" "Verifying restore integrity..."
    
    local failed_verifications=0
    
    # Check if critical directories exist
    local critical_dirs="${WEBOPS_ROOT}/control-panel ${WEBOPS_ROOT}/cli"
    
    for dir in ${critical_dirs}; do
        if [ ! -d "${dir}" ]; then
            log "ERROR" "Critical directory missing after restore: ${dir}"
            failed_verifications=$((failed_verifications + 1))
        fi
    done
    
    # Check if database file exists
    local sqlite_db="${WEBOPS_ROOT}/control-panel/db.sqlite3"
    if [ -f "${sqlite_db}" ]; then
        if ! sqlite3 "${sqlite_db}" ".tables" >/dev/null 2>&1; then
            log "ERROR" "Database appears to be corrupted after restore"
            failed_verifications=$((failed_verifications + 1))
        fi
    fi
    
    if [ "${failed_verifications}" -gt 0 ]; then
        log "ERROR" "Restore verification failed: ${failed_verifications} issue(s)"
        return 1
    else
        log "INFO" "Restore verification completed successfully"
        return 0
    fi
}

# Cleanup temporary files
cleanup_temp_files() {
    log "INFO" "Cleaning up temporary files..."
    
    if [ -d "${TEMP_DIR}" ]; then
        rm -rf "${TEMP_DIR}" 2>/dev/null || log "WARN" "Failed to cleanup temporary directory"
    fi
    
    log "INFO" "Cleanup completed"
}

###############################################################################
# Rollback Functions
###############################################################################

# Perform rollback
perform_rollback() {
    log "WARN" "Starting rollback operation..."
    
    local rollback_dir="${ROLLBACK_DIR}"
    local rollback_manifest="${rollback_dir}/rollback_manifest.txt"
    
    if [ ! -d "${rollback_dir}" ] || [ ! -f "${rollback_manifest}" ]; then
        log "ERROR" "Rollback backup not found: ${rollback_dir}"
        exit "${EXIT_ROLLBACK_FAILED}"
    fi
    
    # Read rollback manifest and restore components
    while IFS=': ' read -r component checksum; do
        # Skip comments and empty lines
        case "${component}" in
            \#*|'') continue ;;
        esac
        
        local rollback_file="${rollback_dir}/${component}_rollback.tar.gz"
        
        if [ -f "${rollback_file}" ]; then
            log "INFO" "Rolling back: ${component}"
            
            case "${component}" in
                control_panel)
                    rm -rf "${WEBOPS_ROOT}/control-panel"
                    tar xzf "${rollback_file}" -C "$(dirname "${WEBOPS_ROOT}/control-panel")" 2>/dev/null || log "ERROR" "Failed to rollback: ${component}"
                    ;;
                cli)
                    rm -rf "${WEBOPS_ROOT}/cli"
                    tar xzf "${rollback_file}" -C "$(dirname "${WEBOPS_ROOT}/cli")" 2>/dev/null || log "ERROR" "Failed to rollback: ${component}"
                    ;;
                config)
                    if [ -d "${WEBOPS_ROOT}/control-panel/config" ]; then
                        rm -rf "${WEBOPS_ROOT}/control-panel/config"
                    fi
                    tar xzf "${rollback_file}" -C "${WEBOPS_ROOT}/control-panel" 2>/dev/null || log "ERROR" "Failed to rollback: ${component}"
                    ;;
                database)
                    local sqlite_db="${WEBOPS_ROOT}/control-panel/db.sqlite3"
                    if [ -f "${rollback_file}" ]; then
                        rm -f "${sqlite_db}"
                        tar xzf "${rollback_file}" -C "${TEMP_DIR}" 2>/dev/null
                        if [ -f "${TEMP_DIR}/database.sqlite" ]; then
                            mv "${TEMP_DIR}/database.sqlite" "${sqlite_db}"
                            rm -rf "${TEMP_DIR}/database.sqlite"
                        fi
                    fi
                    ;;
                media)
                    if [ -d "${WEBOPS_ROOT}/control-panel/media" ]; then
                        rm -rf "${WEBOPS_ROOT}/control-panel/media"
                    fi
                    tar xzf "${rollback_file}" -C "$(dirname "${WEBOPS_ROOT}/control-panel/media")" 2>/dev/null || log "ERROR" "Failed to rollback: ${component}"
                    ;;
                logs)
                    if [ -d "${WEBOPS_ROOT}/control-panel/logs" ]; then
                        rm -rf "${WEBOPS_ROOT}/control-panel/logs"
                    fi
                    tar xzf "${rollback_file}" -C "$(dirname "${WEBOPS_ROOT}/control-panel/logs")" 2>/dev/null || log "ERROR" "Failed to rollback: ${component}"
                    ;;
            esac
        fi
        
    done < "${rollback_manifest}"
    
    log "WARN" "Rollback completed. WebOps has been restored to pre-restore state."
    log "WARN" "Rollback backup location: ${rollback_dir}"
    
    exit "${EXIT_SUCCESS}"
}

###############################################################################
# Usage and Help Functions
###############################################################################

# Display usage information
usage() {
    cat << EOF
${SCRIPT_NAME} v${SCRIPT_VERSION} - WebOps Secure Restore Script

USAGE:
    ${SCRIPT_NAME} [OPTIONS] BACKUP_DIR

DESCRIPTION:
    Safely restores WebOps installation from backup with rollback capability.
    Supports checksum verification, secure temporary directories, and
    comprehensive error handling.

OPTIONS:
    -h, --help              Display this help message and exit
    -v, --version           Display version information and exit
    -d, --dry-run          Perform a dry run without making changes
    -f, --force            Skip confirmation prompts
    -r, --rollback         Force rollback (restore from pre-restore backup)
    -c, --components       Specify components to restore (comma-separated)
    -l, --list             List available backups
    --verbose              Enable verbose output
    --no-verify            Skip integrity verification
    --no-rollback          Skip creating rollback backup

BACKUP_DIR:
    Path to the backup directory created by backup.sh script.
    Can be absolute or relative path.

COMPONENTS:
    control-panel          Django control panel application
    cli                    Command-line interface
    config                 Configuration files
    database               Database (PostgreSQL/SQLite)
    media                  Static assets and user uploads
    logs                   Log files

EXAMPLES:
    # Restore from full backup
    ${SCRIPT_NAME} /path/to/backup/directory

    # Dry run of restore
    ${SCRIPT_NAME} --dry-run /path/to/backup/directory

    # Force restore without prompts
    ${SCRIPT_NAME} --force /path/to/backup/directory

    # Selective restore
    ${SCRIPT_NAME} -c database,config /path/to/backup/directory

    # List available backups
    ${SCRIPT_NAME} --list

    # Force rollback
    ${SCRIPT_NAME} --rollback

EXIT CODES:
    ${EXIT_SUCCESS}       Restore completed successfully
    ${EXIT_INVALID_ARGS}  Invalid command line arguments
    ${EXIT_PERMISSION_DENIED} Insufficient permissions
    ${EXIT_BACKUP_NOT_FOUND} Backup directory not found
    ${EXIT_VERIFICATION_FAILED} Integrity verification failed
    ${EXIT_RESTORE_FAILED} Restore operation failed
    ${EXIT_ROLLBACK_FAILED} Rollback operation failed

ENVIRONMENT VARIABLES:
    WEBOPS_ROOT           WebOps installation directory

NOTES:
    - Creates automatic rollback backup before restore
    - Requires write permissions to WebOps installation directory
    - Backup integrity is verified using MD5 checksums
    - PostgreSQL restoration requires proper environment configuration
    - All operations are logged to syslog and local files
    - Rollback backup is created in: \$WEBOPS_ROOT/backups/rollback_*

ROLLBACK:
    If restore fails, automatic rollback is performed to restore
    the system to its previous state. Rollback can also be forced
    using --rollback option.

AUTHOR:
    Douglas Mutethia, Eleso Solutions
    https://github.com/dagiim/webops

EOF
}

# Display version information
version() {
    echo "${SCRIPT_NAME} v${SCRIPT_VERSION}"
    echo "WebOps Secure Restore Script"
    echo "Author: Douglas Mutethia, Eleso Solutions"
    echo "License: MIT"
}

# List available backups
list_backups() {
    local backup_base_dir="${WEBOPS_ROOT}/backups"
    
    echo "Available WebOps Backups:"
    echo "========================"
    
    if [ ! -d "${backup_base_dir}" ]; then
        echo "No backup directory found: ${backup_base_dir}"
        return 0
    fi
    
    local backup_count=0
    
    for backup_dir in "${backup_base_dir}"/*/; do
        if [ -d "${backup_dir}" ]; then
            local backup_name
            backup_name="$(basename "${backup_dir}")"
            
            echo "Backup: ${backup_name}"
            
            # Check for metadata file
            local metadata_file="${backup_dir}/backup_metadata.json"
            if [ -f "${metadata_file}" ]; then
                local backup_version timestamp hostname
                eval "$(grep -o '"[^"]*": "[^"]*"' "${metadata_file}" | sed 's/: /="/' | sed 's/$/"/')"
                
                echo "  Version: ${backup_version:-unknown}"
                echo "  Date: ${timestamp:-unknown}"
                echo "  Host: ${hostname:-unknown}"
            else
                echo "  Metadata: Not available"
            fi
            
            # Check for manifest file
            local manifest_file="${backup_dir}/backup_manifest.txt"
            if [ -f "${manifest_file}" ]; then
                echo "  Components:"
                while IFS=': ' read -r component checksum; do
                    case "${component}" in
                        \#*|'') continue ;;
                    esac
                    echo "    - ${component}"
                done < "${manifest_file}"
            fi
            
            echo ""
            backup_count=$((backup_count + 1))
        fi
    done
    
    if [ "${backup_count}" -eq 0 ]; then
        echo "No backups found."
    else
        echo "Total backups: ${backup_count}"
    fi
    
    return 0
}

###############################################################################
# Main Script Logic
###############################################################################

# Initialize variables
DRY_RUN=false
FORCE_RESTORE=false
ROLLBACK_MODE=false
COMPONENTS=""
LIST_MODE=false
VERBOSE=false
VERIFY_INTEGRITY=true
CREATE_ROLLBACK=true
BACKUP_DIR=""

# Parse command line arguments
while [ $# -gt 0 ]; do
    case $1 in
        -h|--help)
            usage
            exit "${EXIT_SUCCESS}"
            ;;
        -v|--version)
            version
            exit "${EXIT_SUCCESS}"
            ;;
        -d|--dry-run)
            DRY_RUN=true
            ;;
        -f|--force)
            FORCE_RESTORE=true
            ;;
        -r|--rollback)
            ROLLBACK_MODE=true
            ;;
        -c|--components)
            if [ -n "${2:-}" ]; then
                COMPONENTS="$2"
                shift
            else
                echo "Error: --components requires an argument" >&2
                exit "${EXIT_INVALID_ARGS}"
            fi
            ;;
        -l|--list)
            LIST_MODE=true
            ;;
        --verbose)
            VERBOSE=true
            ;;
        --no-verify)
            VERIFY_INTEGRITY=false
            ;;
        --no-rollback)
            CREATE_ROLLBACK=false
            ;;
        -*)
            echo "Error: Unknown option: $1" >&2
            usage
            exit "${EXIT_INVALID_ARGS}"
            ;;
        *)
            if [ -z "${BACKUP_DIR}" ]; then
                BACKUP_DIR="$1"
            else
                echo "Error: Multiple backup directories specified" >&2
                usage
                exit "${EXIT_INVALID_ARGS}"
            fi
            ;;
    esac
    shift
done

# Handle list mode
if [ "${LIST_MODE}" = true ]; then
    list_backups
    exit "${EXIT_SUCCESS}"
fi

# Handle rollback mode
if [ "${ROLLBACK_MODE}" = true ]; then
    log "WARN" "Rollback mode requested"
    if ! confirm_action "Are you sure you want to perform a rollback?"; then
        log "INFO" "Rollback cancelled by user"
        exit "${EXIT_SUCCESS}"
    fi
    perform_rollback
fi

# Validate backup directory argument
if [ -z "${BACKUP_DIR}" ]; then
    echo "Error: Backup directory not specified" >&2
    echo ""
    usage
    exit "${EXIT_INVALID_ARGS}"
fi

# Convert relative path to absolute path
if [ ! -e "${BACKUP_DIR}" ]; then
    BACKUP_DIR="$(pwd)/${BACKUP_DIR}"
fi

# Create initial log entry
log "INFO" "Starting WebOps restore script v${SCRIPT_VERSION}"
log "INFO" "Backup directory: ${BACKUP_DIR}"
log "INFO" "WebOps root: ${WEBOPS_ROOT}"

# Check if this is a dry run
if [ "${DRY_RUN}" = true ]; then
    log "INFO" "DRY RUN MODE: This would perform the following operations:"
    echo "  - Verify backup integrity"
    echo "  - Create rollback backup: ${ROLLBACK_DIR}"
    echo "  - Restore components from: ${BACKUP_DIR}"
    
    if [ -n "${COMPONENTS}" ]; then
        echo "  - Selective restore: ${COMPONENTS}"
    else
        echo "  - Full restore"
    fi
    
    echo "  - Verify restore integrity"
    
    log "INFO" "Dry run completed"
    exit "${EXIT_SUCCESS}"
fi

# Confirm restore operation (unless force mode)
if [ "${FORCE_RESTORE}" != true ]; then
    echo ""
    echo "${YELLOW}========================================${NC}"
    echo "${YELLOW}   WebOps Restore Operation${NC}"
    echo "${YELLOW}========================================${NC}"
    echo ""
    echo "This will restore WebOps from backup: ${BACKUP_DIR}"
    echo "A rollback backup will be created in: ${ROLLBACK_DIR}"
    echo ""
    
    if ! confirm_action "Do you want to continue with the restore operation?"; then
        log "INFO" "Restore cancelled by user"
        exit "${EXIT_SUCCESS}"
    fi
fi

# Main restore execution
perform_restore() {
    log "INFO" "Starting restore operation..."
    
    # Check requirements
    check_requirements "${BACKUP_DIR}"
    
    # Verify backup integrity
    if [ "${VERIFY_INTEGRITY}" = true ]; then
        if ! verify_backup_integrity "${BACKUP_DIR}"; then
            log "ERROR" "Backup verification failed - aborting restore"
            exit "${EXIT_VERIFICATION_FAILED}"
        fi
        
        # Display backup metadata
        display_backup_metadata "${BACKUP_DIR}"
    fi
    
    # Create rollback backup
    if [ "${CREATE_ROLLBACK}" = true ]; then
        if ! create_rollback_backup; then
            log "WARN" "Failed to create rollback backup - continuing without rollback"
        fi
    fi
    
    # Perform component restoration
    local failed_restorations=0
    
    if [ -n "${COMPONENTS}" ]; then
        # Selective restore
        IFS=',' read -ra SELECTED_COMPONENTS << EOF
${COMPONENTS}
EOF
        
        for component in "${SELECTED_COMPONENTS[@]}"; do
            component="$(echo "${component}" | xargs)"  # Trim whitespace
            
            local backup_file="${BACKUP_DIR}/${component}.tar.gz"
            local metadata_file="${BACKUP_DIR}/backup_metadata.json"
            
            case "${component}" in
                control-panel|control_panel)
                    restore_control_panel "${backup_file}" || failed_restorations=$((failed_restorations + 1))
                    ;;
                cli)
                    restore_cli "${backup_file}" || failed_restorations=$((failed_restorations + 1))
                    ;;
                config|configuration)
                    restore_configurations "${backup_file}" || failed_restorations=$((failed_restorations + 1))
                    ;;
                database|db)
                    restore_database "${backup_file}" "${metadata_file}" || failed_restorations=$((failed_restorations + 1))
                    ;;
                media|static)
                    restore_media "${backup_file}" || failed_restorations=$((failed_restorations + 1))
                    ;;
                logs)
                    restore_logs "${backup_file}" || failed_restorations=$((failed_restorations + 1))
                    ;;
                *)
                    log "WARN" "Unknown component: ${component}"
                    ;;
            esac
        done
    else
        # Full restore
        restore_control_panel "${BACKUP_DIR}/control_panel.tar.gz" || failed_restorations=$((failed_restorations + 1))
        restore_cli "${BACKUP_DIR}/cli.tar.gz" || failed_restorations=$((failed_restorations + 1))
        restore_configurations "${BACKUP_DIR}/config.tar.gz" || failed_restorations=$((failed_restorations + 1))
        restore_database "${BACKUP_DIR}/database.sql.gz" "${BACKUP_DIR}/backup_metadata.json" || failed_restorations=$((failed_restorations + 1))
        restore_media "${BACKUP_DIR}/media.tar.gz" || failed_restorations=$((failed_restorations + 1))
        restore_logs "${BACKUP_DIR}/logs.tar.gz" || failed_restorations=$((failed_restorations + 1))
    fi
    
    # Verify restore
    if [ "${VERIFY_INTEGRITY}" = true ]; then
        if ! verify_restore; then
            log "ERROR" "Restore verification failed"
            
            # Automatic rollback on failed verification
            if [ "${CREATE_ROLLBACK}" = true ] && [ -d "${ROLLBACK_DIR}" ]; then
                log "WARN" "Automatic rollback will be performed"
                perform_rollback
            else
                log "ERROR" "Restore failed and rollback is not available"
                exit "${EXIT_RESTORE_FAILED}"
            fi
        fi
    fi
    
    # Cleanup
    cleanup_temp_files
    
    if [ "${failed_restorations}" -gt 0 ]; then
        log "WARN" "Restore completed with ${failed_restorations} component(s) failing"
        exit "${EXIT_RESTORE_FAILED}"
    else
        log "INFO" "Restore completed successfully"
        return 0
    fi
}

# Confirmation prompt function
confirm_action() {
    local message="$1"
    
    while true; do
        printf "%s (y/N): " "${message}"
        read -r response
        
        case "${response}" in
            [Yy]|[Yy][Ee][Ss])
                return 0
                ;;
            [Nn]|[Nn][Oo]|"")
                return 1
                ;;
            *)
                echo "Please answer 'y' or 'n'"
                ;;
        esac
    done
}

# Perform the restore
if perform_restore; then
    echo ""
    echo "${GREEN}================================${NC}"
    echo "${GREEN}WebOps Restore Completed Successfully${NC}"
    echo "${GREEN}================================${NC}"
    echo ""
    echo "Backup Location: ${BACKUP_DIR}"
    echo "Rollback Backup: ${ROLLBACK_DIR}"
    echo "Restore Date: $(date)"
    echo ""
    
    if [ -d "${ROLLBACK_DIR}" ]; then
        echo "To force rollback if needed:"
        echo "  ${SCRIPT_NAME} --rollback"
        echo ""
    fi
    
    exit "${EXIT_SUCCESS}"
else
    echo ""
    echo "${RED}================================${NC}"
    echo "${RED}WebOps Restore Failed${NC}"
    echo "${RED}================================${NC}"
    echo ""
    
    if [ -d "${ROLLBACK_DIR}" ]; then
        echo "Rollback backup available at:"
        echo "  ${ROLLBACK_DIR}"
        echo ""
        echo "To perform rollback:"
        echo "  ${SCRIPT_NAME} --rollback"
        echo ""
    fi
    
    echo "Check logs for details:"
    echo "  ${RESTORE_LOG}"
    echo ""
    
    exit "${EXIT_RESTORE_FAILED}"
fi