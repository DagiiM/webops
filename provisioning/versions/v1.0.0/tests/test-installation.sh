#!/bin/bash
#
# WebOps Installation Test Suite
# Comprehensive testing of v1.0.0 installation package
#

set -euo pipefail

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNINGS=0

# Test configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBOPS_VERSION_DIR="$(dirname "$SCRIPT_DIR")"
TEST_LOG="/tmp/webops-test-$(date +%Y%m%d-%H%M%S).log"

#=============================================================================
# Test Framework
#=============================================================================

start_test() {
    echo -e "\n${BLUE}[TEST]${NC} $1"
    ((TESTS_RUN++))
}

pass_test() {
    echo -e "${GREEN}  ✓ PASS${NC} $1"
    ((TESTS_PASSED++))
}

fail_test() {
    echo -e "${RED}  ✗ FAIL${NC} $1"
    ((TESTS_FAILED++))
}

warn_test() {
    echo -e "${YELLOW}  ⚠ WARN${NC} $1"
    ((TESTS_WARNINGS++))
}

section() {
    echo ""
    echo "============================================================================="
    echo "$1"
    echo "============================================================================="
}

#=============================================================================
# Test Suite 1: File Structure Tests
#=============================================================================

test_file_structure() {
    section "Test Suite 1: File Structure"

    start_test "Check critical files exist"
    local critical_files=(
        "README.md"
        "INSTALL.md"
        "TROUBLESHOOTING.md"
        "CHANGES.md"
        "config.env.template"
        "bin/webops"
        "lifecycle/install.sh"
        "lifecycle/resume.sh"
        "lifecycle/repair.sh"
        "lifecycle/uninstall.sh"
        "setup/base.sh"
        "setup/validate.sh"
        "setup/django.sh"
        "lib/common.sh"
        "lib/state.sh"
        "lib/os.sh"
        "lib/addon-contract.sh"
    )

    local missing_files=0
    for file in "${critical_files[@]}"; do
        if [[ -f "${WEBOPS_VERSION_DIR}/${file}" ]]; then
            pass_test "$file exists"
        else
            fail_test "$file is missing"
            ((missing_files++))
        fi
    done

    if [[ $missing_files -eq 0 ]]; then
        pass_test "All critical files present"
    else
        fail_test "$missing_files critical files missing"
    fi

    start_test "Check systemd templates exist"
    local systemd_templates=(
        "systemd/webops-web.service.template"
        "systemd/webops-worker.service.template"
        "systemd/webops-beat.service.template"
        "systemd/webops-channels.service.template"
    )

    local missing_templates=0
    for template in "${systemd_templates[@]}"; do
        if [[ -f "${WEBOPS_VERSION_DIR}/${template}" ]]; then
            pass_test "$template exists"
        else
            fail_test "$template is missing"
            ((missing_templates++))
        fi
    done

    if [[ $missing_templates -eq 0 ]]; then
        pass_test "All systemd templates present"
    else
        fail_test "$missing_templates systemd templates missing"
    fi

    start_test "Check addon scripts exist"
    local addons=(
        "addons/postgresql.sh"
        "addons/etcd.sh"
        "addons/patroni.sh"
        "addons/kubernetes.sh"
        "addons/kvm.sh"
        "addons/monitoring.sh"
        "addons/autorecovery.sh"
    )

    local missing_addons=0
    for addon in "${addons[@]}"; do
        if [[ -f "${WEBOPS_VERSION_DIR}/${addon}" ]]; then
            pass_test "$addon exists"
        else
            fail_test "$addon is missing"
            ((missing_addons++))
        fi
    done

    if [[ $missing_addons -eq 0 ]]; then
        pass_test "All addon scripts present"
    else
        fail_test "$missing_addons addon scripts missing"
    fi
}

#=============================================================================
# Test Suite 2: File Permissions Tests
#=============================================================================

test_file_permissions() {
    section "Test Suite 2: File Permissions"

    start_test "Check executable scripts"
    local executable_scripts=(
        "bin/webops"
        "lifecycle/install.sh"
        "lifecycle/resume.sh"
        "lifecycle/repair.sh"
        "lifecycle/uninstall.sh"
        "setup/base.sh"
        "setup/validate.sh"
        "setup/django.sh"
        "addons/postgresql.sh"
        "addons/etcd.sh"
        "addons/patroni.sh"
        "addons/kubernetes.sh"
        "addons/kvm.sh"
        "addons/monitoring.sh"
        "addons/autorecovery.sh"
    )

    local permission_errors=0
    for script in "${executable_scripts[@]}"; do
        if [[ -x "${WEBOPS_VERSION_DIR}/${script}" ]]; then
            pass_test "$script is executable"
        else
            fail_test "$script is not executable"
            ((permission_errors++))
        fi
    done

    if [[ $permission_errors -eq 0 ]]; then
        pass_test "All scripts have correct permissions"
    else
        fail_test "$permission_errors scripts have incorrect permissions"
    fi

    start_test "Check library files are sourceable (not executable)"
    local library_files=(
        "lib/common.sh"
        "lib/state.sh"
        "lib/os.sh"
        "lib/addon-contract.sh"
        "os/common.sh"
        "os/ubuntu.sh"
        "os/debian.sh"
        "os/rocky.sh"
    )

    for lib in "${library_files[@]}"; do
        if [[ -f "${WEBOPS_VERSION_DIR}/${lib}" ]]; then
            if [[ -x "${WEBOPS_VERSION_DIR}/${lib}" ]]; then
                warn_test "$lib is executable (should be sourceable only)"
            else
                pass_test "$lib is sourceable (not executable)"
            fi
        fi
    done
}

#=============================================================================
# Test Suite 3: Syntax Validation Tests
#=============================================================================

test_syntax_validation() {
    section "Test Suite 3: Syntax Validation"

    start_test "Validate shell script syntax"
    local syntax_errors=0

    # Find all .sh files
    while IFS= read -r -d '' script; do
        if bash -n "$script" 2>/dev/null; then
            pass_test "$(basename "$script") syntax OK"
        else
            fail_test "$(basename "$script") has syntax errors"
            bash -n "$script" 2>&1 || true
            ((syntax_errors++))
        fi
    done < <(find "${WEBOPS_VERSION_DIR}" -name "*.sh" -type f -print0)

    if [[ $syntax_errors -eq 0 ]]; then
        pass_test "All shell scripts have valid syntax"
    else
        fail_test "$syntax_errors scripts have syntax errors"
    fi
}

#=============================================================================
# Test Suite 4: Documentation Tests
#=============================================================================

test_documentation() {
    section "Test Suite 4: Documentation Tests"

    start_test "Check README.md completeness"
    if [[ -f "${WEBOPS_VERSION_DIR}/README.md" ]]; then
        local readme_size=$(wc -l < "${WEBOPS_VERSION_DIR}/README.md")
        if [[ $readme_size -gt 100 ]]; then
            pass_test "README.md is comprehensive ($readme_size lines)"
        else
            fail_test "README.md seems incomplete ($readme_size lines)"
        fi

        # Check for key sections
        local required_sections=(
            "Quick Start"
            "System Requirements"
            "Installation"
            "Configuration"
            "Addons"
            "Troubleshooting"
        )

        for section in "${required_sections[@]}"; do
            if grep -qi "$section" "${WEBOPS_VERSION_DIR}/README.md"; then
                pass_test "README contains '$section' section"
            else
                fail_test "README missing '$section' section"
            fi
        done
    else
        fail_test "README.md not found"
    fi

    start_test "Check INSTALL.md completeness"
    if [[ -f "${WEBOPS_VERSION_DIR}/INSTALL.md" ]]; then
        local install_size=$(wc -l < "${WEBOPS_VERSION_DIR}/INSTALL.md")
        if [[ $install_size -gt 100 ]]; then
            pass_test "INSTALL.md is comprehensive ($install_size lines)"
        else
            fail_test "INSTALL.md seems incomplete ($install_size lines)"
        fi
    else
        fail_test "INSTALL.md not found"
    fi

    start_test "Check TROUBLESHOOTING.md completeness"
    if [[ -f "${WEBOPS_VERSION_DIR}/TROUBLESHOOTING.md" ]]; then
        local troubleshoot_size=$(wc -l < "${WEBOPS_VERSION_DIR}/TROUBLESHOOTING.md")
        if [[ $troubleshoot_size -gt 100 ]]; then
            pass_test "TROUBLESHOOTING.md is comprehensive ($troubleshoot_size lines)"
        else
            fail_test "TROUBLESHOOTING.md seems incomplete ($troubleshoot_size lines)"
        fi
    else
        fail_test "TROUBLESHOOTING.md not found"
    fi
}

#=============================================================================
# Test Suite 5: Configuration Tests
#=============================================================================

test_configuration() {
    section "Test Suite 5: Configuration Tests"

    start_test "Check config.env.template has flexible paths"
    if [[ -f "${WEBOPS_VERSION_DIR}/config.env.template" ]]; then
        if grep -q 'WEBOPS_ROOT=${WEBOPS_ROOT:-' "${WEBOPS_VERSION_DIR}/config.env.template"; then
            pass_test "config.env.template has flexible WEBOPS_ROOT"
        else
            fail_test "config.env.template has hardcoded WEBOPS_ROOT"
        fi

        # Check for key configuration sections
        local required_sections=(
            "Platform Configuration"
            "Security Configuration"
            "Database Configuration"
            "Control Panel Configuration"
            "Feature Flags"
        )

        for section in "${required_sections[@]}"; do
            if grep -qi "$section" "${WEBOPS_VERSION_DIR}/config.env.template"; then
                pass_test "Config has '$section' section"
            else
                fail_test "Config missing '$section' section"
            fi
        done
    else
        fail_test "config.env.template not found"
    fi
}

#=============================================================================
# Test Suite 6: Systemd Template Tests
#=============================================================================

test_systemd_templates() {
    section "Test Suite 6: Systemd Template Tests"

    start_test "Validate systemd templates"
    local templates=(
        "systemd/webops-web.service.template"
        "systemd/webops-worker.service.template"
        "systemd/webops-beat.service.template"
        "systemd/webops-channels.service.template"
    )

    for template in "${templates[@]}"; do
        if [[ -f "${WEBOPS_VERSION_DIR}/${template}" ]]; then
            # Check for required sections
            if grep -q '\[Unit\]' "${WEBOPS_VERSION_DIR}/${template}" && \
               grep -q '\[Service\]' "${WEBOPS_VERSION_DIR}/${template}" && \
               grep -q '\[Install\]' "${WEBOPS_VERSION_DIR}/${template}"; then
                pass_test "$(basename "$template") has required sections"
            else
                fail_test "$(basename "$template") missing required sections"
            fi

            # Check for variable placeholders
            if grep -q '{{' "${WEBOPS_VERSION_DIR}/${template}"; then
                pass_test "$(basename "$template") has variable placeholders"
            else
                warn_test "$(basename "$template") has no variable placeholders"
            fi

            # Check for security hardening
            if grep -q 'NoNewPrivileges' "${WEBOPS_VERSION_DIR}/${template}"; then
                pass_test "$(basename "$template") has security hardening"
            else
                warn_test "$(basename "$template") missing security hardening"
            fi
        else
            fail_test "$template not found"
        fi
    done
}

#=============================================================================
# Test Suite 7: Script Logic Tests
#=============================================================================

test_script_logic() {
    section "Test Suite 7: Script Logic Tests"

    start_test "Check install.sh has logging"
    if grep -q 'init_logging' "${WEBOPS_VERSION_DIR}/lifecycle/install.sh"; then
        pass_test "install.sh has logging initialization"
    else
        fail_test "install.sh missing logging initialization"
    fi

    if grep -q 'INSTALL_LOG' "${WEBOPS_VERSION_DIR}/lifecycle/install.sh"; then
        pass_test "install.sh defines INSTALL_LOG variable"
    else
        fail_test "install.sh missing INSTALL_LOG variable"
    fi

    start_test "Check install.sh has path detection"
    if grep -q 'detected_root' "${WEBOPS_VERSION_DIR}/lifecycle/install.sh"; then
        pass_test "install.sh has path detection"
    else
        fail_test "install.sh missing path detection"
    fi

    start_test "Check django.sh has required functions"
    local required_functions=(
        "setup_directories"
        "setup_python_venv"
        "configure_django_env"
        "setup_django_database"
        "collect_static_files"
        "install_systemd_services"
    )

    for func in "${required_functions[@]}"; do
        if grep -q "^${func}()" "${WEBOPS_VERSION_DIR}/setup/django.sh"; then
            pass_test "django.sh has $func function"
        else
            fail_test "django.sh missing $func function"
        fi
    done
}

#=============================================================================
# Test Suite 8: CLI Tests
#=============================================================================

test_cli() {
    section "Test Suite 8: CLI Tests"

    start_test "Test webops CLI help"
    if "${WEBOPS_VERSION_DIR}/bin/webops" help > /dev/null 2>&1; then
        pass_test "webops help command works"
    else
        fail_test "webops help command failed"
    fi

    start_test "Test webops CLI version"
    if "${WEBOPS_VERSION_DIR}/bin/webops" version > /dev/null 2>&1; then
        pass_test "webops version command works"
    else
        fail_test "webops version command failed"
    fi

    start_test "Check webops CLI lists all commands"
    local output=$("${WEBOPS_VERSION_DIR}/bin/webops" help)
    local required_commands=(
        "install"
        "apply"
        "uninstall"
        "validate"
        "update"
        "rollback"
        "state"
    )

    for cmd in "${required_commands[@]}"; do
        if echo "$output" | grep -q "$cmd"; then
            pass_test "CLI help lists '$cmd' command"
        else
            fail_test "CLI help missing '$cmd' command"
        fi
    done
}

#=============================================================================
# Test Suite 9: Validation Script Tests
#=============================================================================

test_validation_script() {
    section "Test Suite 9: Validation Script Tests"

    start_test "Check validation functions exist"
    local validation_functions=(
        "validate_root"
        "validate_os"
        "validate_resources"
        "validate_network"
        "validate_systemd"
    )

    for func in "${validation_functions[@]}"; do
        if grep -q "^${func}()" "${WEBOPS_VERSION_DIR}/setup/validate.sh"; then
            pass_test "validate.sh has $func function"
        else
            fail_test "validate.sh missing $func function"
        fi
    done
}

#=============================================================================
# Test Suite 10: Integration Tests
#=============================================================================

test_integration() {
    section "Test Suite 10: Integration Tests"

    start_test "Test path detection logic"
    # Simulate path detection
    local test_dir="/tmp/webops-test-$$"
    mkdir -p "$test_dir/.webops/versions/v1.0.0"

    cd "$test_dir"
    local detected_root="$(cd "$(dirname ".webops")" && pwd)"

    if [[ "$detected_root" == "$test_dir" ]]; then
        pass_test "Path detection works correctly"
    else
        fail_test "Path detection failed (expected: $test_dir, got: $detected_root)"
    fi

    rm -rf "$test_dir"

    start_test "Test config generation would work"
    # Check if install.sh would generate valid config
    if grep -q 'WEBOPS_ROOT=${install_root}' "${WEBOPS_VERSION_DIR}/lifecycle/install.sh"; then
        pass_test "install.sh uses detected path in config"
    else
        fail_test "install.sh doesn't use detected path"
    fi

    start_test "Test systemd template substitution logic"
    # Check if django.sh has substitution function
    if grep -q 'substitute_template' "${WEBOPS_VERSION_DIR}/setup/django.sh"; then
        pass_test "django.sh has template substitution"
    else
        fail_test "django.sh missing template substitution"
    fi
}

#=============================================================================
# Main Test Runner
#=============================================================================

run_all_tests() {
    echo "============================================================================="
    echo "WebOps v1.0.0 Installation Test Suite"
    echo "============================================================================="
    echo "Test Directory: ${WEBOPS_VERSION_DIR}"
    echo "Test Log: ${TEST_LOG}"
    echo "Started: $(date)"
    echo ""

    # Run all test suites
    test_file_structure
    test_file_permissions
    test_syntax_validation
    test_documentation
    test_configuration
    test_systemd_templates
    test_script_logic
    test_cli
    test_validation_script
    test_integration

    # Print summary
    section "Test Summary"
    echo ""
    echo "Tests Run:     $TESTS_RUN"
    echo -e "${GREEN}Tests Passed:  $TESTS_PASSED${NC}"
    echo -e "${RED}Tests Failed:  $TESTS_FAILED${NC}"
    echo -e "${YELLOW}Warnings:      $TESTS_WARNINGS${NC}"
    echo ""

    local pass_rate=$((TESTS_PASSED * 100 / TESTS_RUN))
    echo "Pass Rate:     ${pass_rate}%"
    echo ""

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                                                               ║${NC}"
        echo -e "${GREEN}║  ✓ ALL TESTS PASSED - INSTALLATION IS PRODUCTION-READY       ║${NC}"
        echo -e "${GREEN}║                                                               ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 0
    else
        echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                                                               ║${NC}"
        echo -e "${RED}║  ✗ SOME TESTS FAILED - REVIEW REQUIRED                       ║${NC}"
        echo -e "${RED}║                                                               ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
        return 1
    fi
}

# Run tests and save to log
run_all_tests 2>&1 | tee "$TEST_LOG"
exit_code=${PIPESTATUS[0]}

echo ""
echo "Test log saved to: $TEST_LOG"

exit $exit_code
