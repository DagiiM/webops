#!/bin/bash
#
# WebOps Addon Contract Validation Test Script
# Tests all signed addon contracts for validity and SLA compliance
#

set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/addon-contract.sh"

# Test configuration
readonly TEST_RESULTS_FILE="${SCRIPT_DIR}/../contracts/test-results.log"
readonly CONTRACTS_DIR="${SCRIPT_DIR}/../contracts"

# Initialize test results
> "$TEST_RESULTS_FILE"
log_info "WebOps Addon Contract Validation Test" | tee -a "$TEST_RESULTS_FILE"
log_info "=====================================" | tee -a "$TEST_RESULTS_FILE"
log_info "Test started at: $(date -Iseconds)" | tee -a "$TEST_RESULTS_FILE"
echo | tee -a "$TEST_RESULTS_FILE"

# Test counters (using regular variables since we need them globally)
total_tests=0
passed_tests=0
failed_tests=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    ((total_tests++))
    
    log_info "Running test: $test_name" | tee -a "$TEST_RESULTS_FILE"
    
    if eval "$test_command" >> "$TEST_RESULTS_FILE" 2>&1; then
        log_success "✓ PASSED: $test_name" | tee -a "$TEST_RESULTS_FILE"
        ((passed_tests++))
        return 0
    else
        log_error "✗ FAILED: $test_name" | tee -a "$TEST_RESULTS_FILE"
        ((failed_tests++))
        return 1
    fi
}

# Test 1: Verify all contract files exist
test_contract_files_exist() {
    local missing_files=()
    
    for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
        local contract_file="${CONTRACTS_DIR}/${addon}-contract.json"
        local signature_file="${CONTRACTS_DIR}/signatures/${addon}.sig"
        
        if [[ ! -f "$contract_file" ]]; then
            missing_files+=("$contract_file")
        fi
        
        if [[ ! -f "$signature_file" ]]; then
            missing_files+=("$signature_file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        echo "Missing contract files:"
        printf '  %s\n' "${missing_files[@]}"
        return 1
    fi
    
    echo "All contract files exist"
    return 0
}

# Test 2: Verify contract signatures
test_contract_signatures() {
    local failed_signatures=()
    
    for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
        if ! verify_contract_signature "$addon"; then
            failed_signatures+=("$addon")
        fi
    done
    
    if [[ ${#failed_signatures[@]} -gt 0 ]]; then
        echo "Signature verification failed for:"
        printf '  %s\n' "${failed_signatures[@]}"
        return 1
    fi
    
    echo "All contract signatures verified"
    return 0
}

# Test 3: Validate addon contracts
test_addon_contracts() {
    local failed_contracts=()
    
    for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
        local addon_path="${SCRIPT_DIR}/../addons/${addon}.sh"
        if ! validate_addon_contract "$addon_path"; then
            failed_contracts+=("$addon")
        fi
    done
    
    if [[ ${#failed_contracts[@]} -gt 0 ]]; then
        echo "Contract validation failed for:"
        printf '  %s\n' "${failed_contracts[@]}"
        return 1
    fi
    
    echo "All addon contracts validated"
    return 0
}

# Test 4: Check SLA compliance
test_sla_compliance() {
    local failed_sla=()
    
    for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
        if ! check_sla_compliance "$addon"; then
            failed_sla+=("$addon")
        fi
    done
    
    if [[ ${#failed_sla[@]} -gt 0 ]]; then
        echo "SLA compliance check failed for:"
        printf '  %s\n' "${failed_sla[@]}"
        return 1
    fi
    
    echo "All SLA compliance checks passed"
    return 0
}

# Test 5: Verify contract metadata
test_contract_metadata() {
    local failed_metadata=()
    
    for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
        local contract_file="${CONTRACTS_DIR}/${addon}-contract.json"
        
        # Check if contract file is valid JSON
        if ! grep -q '"addon_name"' "$contract_file"; then
            failed_metadata+=("$addon: missing addon_name")
        fi
        
        if ! grep -q '"contract_version"' "$contract_file"; then
            failed_metadata+=("$addon: missing contract_version")
        fi
        
        if ! grep -q '"signed_at"' "$contract_file"; then
            failed_metadata+=("$addon: missing signed_at")
        fi
        
        if ! grep -q '"validation_hash"' "$contract_file"; then
            failed_metadata+=("$addon: missing validation_hash")
        fi
    done
    
    if [[ ${#failed_metadata[@]} -gt 0 ]]; then
        echo "Metadata validation failed:"
        printf '  %s\n' "${failed_metadata[@]}"
        return 1
    fi
    
    echo "All contract metadata validated"
    return 0
}

# Test 6: Check signature file integrity
test_signature_integrity() {
    local failed_signatures=()
    
    for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
        local signature_file="${CONTRACTS_DIR}/signatures/${addon}.sig"
        local file_size=$(stat -c%s "$signature_file" 2>/dev/null || echo "0")
        
        if [[ $file_size -ne 256 ]]; then
            failed_signatures+=("$addon: invalid signature size ($file_size bytes)")
        fi
    done
    
    if [[ ${#failed_signatures[@]} -gt 0 ]]; then
        echo "Signature integrity check failed:"
        printf '  %s\n' "${failed_signatures[@]}"
        return 1
    fi
    
    echo "All signature files have correct size (256 bytes)"
    return 0
}

# Run all tests
log_info "Starting addon contract validation tests..." | tee -a "$TEST_RESULTS_FILE"
echo | tee -a "$TEST_RESULTS_FILE"

run_test "Contract Files Existence" "test_contract_files_exist"
run_test "Contract Signatures" "test_contract_signatures"
run_test "Addon Contract Validation" "test_addon_contracts"
run_test "SLA Compliance" "test_sla_compliance"
run_test "Contract Metadata" "test_contract_metadata"
run_test "Signature Integrity" "test_signature_integrity"

# Generate summary
echo | tee -a "$TEST_RESULTS_FILE"
log_info "Test Summary:" | tee -a "$TEST_RESULTS_FILE"
log_info "============" | tee -a "$TEST_RESULTS_FILE"
log_info "Total Tests: $total_tests" | tee -a "$TEST_RESULTS_FILE"
log_success "Passed: $passed_tests" | tee -a "$TEST_RESULTS_FILE"
if [[ $failed_tests -gt 0 ]]; then
    log_error "Failed: $failed_tests" | tee -a "$TEST_RESULTS_FILE"
fi
echo | tee -a "$TEST_RESULTS_FILE"

# Calculate success rate
success_rate=$(echo "scale=2; $passed_tests * 100 / $total_tests" | bc)
log_info "Success Rate: ${success_rate}%" | tee -a "$TEST_RESULTS_FILE"

# Exit with appropriate code
if [[ $failed_tests -eq 0 ]]; then
    log_success "All tests passed successfully!" | tee -a "$TEST_RESULTS_FILE"
    exit 0
else
    log_error "Some tests failed. Check $TEST_RESULTS_FILE for details." | tee -a "$TEST_RESULTS_FILE"
    exit 1
fi