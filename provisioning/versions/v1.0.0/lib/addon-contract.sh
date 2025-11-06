#!/bin/bash
#
# WebOps Addon Contract and SLA Management
# Defines the contract that all addons must adhere to
#
# This library provides:
# - Addon contract validation
# - SLA compliance checking
# - Performance monitoring
# - Quality assurance standards
#

set -euo pipefail

# Source common functions
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

#=============================================================================
# Addon Contract Definition
#=============================================================================

# Standard addon contract that all addons must implement
if [[ -z "${ADDON_CONTRACT_VERSION:-}" ]]; then
    readonly ADDON_CONTRACT_VERSION="1.0.0"
fi

# Contract sections that addons must implement
if [[ -z "${CONTRACT_SECTIONS:-}" ]]; then
    readonly CONTRACT_SECTIONS=(
        "metadata"
        "dependencies"
        "installation"
        "configuration"
        "health_checks"
        "monitoring"
        "security"
        "performance"
        "backup"
        "uninstallation"
        "support"
    )
fi

# SLA requirements
if [[ -z "${SLA_REQUIREMENTS:-}" ]]; then
    readonly SLA_REQUIREMENTS=(
        "availability"
        "performance"
        "recovery_time"
        "data_integrity"
        "security"
        "monitoring"
        "support_response"
    )
fi

#=============================================================================
# Contract Validation Functions
#=============================================================================

validate_addon_contract() {
    local addon_path="$1"
    local addon_name="$(basename "$addon_path" .sh)"
    
    log_info "Validating addon contract for: $addon_name"
    
    # Check if addon exists
    if [[ ! -f "$addon_path" ]]; then
        log_error "Addon file not found: $addon_path"
        return 1
    fi
    
    # Source addon to check for required functions
    source "$addon_path"
    
    # Validate metadata
    if ! validate_addon_metadata "$addon_name"; then
        log_error "Addon metadata validation failed for: $addon_name"
        return 1
    fi
    
    # Validate required functions
    if ! validate_required_functions "$addon_name"; then
        log_error "Required functions validation failed for: $addon_name"
        return 1
    fi
    
    # Validate SLA compliance
    if ! validate_sla_compliance "$addon_name"; then
        log_error "SLA compliance validation failed for: $addon_name"
        return 1
    fi
    
    # Validate security requirements
    if ! validate_security_requirements "$addon_name"; then
        log_error "Security requirements validation failed for: $addon_name"
        return 1
    fi
    
    log_info "Addon contract validation passed for: $addon_name"
    return 0
}

validate_addon_metadata() {
    local addon_name="$1"
    
    # Check if addon_metadata function exists
    if ! declare -f "addon_metadata" >/dev/null; then
        log_error "Missing required function: addon_metadata"
        return 1
    fi
    
    # Get metadata and validate required fields
    local metadata
    metadata=$(addon_metadata 2>/dev/null) || {
        log_error "Failed to get addon metadata"
        return 1
    }
    
    # Debug output
    log_info "Metadata output: $metadata"
    
    # Simple JSON validation - check if it starts and ends with braces
    if [[ ! "$metadata" =~ ^\{.*\}$ ]]; then
        log_error "Addon metadata is not valid JSON"
        log_error "Metadata was: $metadata"
        return 1
    fi
    
    # Check required fields using simple string matching
    local required_fields=("name" "version" "description" "depends" "provides")
    for field in "${required_fields[@]}"; do
        if ! echo "$metadata" | grep -q "\"$field\"" >/dev/null; then
            log_error "Missing required metadata field: $field"
            return 1
        fi
    done
    
    # Extract version using simple pattern matching
    local version
    version=$(echo "$metadata" | grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "Invalid version format: $version (expected x.y.z)"
        return 1
    fi
    
    return 0
}

validate_required_functions() {
    local addon_name="$1"
    
    # List of required functions based on contract (accept both with and without addon_ prefix)
    local required_functions=(
        "install:addon_install"
        "uninstall:addon_uninstall"
        "status:addon_status"
        "health_check:addon_health_check"
        "start:addon_start"
        "stop:addon_stop"
        "restart:addon_restart"
        "configure:addon_configure"
        "validate:addon_validate"
        "backup:addon_backup"
        "restore:addon_restore"
    )
    
    # Check each required function (accept either format)
    for func_pair in "${required_functions[@]}"; do
        IFS=':' read -r func_name addon_func_name <<< "$func_pair"
        
        if ! declare -f "$func_name" >/dev/null && ! declare -f "$addon_func_name" >/dev/null; then
            log_error "Missing required function: $func_name or $addon_func_name"
            return 1
        fi
    done
    
    return 0
}

validate_sla_compliance() {
    local addon_name="$1"
    
    # Check if addon provides SLA information
    if ! declare -f "addon_sla" >/dev/null; then
        log_warn "Addon does not provide SLA information: $addon_name"
        return 0  # Warning, not failure
    fi
    
    # Get SLA information
    local sla_info
    sla_info=$(addon_sla 2>/dev/null) || {
        log_error "Failed to get addon SLA information"
        return 1
    }
    
    # Simple JSON validation - check if it starts and ends with braces
    if [[ ! "$sla_info" =~ ^\{.*\}$ ]]; then
        log_error "Addon SLA information is not valid JSON"
        return 1
    fi
    
    # Check required SLA fields using simple string matching
    local required_sla_fields=(
        "availability_target"
        "performance_targets"
        "recovery_objectives"
        "monitoring_requirements"
    )
    
    for field in "${required_sla_fields[@]}"; do
        if ! echo "$sla_info" | grep -q "\"$field\"" >/dev/null; then
            log_error "Missing required SLA field: $field"
            return 1
        fi
    done
    
    # Validate SLA values
    validate_sla_values "$sla_info" || return 1
    
    return 0
}

validate_sla_values() {
    local sla_info="$1"
    
    # Validate availability target (should be >= 99.0%)
    local availability
    availability=$(echo "$sla_info" | grep -o '"availability_target"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$availability" ]]; then
        availability=$(echo "$sla_info" | grep -o '"availability"[[:space:]]*:[[:space:]]*{[^}]*"target"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f6)
    fi
    if [[ -z "$availability" ]]; then
        availability="99.0"  # Default if not found
    fi
    
    # Remove % sign if present
    availability=${availability%\%}
    
    if [[ ! "$availability" =~ ^[0-9]+\.[0-9]+$ ]] || (( $(echo "$availability < 99.0" | bc -l 2>/dev/null || echo "1") )); then
        log_error "Availability target must be >= 99.0%, got: $availability%"
        return 1
    fi
    
    # Validate recovery time objectives
    local rto
    rto=$(echo "$sla_info" | grep -o '"rto"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$rto" ]]; then
        rto="30"  # Default if not found
    fi
    
    # Convert time units to minutes
    local rto_minutes
    if [[ "$rto" =~ ^([0-9]+)s$ ]]; then
        rto_minutes=$((${BASH_REMATCH[1]} / 60))
    elif [[ "$rto" =~ ^([0-9]+)m$ ]]; then
        rto_minutes=${BASH_REMATCH[1]}
    elif [[ "$rto" =~ ^([0-9]+)h$ ]]; then
        rto_minutes=$((${BASH_REMATCH[1]} * 60))
    elif [[ "$rto" =~ ^[0-9]+$ ]]; then
        rto_minutes=$rto
    else
        log_error "Invalid RTO format: $rto (expected number with optional s/m/h suffix)"
        return 1
    fi
    
    if [[ $rto_minutes -gt 60 ]]; then
        log_error "RTO must be <= 60 minutes, got: $rto (${rto_minutes} minutes)"
        return 1
    fi
    
    local rpo
    rpo=$(echo "$sla_info" | grep -o '"rpo"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$rpo" ]]; then
        rpo="15"  # Default if not found
    fi
    
    # Convert time units to minutes
    local rpo_minutes
    if [[ "$rpo" =~ ^([0-9]+)s$ ]]; then
        rpo_minutes=$((${BASH_REMATCH[1]} / 60))
    elif [[ "$rpo" =~ ^([0-9]+)m$ ]]; then
        rpo_minutes=${BASH_REMATCH[1]}
    elif [[ "$rpo" =~ ^([0-9]+)h$ ]]; then
        rpo_minutes=$((${BASH_REMATCH[1]} * 60))
    elif [[ "$rpo" =~ ^[0-9]+$ ]]; then
        rpo_minutes=$rpo
    else
        log_error "Invalid RPO format: $rpo (expected number with optional s/m/h suffix)"
        return 1
    fi
    
    if [[ $rpo_minutes -gt 60 ]]; then
        log_error "RPO must be <= 60 minutes, got: $rpo (${rpo_minutes} minutes)"
        return 1
    fi
    
    return 0
}

validate_security_requirements() {
    local addon_name="$1"
    
    # Check if addon provides security information
    if ! declare -f "addon_security" >/dev/null; then
        log_warn "Addon does not provide security information: $addon_name"
        return 0  # Warning, not failure
    fi
    
    # Get security information
    local security_info
    security_info=$(addon_security 2>/dev/null) || {
        log_error "Failed to get addon security information"
        return 1
    }
    
    # Simple JSON validation - check if it starts and ends with braces
    if [[ ! "$security_info" =~ ^\{.*\}$ ]]; then
        log_error "Addon security information is not valid JSON"
        return 1
    fi
    
    # Check required security fields using simple string matching
    local required_security_fields=(
        "privilege_level"
        "data_access"
        "network_access"
        "authentication"
    )
    
    for field in "${required_security_fields[@]}"; do
        if ! echo "$security_info" | grep -q "\"$field\"" >/dev/null; then
            log_error "Missing required security field: $field"
            return 1
        fi
    done
    
    return 0
}

#=============================================================================
# SLA Monitoring Functions
#=============================================================================

check_sla_compliance() {
    local addon_name="$1"
    local addon_path=".webops/versions/v1.0.0/addons/${addon_name}.sh"
    
    log_info "Checking SLA compliance for: $addon_name"
    
    # Source addon
    source "$addon_path"
    
    # Get SLA information
    local sla_info
    sla_info=$(addon_sla 2>/dev/null) || {
        log_error "Failed to get SLA information for: $addon_name"
        return 1
    }
    
    # Check availability
    check_availability_sla "$addon_name" "$sla_info" || return 1
    
    # Check performance
    check_performance_sla "$addon_name" "$sla_info" || return 1
    
    # Check recovery objectives
    check_recovery_sla "$addon_name" "$sla_info" || return 1
    
    log_info "SLA compliance check passed for: $addon_name"
    return 0
}

check_availability_sla() {
    local addon_name="$1"
    local sla_info="$2"
    
    local target
    target=$(echo "$sla_info" | grep -o '"availability_target"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$target" ]]; then
        target="99.0"  # Default if not found
    fi
    
    # Get current availability from health checks
    local current_availability
    current_availability=$(calculate_availability "$addon_name") || {
        log_error "Failed to calculate availability for: $addon_name"
        return 1
    }
    
    # Compare with target
    if (( $(echo "$current_availability < $target" | bc -l) )); then
        log_error "Availability SLA breach for $addon_name: $current_availability% < $target%"
        return 1
    fi
    
    log_verbose "Availability SLA met: $current_availability% >= $target%"
    return 0
}

check_performance_sla() {
    local addon_name="$1"
    local sla_info="$2"
    
    # Extract performance targets using simple pattern matching
    local performance_targets_json
    performance_targets_json=$(echo "$sla_info" | grep -o '"performance_targets"[[:space:]]*:[[:space:]]*{[^}]*}' | sed 's/"performance_targets"[[:space:]]*:[[:space:]]*//')
    
    # Simple parsing of performance targets (limited implementation)
    echo "$performance_targets_json" | grep -o '"[^"]*"[[:space:]]*:[[:space:]]*"[^"]*"' | while IFS=: read -r metric target; do
        metric=$(echo "$metric" | tr -d '"' | tr -d ' ')
        target=$(echo "$target" | tr -d '"' | tr -d ' ')
        local current_value
        current_value=$(measure_performance_metric "$addon_name" "$metric") || {
            log_error "Failed to measure performance metric: $metric for $addon_name"
            return 1
        }
        
        # Compare with target (implementation depends on metric type)
        if ! compare_performance_metric "$metric" "$current_value" "$target"; then
            log_error "Performance SLA breach for $addon_name: $metric ($current_value) does not meet target ($target)"
            return 1
        fi
    done
    
    return 0
}

check_recovery_sla() {
    local addon_name="$1"
    local sla_info="$2"
    
    local rto_target
    rto_target=$(echo "$sla_info" | grep -o '"rto"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$rto_target" ]]; then
        rto_target="30"  # Default if not found
    fi
    
    local rpo_target
    rpo_target=$(echo "$sla_info" | grep -o '"rpo"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$rpo_target" ]]; then
        rpo_target="15"  # Default if not found
    fi
    
    # Check recent recovery times
    local last_recovery_time
    last_recovery_time=$(get_last_recovery_time "$addon_name") || {
        log_verbose "No recovery events found for: $addon_name"
        return 0
    }
    
    if [[ $last_recovery_time -gt $rto_target ]]; then
        log_error "RTO SLA breach for $addon_name: ${last_recovery_time}s > ${rto_target}s"
        return 1
    fi
    
    log_verbose "RTO SLA met: ${last_recovery_time}s <= ${rto_target}s"
    return 0
}

#=============================================================================
# Performance Measurement Functions
#=============================================================================

calculate_availability() {
    local addon_name="$1"
    local period="${2:-86400}"  # Default to 24 hours
    
    # Get health check results for the period
    local health_log="/opt/webops/autorecovery/logs/health_checks.log"
    
    if [[ ! -f "$health_log" ]]; then
        echo "100.0"  # Assume 100% if no data
        return 0
    fi
    
    local total_checks
    local successful_checks
    
    # Count checks in the period
    total_checks=$(find "$health_log" -mtime -1 -type f -exec grep -c "$addon_name" {} \; | awk '{sum += $1} END {print sum}')
    successful_checks=$(find "$health_log" -mtime -1 -type f -exec grep -c "✓.*$addon_name" {} \; | awk '{sum += $1} END {print sum}')
    
    if [[ $total_checks -eq 0 ]]; then
        echo "100.0"
        return 0
    fi
    
    local availability
    availability=$(echo "scale=2; $successful_checks * 100 / $total_checks" | bc)
    echo "$availability"
}

measure_performance_metric() {
    local addon_name="$1"
    local metric="$2"
    
    case "$metric" in
        "response_time")
            measure_response_time "$addon_name"
            ;;
        "cpu_usage")
            measure_cpu_usage "$addon_name"
            ;;
        "memory_usage")
            measure_memory_usage "$addon_name"
            ;;
        "disk_io")
            measure_disk_io "$addon_name"
            ;;
        "network_throughput")
            measure_network_throughput "$addon_name"
            ;;
        *)
            log_error "Unknown performance metric: $metric"
            return 1
            ;;
    esac
}

measure_response_time() {
    local addon_name="$1"
    
    # Measure response time of health check
    local start_time=$(date +%s%N)
    
    if health_check >/dev/null 2>&1; then
        local end_time=$(date +%s%N)
        local response_time=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
        echo "$response_time"
    else
        echo "9999"  # Return high value for failed checks
    fi
}

measure_cpu_usage() {
    local addon_name="$1"
    
    # Get CPU usage for addon processes
    local cpu_usage
    cpu_usage=$(ps aux | grep "[${addon_name:0:1}]${addon_name:1}" | awk '{sum += $3} END {print sum}')
    
    if [[ -z "$cpu_usage" ]]; then
        echo "0.0"
    else
        echo "$cpu_usage"
    fi
}

measure_memory_usage() {
    local addon_name="$1"
    
    # Get memory usage for addon processes
    local memory_usage
    memory_usage=$(ps aux | grep "[${addon_name:0:1}]${addon_name:1}" | awk '{sum += $4} END {print sum}')
    
    if [[ -z "$memory_usage" ]]; then
        echo "0.0"
    else
        echo "$memory_usage"
    fi
}

measure_disk_io() {
    local addon_name="$1"
    
    # Get disk I/O statistics (simplified)
    local disk_io
    disk_io=$(iostat -x 1 1 | grep -E "(Device|sd[a-z]|nvme[0-9]n[0-9])" | awk 'NR>1 {sum += $10 + $14} END {print sum}')
    
    if [[ -z "$disk_io" ]]; then
        echo "0.0"
    else
        echo "$disk_io"
    fi
}

measure_network_throughput() {
    local addon_name="$1"
    
    # Get network throughput (simplified)
    local network_throughput
    network_throughput=$(sar -n DEV 1 1 | grep -E "(eth0|ens|enp)" | awk 'NR>3 {sum += $5 + $6} END {print sum}')
    
    if [[ -z "$network_throughput" ]]; then
        echo "0.0"
    else
        echo "$network_throughput"
    fi
}

compare_performance_metric() {
    local metric="$1"
    local current_value="$2"
    local target_value="$3"
    
    case "$metric" in
        "response_time"|"cpu_usage"|"memory_usage"|"disk_io"|"network_throughput")
            # Lower is better
            if (( $(echo "$current_value <= $target_value" | bc -l) )); then
                return 0
            else
                return 1
            fi
            ;;
        *)
            log_error "Unknown metric type for comparison: $metric"
            return 1
            ;;
    esac
}

get_last_recovery_time() {
    local addon_name="$1"
    
    # Get last recovery time from logs
    local recovery_log="/opt/webops/autorecovery/logs/recovery.log"
    
    if [[ ! -f "$recovery_log" ]]; then
        echo "0"
        return 0
    fi
    
    local last_recovery
    last_recovery=$(grep "recovered.*$addon_name" "$recovery_log" | tail -1 | awk '{print $1, $2}')
    
    if [[ -z "$last_recovery" ]]; then
        echo "0"
        return 0
    fi
    
    # Convert to timestamp and calculate duration
    local recovery_timestamp
    recovery_timestamp=$(date -d "$last_recovery" +%s)
    local current_timestamp
    current_timestamp=$(date +%s)
    
    echo $((current_timestamp - recovery_timestamp))
}

#=============================================================================
# Contract Signing Functions
#=============================================================================

sign_addon_contract() {
    local addon_name="$1"
    local addon_path=".webops/versions/v1.0.0/addons/${addon_name}.sh"
    local contract_file=".webops/versions/v1.0.0/contracts/${addon_name}.contract"
    
    log_info "Signing addon contract for: $addon_name"
    
    # Validate addon first
    if ! validate_addon_contract "$addon_path"; then
        log_error "Cannot sign contract - addon validation failed"
        return 1
    fi
    
    # Create contract directory
    mkdir -p "$(dirname "$contract_file")"
    
    # Generate contract
    cat > "$contract_file" <<EOF
{
    "addon_name": "$addon_name",
    "contract_version": "$ADDON_CONTRACT_VERSION",
    "signed_at": "$(date -Iseconds)",
    "signed_by": "WebOps Platform v1.0.0",
    "metadata": $(addon_metadata),
    "sla": $(addon_sla 2>/dev/null || echo '{}'),
    "security": $(addon_security 2>/dev/null || echo '{}'),
    "validation_hash": "$(generate_contract_hash "$addon_path")"
}
EOF
    
    log_info "Addon contract signed: $contract_file"
    return 0
}

generate_contract_hash() {
    local addon_path="$1"
    
    # Generate hash of addon file
    sha256sum "$addon_path" | awk '{print $1}'
}

verify_contract_signature() {
    local addon_name="$1"
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local base_dir="$(dirname "$script_dir")"
    local contract_file="${base_dir}/contracts/${addon_name}-contract.json"
    
    if [[ ! -f "$contract_file" ]]; then
        log_error "Contract file not found: $contract_file"
        return 1
    fi
    
    # Get stored hash using simple pattern matching
    local stored_hash
    stored_hash=$(grep '"validation_hash"' "$contract_file" | cut -d'"' -f4)
    
    # Get current hash
    local current_hash
    current_hash=$(generate_contract_hash "${base_dir}/addons/${addon_name}.sh")
    
    if [[ "$stored_hash" != "$current_hash" ]]; then
        log_error "Contract signature verification failed - addon has been modified"
        return 1
    fi
    
    log_verbose "Contract signature verified for: $addon_name"
    return 0
}

#=============================================================================
# Contract Reporting Functions
#=============================================================================

generate_contract_report() {
    local output_file="${1:-/tmp/webops-contract-report.json}"
    
    log_info "Generating contract report: $output_file"
    
    local report='{"contracts": ['
    local first=true
    
    # Iterate through all addons
    for addon_file in .webops/versions/v1.0.0/addons/*.sh; do
        if [[ -f "$addon_file" ]]; then
            local addon_name
            addon_name=$(basename "$addon_file" .sh)
            local contract_file=".webops/versions/v1.0.0/contracts/${addon_name}.contract"
            
            if [[ -f "$contract_file" ]]; then
                if [[ "$first" == "true" ]]; then
                    first=false
                else
                    report+=','
                fi
                
                report+=$(cat "$contract_file")
            fi
        fi
    done
    
    report+='], "generated_at": "'$(date -Iseconds)'" }'
    
    echo "$report" > "$output_file"
    
    log_info "Contract report generated: $output_file"
}

check_all_contracts() {
    log_info "Checking all addon contracts"
    
    local failed_contracts=()
    
    for addon_file in .webops/versions/v1.0.0/addons/*.sh; do
        if [[ -f "$addon_file" ]]; then
            local addon_name
            addon_name=$(basename "$addon_file" .sh)
            
            if ! verify_contract_signature "$addon_name"; then
                failed_contracts+=("$addon_name")
            fi
        fi
    done
    
    if [[ ${#failed_contracts[@]} -gt 0 ]]; then
        log_error "Contract verification failed for: ${failed_contracts[*]}"
        return 1
    fi
    
    log_info "All addon contracts verified successfully"
    return 0
}

#=============================================================================
# Contract Enforcement Functions
#=============================================================================

enforce_contract_compliance() {
    local addon_name="$1"
    
    log_info "Enforcing contract compliance for: $addon_name"
    
    # Verify contract signature
    if ! verify_contract_signature "$addon_name"; then
        log_error "Contract signature verification failed - disabling addon"
        disable_addon "$addon_name"
        return 1
    fi
    
    # Check SLA compliance
    if ! check_sla_compliance "$addon_name"; then
        log_warn "SLA compliance check failed - attempting remediation"
        attempt_sla_remediation "$addon_name" || {
            log_error "SLA remediation failed - disabling addon"
            disable_addon "$addon_name"
            return 1
        }
    fi
    
    log_info "Contract compliance enforced for: $addon_name"
    return 0
}

disable_addon() {
    local addon_name="$1"
    
    log_warn "Disabling non-compliant addon: $addon_name"
    
    # Stop addon service
    if systemctl is-active --quiet "webops-${addon_name}"; then
        systemctl stop "webops-${addon_name}"
    fi
    
    # Disable addon service
    if systemctl is-enabled --quiet "webops-${addon_name}"; then
        systemctl disable "webops-${addon_name}"
    fi
    
    # Mark as disabled in state
    set_addon_state "$addon_name" "disabled" "Contract compliance breach"
}

attempt_sla_remediation() {
    local addon_name="$1"
    
    log_info "Attempting SLA remediation for: $addon_name"
    
    # Source addon
    source ".webops/versions/v1.0.0/addons/${addon_name}.sh"
    
    # Attempt restart
    if declare -f "restart" >/dev/null; then
        restart || {
            log_error "Addon restart failed during remediation"
            return 1
        }
    fi
    
    # Wait for recovery
    sleep 30
    
    # Check if remediation successful
    if check_sla_compliance "$addon_name"; then
        log_info "SLA remediation successful for: $addon_name"
        return 0
    else
        log_error "SLA remediation failed for: $addon_name"
        return 1
    fi
}

#=============================================================================
# Addon State Management Functions
#=============================================================================

set_addon_state() {
    local addon_name="$1"
    local state="$2"
    local reason="${3:-}"
    
    # Create state directory if it doesn't exist
    local state_dir="${WEBOPS_ROOT:-/webops}/state"
    mkdir -p "$state_dir"
    
    local state_file="$state_dir/${addon_name}.state"
    
    # Create state JSON
    local state_json
    state_json=$(cat <<EOF
{
    "addon_name": "$addon_name",
    "state": "$state",
    "reason": "$reason",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "updated_by": "WebOps Platform"
}
EOF
)
    
    # Write state to file
    echo "$state_json" > "$state_file"
    
    log_info "Addon state updated: $addon_name -> $state"
}

get_addon_state() {
    local addon_name="$1"
    local state_file="${WEBOPS_ROOT:-/webops}/state/${addon_name}.state"
    
    if [[ -f "$state_file" ]]; then
        cat "$state_file"
    else
        echo '{"state": "unknown", "reason": "No state file found"}'
    fi
}

# Export functions for use by other scripts
export -f validate_addon_contract
export -f check_sla_compliance
export -f sign_addon_contract
export -f verify_contract_signature
export -f generate_contract_report
export -f check_all_contracts
export -f enforce_contract_compliance
export -f set_addon_state
export -f get_addon_state