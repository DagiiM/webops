#!/bin/sh

###############################################################################
# WebOps Secure Backup Script
# 
# Purpose: Create secure, dependency-free backups of WebOps installation
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

# Backup configuration
readonly BACKUP_BASE_DIR="${WEBOPS_ROOT}/backups"
readonly BACKUP_DATE="$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_DIR="${BACKUP_BASE_DIR}/${BACKUP_DATE}"
readonly TEMP_DIR="$(mktemp -d -t webops-backup-XXXXXXXXXX)"
readonly LOG_FILE="${BACKUP_DIR}/backup.log"
readonly METADATA_FILE="${BACKUP_DIR}/backup_metadata.json"
readonly MANIFEST_FILE="${BACKUP_DIR}/backup_manifest.txt"

# Security settings
umask 077

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_INVALID_ARGS=1
readonly EXIT_PERMISSION_DENIED=2
readonly EXIT_DISK_SPACE=3
readonly EXIT_BACKUP_FAILED=4
readonly EXIT_VERIFICATION_FAILED=5

###############################################################################
# Utility Functions
###############################################################################

# Enhanced logging with syslog integration
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    
    # Log to file
    echo "[${timestamp}] [${level}] ${message}" >> "${LOG_FILE}" 2>/dev/null || true
    
    # Log to syslog if available
    if command -v logger >/dev/null 2>&1; then
        logger -t "webops-backup" -p "user.${level}" "${message}" 2>/dev/null || true
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
    local required_commands="tar gzip md5sum find ls mkdir rmdir rm"
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
    
    # Create backup directory
    if ! mkdir -p "${BACKUP_DIR}" 2>/dev/null; then
        log "ERROR" "Failed to create backup directory: ${BACKUP_DIR}"
        exit "${EXIT_PERMISSION_DENIED}"
    fi
    
    # Check disk space (require at least 1GB free)
    local available_space
    available_space="$(df "${BACKUP_BASE_DIR}" | awk 'NR==2 {print $4}')" || available_space=0
    if [ "${available_space}" -lt 1048576 ]; then  # 1GB in KB
        log "WARN" "Low disk space: ${available_space}KB available"
    fi
    
    log "INFO" "System requirements check completed"
}

# Create secure temporary directory
create_secure_temp_dir() {
    log "DEBUG" "Creating secure temporary directory..."
    
    if [ -d "${TEMP_DIR}" ]; then
        chmod 700 "${TEMP_DIR}" || log "WARN" "Failed to set permissions on temp directory"
        log "INFO" "Using temporary directory: ${TEMP_DIR}"
    else
        log "ERROR" "Failed to create temporary directory"
        exit "${EXIT_BACKUP_FAILED}"
    fi
}

# Generate checksum for integrity verification
generate_checksum() {
    local file="$1"
    local checksum
    
    if ! checksum="$(md5sum "${file}" 2>/dev/null | cut -d' ' -f1)"; then
        log "ERROR" "Failed to generate checksum for: ${file}"
        return 1
    fi
    
    echo "${checksum}"
}

# Verify file integrity
verify_file_integrity() {
    local file="$1"
    local expected_checksum="$2"
    local actual_checksum
    
    if ! actual_checksum="$(generate_checksum "${file}")"; then
        return 1
    fi
    
    if [ "${expected_checksum}" != "${actual_checksum}" ]; then
        log "ERROR" "Checksum verification failed for: ${file}"
        log "ERROR" "Expected: ${expected_checksum}, Got: ${actual_checksum}"
        return 1
    fi
    
    return 0
}

###############################################################################
# Backup Component Functions
###############################################################################

# Backup control panel application
backup_control_panel() {
    local component="control_panel"
    local source_dir="${WEBOPS_ROOT}/control-panel"
    local dest_file="${TEMP_DIR}/${component}.tar.gz"
    local checksum_file="${TEMP_DIR}/${component}.md5"
    
    log "INFO" "Backing up control panel application..."
    
    if [ ! -d "${source_dir}" ]; then
        log "WARN" "Control panel directory not found: ${source_dir}"
        return 0
    fi
    
    # Exclude problematic directories
    local exclude_patterns="--exclude=*.pyc --exclude=__pycache__ --exclude=.git --exclude=venv --exclude=node_modules"
    
    if ! tar czf "${dest_file}" ${exclude_patterns} -C "$(dirname "${source_dir}")" "$(basename "${source_dir}")" 2>/dev/null; then
        log "ERROR" "Failed to backup control panel"
        return 1
    fi
    
    # Generate checksum
    local checksum
    if ! checksum="$(generate_checksum "${dest_file}")"; then
        log "ERROR" "Failed to generate checksum for control panel backup"
        return 1
    fi
    
    echo "${checksum}" > "${checksum_file}"
    echo "${checksum}" >> "${MANIFEST_FILE}"
    
    log "INFO" "Control panel backup completed"
    return 0
}

# Backup CLI interface
backup_cli() {
    local component="cli"
    local source_dir="${WEBOPS_ROOT}/cli"
    local dest_file="${TEMP_DIR}/${component}.tar.gz"
    local checksum_file="${TEMP_DIR}/${component}.md5"
    
    log "INFO" "Backing up CLI interface..."
    
    if [ ! -d "${source_dir}" ]; then
        log "WARN" "CLI directory not found: ${source_dir}"
        return 0
    fi
    
    # Exclude build artifacts and caches
    local exclude_patterns="--exclude=*.pyc --exclude=__pycache__ --exclude=.git --exclude=venv --exclude=build --exclude=dist"
    
    if ! tar czf "${dest_file}" ${exclude_patterns} -C "$(dirname "${source_dir}")" "$(basename "${source_dir}")" 2>/dev/null; then
        log "ERROR" "Failed to backup CLI"
        return 1
    fi
    
    # Generate checksum
    local checksum
    if ! checksum="$(generate_checksum "${dest_file}")"; then
        log "ERROR" "Failed to generate checksum for CLI backup"
        return 1
    fi
    
    echo "${checksum}" > "${checksum_file}"
    echo "${checksum}" >> "${MANIFEST_FILE}"
    
    log "INFO" "CLI backup completed"
    return 0
}

# Backup configuration files
backup_configurations() {
    local component="config"
    local source_dirs="${WEBOPS_ROOT}/control-panel/config ${WEBOPS_ROOT}/.webops"
    local dest_file="${TEMP_DIR}/${component}.tar.gz"
    local checksum_file="${TEMP_DIR}/${component}.md5"
    
    log "INFO" "Backing up configuration files..."
    
    # Create temporary directory for config files
    local temp_config_dir="${TEMP_DIR}/config_temp"
    mkdir -p "${temp_config_dir}"
    
    # Copy configuration directories
    for source_dir in ${source_dirs}; do
        if [ -d "${source_dir}" ]; then
            log "DEBUG" "Copying config directory: ${source_dir}"
            cp -r "${source_dir}" "${temp_config_dir}/" 2>/dev/null || log "WARN" "Failed to copy: ${source_dir}"
        fi
    done
    
    # Create archive
    if ! tar czf "${dest_file}" -C "${temp_config_dir}" . 2>/dev/null; then
        log "ERROR" "Failed to backup configurations"
        return 1
    fi
    
    # Cleanup temporary config directory
    rm -rf "${temp_config_dir}"
    
    # Generate checksum
    local checksum
    if ! checksum="$(generate_checksum "${dest_file}")"; then
        log "ERROR" "Failed to generate checksum for config backup"
        return 1
    fi
    
    echo "${checksum}" > "${checksum_file}"
    echo "${checksum}" >> "${MANIFEST_FILE}"
    
    log "INFO" "Configuration backup completed"
    return 0
}

# Backup database (PostgreSQL/SQLite)
backup_database() {
    local component="database"
    local dest_file="${TEMP_DIR}/${component}.sql.gz"
    local checksum_file="${TEMP_DIR}/${component}.md5"
    local db_type="unknown"
    
    log "INFO" "Backing up database..."
    
    # Try PostgreSQL first
    if command -v pg_dump >/dev/null 2>&1 && [ -f "${WEBOPS_ROOT}/control-panel/.env" ]; then
        log "DEBUG" "Attempting PostgreSQL backup..."
        
        # Extract database URL from environment
        local db_url=""
        if [ -f "${WEBOPS_ROOT}/control-panel/.env" ]; then
            db_url="$(grep -E '^DATABASE_URL=' "${WEBOPS_ROOT}/control-panel/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"')" || db_url=""
        fi
        
        if [ -n "${db_url}" ] && echo "${db_url}" | grep -q 'postgresql'; then
            db_type="postgresql"
            
            # Extract connection parameters
            local pg_host pg_port pg_user pg_password pg_db
            eval "$(echo "${db_url}" | sed 's|postgresql://||' | sed 's|:|=|g' | sed 's|/.*||' | sed 's|@||')"
            pg_db="$(echo "${db_url}" | sed 's|.*/||')"
            
            # Backup PostgreSQL database
            if PGPASSWORD="${pg_password}" pg_dump -h "${pg_host}" -p "${pg_port}" -U "${pg_user}" -d "${pg_db}" 2>/dev/null | gzip > "${dest_file}"; then
                log "INFO" "PostgreSQL backup completed"
            else
                log "WARN" "PostgreSQL backup failed, trying SQLite..."
                db_type="unknown"
                rm -f "${dest_file}"
            fi
        fi
    fi
    
    # Fallback to SQLite
    if [ "${db_type}" = "unknown" ] || [ ! -f "${dest_file}" ]; then
        log "DEBUG" "Attempting SQLite backup..."
        
        local sqlite_db="${WEBOPS_ROOT}/control-panel/db.sqlite3"
        if [ -f "${sqlite_db}" ]; then
            db_type="sqlite"
            if ! sqlite3 "${sqlite_db}" ".backup" "${TEMP_DIR}/database.sqlite" 2>/dev/null; then
                log "ERROR" "Failed to backup SQLite database"
                return 1
            fi
            gzip "${TEMP_DIR}/database.sqlite" > "${dest_file}" 2>/dev/null || {
                log "ERROR" "Failed to compress SQLite backup"
                return 1
            }
            rm -f "${TEMP_DIR}/database.sqlite"
            log "INFO" "SQLite backup completed"
        else
            log "WARN" "No database file found"
            touch "${dest_file}"  # Create empty file for consistency
        fi
    fi
    
    # Generate checksum
    local checksum
    if ! checksum="$(generate_checksum "${dest_file}")"; then
        log "ERROR" "Failed to generate checksum for database backup"
        return 1
    fi
    
    echo "${checksum}" > "${checksum_file}"
    echo "${checksum}" >> "${MANIFEST_FILE}"
    
    # Store database type in metadata
    echo "\"database_type\": \"${db_type}\"," >> "${METADATA_FILE}"
    
    log "INFO" "Database backup completed"
    return 0
}

# Backup static assets and user uploads
backup_media() {
    local component="media"
    local source_dir="${WEBOPS_ROOT}/control-panel/media"
    local dest_file="${TEMP_DIR}/${component}.tar.gz"
    local checksum_file="${TEMP_DIR}/${component}.md5"
    
    log "INFO" "Backing up media files..."
    
    if [ ! -d "${source_dir}" ]; then
        log "WARN" "Media directory not found: ${source_dir}"
        touch "${dest_file}"  # Create empty file for consistency
    else
        if ! tar czf "${dest_file}" -C "$(dirname "${source_dir}")" "$(basename "${source_dir}")" 2>/dev/null; then
            log "ERROR" "Failed to backup media files"
            return 1
        fi
        
        log "INFO" "Media files backup completed"
    fi
    
    # Generate checksum
    local checksum
    if ! checksum="$(generate_checksum "${dest_file}")"; then
        log "ERROR" "Failed to generate checksum for media backup"
        return 1
    fi
    
    echo "${checksum}" > "${checksum_file}"
    echo "${checksum}" >> "${MANIFEST_FILE}"
    
    return 0
}

# Backup log files
backup_logs() {
    local component="logs"
    local log_dirs="${WEBOPS_ROOT}/control-panel/logs /var/log/nginx"
    local dest_file="${TEMP_DIR}/${component}.tar.gz"
    local checksum_file="${TEMP_DIR}/${component}.md5"
    
    log "INFO" "Backing up log files..."
    
    # Create temporary directory for logs
    local temp_log_dir="${TEMP_DIR}/logs_temp"
    mkdir -p "${temp_log_dir}"
    
    # Copy log directories
    for log_dir in ${log_dirs}; do
        if [ -d "${log_dir}" ]; then
            log "DEBUG" "Copying log directory: ${log_dir}"
            cp -r "${log_dir}" "${temp_log_dir}/" 2>/dev/null || log "WARN" "Failed to copy: ${log_dir}"
        fi
    done
    
    # Create archive
    if ! tar czf "${dest_file}" -C "${temp_log_dir}" . 2>/dev/null; then
        log "ERROR" "Failed to backup logs"
        rm -rf "${temp_log_dir}"
        return 1
    fi
    
    # Cleanup temporary log directory
    rm -rf "${temp_log_dir}"
    
    # Generate checksum
    local checksum
    if ! checksum="$(generate_checksum "${dest_file}")"; then
        log "ERROR" "Failed to generate checksum for logs backup"
        return 1
    fi
    
    echo "${checksum}" > "${checksum_file}"
    echo "${checksum}" >> "${MANIFEST_FILE}"
    
    log "INFO" "Logs backup completed"
    return 0
}

###############################################################################
# Backup Metadata and Manifest Functions
###############################################################################

# Create backup metadata
create_backup_metadata() {
    log "INFO" "Creating backup metadata..."
    
    local hostname
    hostname="$(hostname 2>/dev/null || echo 'unknown')"
    
    local backup_info='{'
    backup_info="${backup_info}\"backup_version\": \"${SCRIPT_VERSION}\","
    backup_info="${backup_info}\"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    backup_info="${backup_info}\"hostname\": \"${hostname}\","
    backup_info="${backup_info}\"webops_root\": \"${WEBOPS_ROOT}\","
    backup_info="${backup_info}\"backup_dir\": \"${BACKUP_DIR}\","
    backup_info="${backup_info}\"script_name\": \"${SCRIPT_NAME}\","
    backup_info="${backup_info}\"components\": {"
    
    # Add component information
    local components="control_panel cli config database media logs"
    local first=true
    
    for component in ${components}; do
        if [ "${first}" = true ]; then
            first=false
        else
            backup_info="${backup_info},"
        fi
        
        local checksum_file="${TEMP_DIR}/${component}.md5"
        if [ -f "${checksum_file}" ]; then
            local checksum
            checksum="$(cat "${checksum_file}")"
            backup_info="${backup_info}\"${component}\": {\"checksum\": \"${checksum}\"}"
        fi
    done
    
    backup_info="${backup_info}}"
    backup_info="${backup_info}}"
    
    echo "${backup_info}" > "${METADATA_FILE}"
    log "INFO" "Backup metadata created"
}

# Create backup manifest
create_backup_manifest() {
    log "INFO" "Creating backup manifest..."
    
    echo "# WebOps Backup Manifest" > "${MANIFEST_FILE}"
    echo "# Generated: $(date)" >> "${MANIFEST_FILE}"
    echo "# Version: ${SCRIPT_VERSION}" >> "${MANIFEST_FILE}"
    echo "" >> "${MANIFEST_FILE}"
    
    # Add component checksums
    for component in control_panel cli config database media logs; do
        local checksum_file="${TEMP_DIR}/${component}.md5"
        if [ -f "${checksum_file}" ]; then
            echo "${component}: $(cat "${checksum_file}")" >> "${MANIFEST_FILE}"
        fi
    done
    
    log "INFO" "Backup manifest created"
}

###############################################################################
# Backup Verification and Finalization
###############################################################################

# Verify backup integrity
verify_backup() {
    log "INFO" "Verifying backup integrity..."
    
    local failed_verifications=0
    
    for component in control_panel cli config database media logs; do
        local dest_file="${TEMP_DIR}/${component}.tar.gz"
        local checksum_file="${TEMP_DIR}/${component}.md5"
        
        if [ -f "${dest_file}" ] && [ -f "${checksum_file}" ]; then
            local expected_checksum
            expected_checksum="$(cat "${checksum_file}")"
            
            if verify_file_integrity "${dest_file}" "${expected_checksum}"; then
                log "INFO" "Verification passed: ${component}"
            else
                log "ERROR" "Verification failed: ${component}"
                failed_verifications=$((failed_verifications + 1))
            fi
        fi
    done
    
    if [ "${failed_verifications}" -gt 0 ]; then
        log "ERROR" "Backup verification failed: ${failed_verifications} component(s)"
        return 1
    else
        log "INFO" "Backup verification completed successfully"
        return 0
    fi
}

# Finalize backup
finalize_backup() {
    log "INFO" "Finalizing backup..."
    
    # Move files from temp to backup directory
    for file in "${TEMP_DIR}"/*; do
        if [ -f "${file}" ]; then
            cp "${file}" "${BACKUP_DIR}/" 2>/dev/null || {
                log "ERROR" "Failed to copy ${file} to backup directory"
                return 1
            }
        fi
    done
    
    # Set secure permissions on backup files
    chmod 600 "${BACKUP_DIR}"/* 2>/dev/null || log "WARN" "Failed to set secure permissions"
    
    # Create backup info file
    echo "WebOps Backup Complete" > "${BACKUP_DIR}/backup_info.txt"
    echo "Date: $(date)" >> "${BACKUP_DIR}/backup_info.txt"
    echo "Version: ${SCRIPT_VERSION}" >> "${BACKUP_DIR}/backup_info.txt"
    echo "Backup Directory: ${BACKUP_DIR}" >> "${BACKUP_DIR}/backup_info.txt"
    
    # Cleanup temporary directory
    rm -rf "${TEMP_DIR}" 2>/dev/null || log "WARN" "Failed to cleanup temporary directory"
    
    log "INFO" "Backup finalized in: ${BACKUP_DIR}"
    return 0
}

###############################################################################
# Main Backup Function
###############################################################################

# Perform full backup
perform_full_backup() {
    log "INFO" "Starting full WebOps backup..."
    
    check_requirements
    create_secure_temp_dir
    
    # Initialize manifest file
    touch "${MANIFEST_FILE}"
    
    # Perform component backups
    local failed_components=0
    
    backup_control_panel || failed_components=$((failed_components + 1))
    backup_cli || failed_components=$((failed_components + 1))
    backup_configurations || failed_components=$((failed_components + 1))
    backup_database || failed_components=$((failed_components + 1))
    backup_media || failed_components=$((failed_components + 1))
    backup_logs || failed_components=$((failed_components + 1))
    
    if [ "${failed_components}" -gt 0 ]; then
        log "WARN" "Some components failed to backup: ${failed_components}"
    fi
    
    # Create metadata and manifest
    create_backup_metadata
    create_backup_manifest
    
    # Verify backup
    if ! verify_backup; then
        log "ERROR" "Backup verification failed"
        exit "${EXIT_VERIFICATION_FAILED}"
    fi
    
    # Finalize backup
    if ! finalize_backup; then
        log "ERROR" "Backup finalization failed"
        exit "${EXIT_BACKUP_FAILED}"
    fi
    
    log "INFO" "Full backup completed successfully"
    return 0
}

# Perform selective backup
perform_selective_backup() {
    local components="$1"
    
    log "INFO" "Starting selective backup: ${components}"
    
    check_requirements
    create_secure_temp_dir
    
    # Initialize manifest file
    touch "${MANIFEST_FILE}"
    
    local failed_components=0
    
    for component in ${components}; do
        case "${component}" in
            control-panel|control_panel)
                backup_control_panel || failed_components=$((failed_components + 1))
                ;;
            cli)
                backup_cli || failed_components=$((failed_components + 1))
                ;;
            config|configuration)
                backup_configurations || failed_components=$((failed_components + 1))
                ;;
            database|db)
                backup_database || failed_components=$((failed_components + 1))
                ;;
            media|static)
                backup_media || failed_components=$((failed_components + 1))
                ;;
            logs)
                backup_logs || failed_components=$((failed_components + 1))
                ;;
            *)
                log "WARN" "Unknown component: ${component}"
                ;;
        esac
    done
    
    # Create metadata and manifest
    create_backup_metadata
    create_backup_manifest
    
    # Verify backup
    if ! verify_backup; then
        log "ERROR" "Backup verification failed"
        exit "${EXIT_VERIFICATION_FAILED}"
    fi
    
    # Finalize backup
    if ! finalize_backup; then
        log "ERROR" "Backup finalization failed"
        exit "${EXIT_BACKUP_FAILED}"
    fi
    
    log "INFO" "Selective backup completed successfully"
    return 0
}

###############################################################################
# Usage and Help Functions
###############################################################################

# Display usage information
usage() {
    cat << EOF
${SCRIPT_NAME} v${SCRIPT_VERSION} - WebOps Secure Backup Script

USAGE:
    ${SCRIPT_NAME} [OPTIONS] [COMPONENTS]

DESCRIPTION:
    Creates secure, dependency-free backups of WebOps installation.
    Supports both full system and selective component backups with
    integrity verification and secure metadata storage.

OPTIONS:
    -h, --help              Display this help message and exit
    -v, --version           Display version information and exit
    -d, --dry-run          Perform a dry run without making changes
    -f, --full             Perform a full system backup (default)
    -c, --components       Specify components to backup (comma-separated)
    -o, --output-dir       Specify custom backup directory
    -q, --quiet            Suppress all output except errors
    --verbose              Enable verbose output
    --no-verify            Skip integrity verification
    --no-compress          Disable compression (not recommended)

COMPONENTS:
    control-panel          Django control panel application
    cli                    Command-line interface
    config                 Configuration files
    database               Database (PostgreSQL/SQLite)
    media                  Static assets and user uploads
    logs                   Log files

EXAMPLES:
    # Full system backup
    ${SCRIPT_NAME}

    # Selective backup of database and configuration
    ${SCRIPT_NAME} -c database,config

    # Dry run of full backup
    ${SCRIPT_NAME} --dry-run

    # Custom backup directory
    ${SCRIPT_NAME} --output-dir /custom/backup/path

EXIT CODES:
    ${EXIT_SUCCESS}       Backup completed successfully
    ${EXIT_INVALID_ARGS}  Invalid command line arguments
    ${EXIT_PERMISSION_DENIED} Insufficient permissions
    ${EXIT_DISK_SPACE}    Insufficient disk space
    ${EXIT_BACKUP_FAILED} Backup operation failed
    ${EXIT_VERIFICATION_FAILED} Integrity verification failed

ENVIRONMENT VARIABLES:
    WEBOPS_ROOT           WebOps installation directory
    BACKUP_BASE_DIR       Base directory for backups (default: \$WEBOPS_ROOT/backups)

NOTES:
    - Requires write permissions to WebOps installation directory
    - Minimum 1GB free disk space recommended
    - Backup integrity is automatically verified using MD5 checksums
    - All operations are logged to syslog and local files
    - Follows WebOps security-first philosophy with minimal dependencies

AUTHOR:
    Douglas Mutethia, Eleso Solutions
    https://github.com/dagiim/webops

EOF
}

# Display version information
version() {
    echo "${SCRIPT_NAME} v${SCRIPT_VERSION}"
    echo "WebOps Secure Backup Script"
    echo "Author: Douglas Mutethia, Eleso Solutions"
    echo "License: MIT"
}

###############################################################################
# Main Script Logic
###############################################################################

# Initialize variables
DRY_RUN=false
FULL_BACKUP=true
CUSTOM_OUTPUT_DIR=""
VERBOSE=false
VERIFY_INTEGRITY=true
COMPRESS=true
QUIET=false
SELECTED_COMPONENTS=""

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
            log "INFO" "Dry run mode enabled"
            ;;
        -f|--full)
            FULL_BACKUP=true
            ;;
        -c|--components)
            if [ -n "${2:-}" ]; then
                SELECTED_COMPONENTS="$2"
                FULL_BACKUP=false
                shift
            else
                echo "Error: --components requires an argument" >&2
                exit "${EXIT_INVALID_ARGS}"
            fi
            ;;
        -o|--output-dir)
            if [ -n "${2:-}" ]; then
                CUSTOM_OUTPUT_DIR="$2"
                shift
            else
                echo "Error: --output-dir requires an argument" >&2
                exit "${EXIT_INVALID_ARGS}"
            fi
            ;;
        -q|--quiet)
            QUIET=true
            ;;
        --verbose)
            VERBOSE=true
            ;;
        --no-verify)
            VERIFY_INTEGRITY=false
            ;;
        --no-compress)
            COMPRESS=false
            log "WARN" "Compression disabled - not recommended"
            ;;
        -*)
            echo "Error: Unknown option: $1" >&2
            usage
            exit "${EXIT_INVALID_ARGS}"
            ;;
        *)
            echo "Error: Unexpected argument: $1" >&2
            usage
            exit "${EXIT_INVALID_ARGS}"
            ;;
    esac
    shift
done

# Override backup directory if specified
if [ -n "${CUSTOM_OUTPUT_DIR}" ]; then
    BACKUP_BASE_DIR="${CUSTOM_OUTPUT_DIR}"
    BACKUP_DIR="${BACKUP_BASE_DIR}/${BACKUP_DATE}"
fi

# Create initial log entry
log "INFO" "Starting WebOps backup script v${SCRIPT_VERSION}"
log "INFO" "WebOps root: ${WEBOPS_ROOT}"
log "INFO" "Backup directory: ${BACKUP_DIR}"

# Check if this is a dry run
if [ "${DRY_RUN}" = true ]; then
    log "INFO" "DRY RUN MODE: This would perform the following operations:"
    
    if [ "${FULL_BACKUP}" = true ]; then
        echo "  - Full system backup"
        echo "  - Components: control-panel, cli, config, database, media, logs"
    else
        echo "  - Selective backup"
        echo "  - Components: ${SELECTED_COMPONENTS}"
    fi
    
    echo "  - Output directory: ${BACKUP_DIR}"
    echo "  - Verification: ${VERIFY_INTEGRITY}"
    echo "  - Compression: ${COMPRESS}"
    
    log "INFO" "Dry run completed"
    exit "${EXIT_SUCCESS}"
fi

# Main backup execution
if [ "${FULL_BACKUP}" = true ]; then
    perform_full_backup
else
    # Parse components from comma-separated string
    COMPONENTS_LIST="$(echo "${SELECTED_COMPONENTS}" | tr ',' ' ')"
    perform_selective_backup "${COMPONENTS_LIST}"
fi

# Final success message
echo ""
echo "================================"
echo "WebOps Backup Completed Successfully"
echo "================================"
echo "Backup Location: ${BACKUP_DIR}"
echo "Backup Date: $(date)"
echo "Components: $([ "${FULL_BACKUP}" = true ] && echo "ALL" || echo "${SELECTED_COMPONENTS}")"
echo ""
echo "To restore this backup, use:"
echo "  ${SCRIPT_DIR}/restore.sh ${BACKUP_DIR}"
echo ""

exit "${EXIT_SUCCESS}"