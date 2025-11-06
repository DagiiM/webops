#!/bin/bash
#
# WebOps State Management
# Tracks installed components and system state
#

# Source common library
if [[ -z "${SCRIPT_DIR:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
# If SCRIPT_DIR points to bin directory, adjust for lib directory
if [[ "${SCRIPT_DIR}" =~ /bin$ ]]; then
    source "${SCRIPT_DIR}/../lib/common.sh"
elif [[ "${SCRIPT_DIR}" =~ /lib$ ]]; then
    source "${SCRIPT_DIR}/common.sh"
else
    source "$(dirname "${SCRIPT_DIR}")/lib/common.sh"
fi

# State file location
# STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
# STATE_FILE="${STATE_DIR}/installed.state"

#=============================================================================
# State Initialization
#=============================================================================

init_state() {
    # Initialize state directory and file
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"
    
    ensure_directory "$STATE_DIR" "root:root" "755"

    if [[ ! -f "$STATE_FILE" ]]; then
        cat > "$STATE_FILE" <<EOF
# WebOps Installation State
# Format: component=status:version:timestamp
# Status: installed, failed, removed
EOF
        log_info "Initialized state file: $STATE_FILE"
    fi
}

#=============================================================================
# State Queries
#=============================================================================

is_component_installed() {
    # Check if component is installed
    local component="$1"
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"

    if [[ ! -f "$STATE_FILE" ]]; then
        return 1
    fi

    grep -q "^${component}=installed:" "$STATE_FILE"
}

get_component_version() {
    # Get installed version of component
    local component="$1"
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"

    if [[ ! -f "$STATE_FILE" ]]; then
        echo "unknown"
        return 1
    fi

    local line=$(grep "^${component}=installed:" "$STATE_FILE" | head -n1)
    if [[ -n "$line" ]]; then
        echo "$line" | cut -d: -f2
    else
        echo "unknown"
        return 1
    fi
}

get_component_timestamp() {
    # Get installation timestamp of component
    local component="$1"
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"

    if [[ ! -f "$STATE_FILE" ]]; then
        echo "unknown"
        return 1
    fi

    local line=$(grep "^${component}=installed:" "$STATE_FILE" | head -n1)
    if [[ -n "$line" ]]; then
        echo "$line" | cut -d: -f3
    else
        echo "unknown"
        return 1
    fi
}

list_installed_components() {
    # List all installed components
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"
    
    if [[ ! -f "$STATE_FILE" ]]; then
        return 0
    fi

    grep "^[^#].*=installed:" "$STATE_FILE" | cut -d= -f1 || true
}

#=============================================================================
# State Modifications
#=============================================================================

mark_component_installed() {
    # Mark component as installed
    local component="$1"
    local version="${2:-unknown}"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"

    init_state

    # Remove existing entry
    sed -i "/^${component}=/d" "$STATE_FILE"

    # Add new entry
    echo "${component}=installed:${version}:${timestamp}" >> "$STATE_FILE"

    log_success "Marked $component as installed (version: $version)"
}

mark_component_failed() {
    # Mark component installation as failed
    local component="$1"
    local version="${2:-unknown}"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"

    init_state

    # Remove existing entry
    sed -i "/^${component}=/d" "$STATE_FILE"

    # Add new entry
    echo "${component}=failed:${version}:${timestamp}" >> "$STATE_FILE"

    log_error "Marked $component as failed (version: $version)"
}

mark_component_removed() {
    # Mark component as removed
    local component="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"

    init_state

    if is_component_installed "$component"; then
        local version=$(get_component_version "$component")

        # Remove existing entry
        sed -i "/^${component}=/d" "$STATE_FILE"

        # Add new entry
        echo "${component}=removed:${version}:${timestamp}" >> "$STATE_FILE"

        log_success "Marked $component as removed"
    else
        log_warn "Component $component was not installed"
    fi
}

#=============================================================================
# Dependency Management
#=============================================================================

init_dependencies() {
    # Initialize dependencies map
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local COMPONENT_DEPENDENCIES_FILE="${STATE_DIR}/dependencies.map"
    
    ensure_directory "$STATE_DIR" "root:root" "755"

    if [[ ! -f "$COMPONENT_DEPENDENCIES_FILE" ]]; then
        cat > "$COMPONENT_DEPENDENCIES_FILE" <<EOF
# WebOps Component Dependencies
# Format: component=dependency1,dependency2,...
patroni=postgresql,etcd
kubernetes=etcd
EOF
        log_info "Initialized dependencies map"
    fi
}

get_component_dependencies() {
    # Get dependencies for a component
    local component="$1"
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local COMPONENT_DEPENDENCIES_FILE="${STATE_DIR}/dependencies.map"

    init_dependencies

    local line=$(grep "^${component}=" "$COMPONENT_DEPENDENCIES_FILE" | head -n1)
    if [[ -n "$line" ]]; then
        echo "$line" | cut -d= -f2 | tr ',' ' '
    fi
}

check_dependencies() {
    # Check if all dependencies are installed
    local component="$1"
    local deps=$(get_component_dependencies "$component")

    if [[ -z "$deps" ]]; then
        return 0
    fi

    local missing=""
    for dep in $deps; do
        if ! is_component_installed "$dep"; then
            missing="$missing $dep"
        fi
    done

    if [[ -n "$missing" ]]; then
        log_error "Missing dependencies for $component:$missing"
        return 1
    fi

    return 0
}

check_dependents() {
    # Check if any installed components depend on this one
    local component="$1"
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local COMPONENT_DEPENDENCIES_FILE="${STATE_DIR}/dependencies.map"

    init_dependencies

    local dependents=""
    while IFS= read -r line; do
        if echo "$line" | grep -q "=$component" || echo "$line" | grep -q ",$component"; then
            local dep_component=$(echo "$line" | cut -d= -f1)
            if is_component_installed "$dep_component"; then
                dependents="$dependents $dep_component"
            fi
        fi
    done < "$COMPONENT_DEPENDENCIES_FILE"

    if [[ -n "$dependents" ]]; then
        log_error "Cannot remove $component. The following components depend on it:$dependents"
        return 1
    fi

    return 0
}

#=============================================================================
# State Reporting
#=============================================================================

print_state() {
    # Print current installation state
    local STATE_DIR="${WEBOPS_ROOT:-/webops}/.webops/state"
    local STATE_FILE="${STATE_DIR}/installed.state"
    
    init_state

    echo "WebOps Installation State"
    echo "========================="
    echo ""

    if [[ ! -f "$STATE_FILE" ]]; then
        echo "No state file found"
        return
    fi

    echo "Installed Components:"
    echo "--------------------"
    while IFS= read -r line; do
        if [[ "$line" =~ ^([^#][^=]+)=installed:([^:]+):([^:]+)$ ]]; then
            local comp="${BASH_REMATCH[1]}"
            local ver="${BASH_REMATCH[2]}"
            local ts="${BASH_REMATCH[3]}"
            printf "  %-20s version: %-10s installed: %s\n" "$comp" "$ver" "$ts"
        fi
    done < "$STATE_FILE"
}
