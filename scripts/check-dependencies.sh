#!/bin/bash
# Dependency Security Checker for WebOps
# Checks all requirements.txt files for known security vulnerabilities

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          WebOps Dependency Security Checker            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if safety is installed
if ! command -v safety &> /dev/null; then
    echo -e "${YELLOW}Safety is not installed. Installing...${NC}"
    pip install safety
    echo ""
fi

# Function to check a requirements file
check_requirements() {
    local file=$1
    local name=$2

    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}⚠  ${name}: File not found - ${file}${NC}"
        return 0
    fi

    echo -e "${BLUE}═══ ${name} ═══${NC}"
    echo "File: ${file}"
    echo ""

    # Run safety check
    if safety check -r "$file" --output=text; then
        echo -e "${GREEN}✓ No known vulnerabilities found${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ Vulnerabilities detected!${NC}"
        echo ""
        return 1
    fi
}

# Track overall status
FOUND_VULNERABILITIES=0

# Check control panel requirements
if ! check_requirements "control-panel/requirements.txt" "Control Panel Dependencies"; then
    FOUND_VULNERABILITIES=1
fi

# Check agent requirements
if ! check_requirements ".webops/agents/requirements.txt" "Agent System Dependencies"; then
    FOUND_VULNERABILITIES=1
fi

# Check CLI requirements
if ! check_requirements "cli/requirements.txt" "CLI Dependencies"; then
    FOUND_VULNERABILITIES=1
fi

# Check KVM addon requirements
if ! check_requirements "control-panel/addons/kvm/requirements.txt" "KVM Addon Dependencies"; then
    FOUND_VULNERABILITIES=1
fi

# Summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                         Summary                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ $FOUND_VULNERABILITIES -eq 0 ]; then
    echo -e "${GREEN}✓ All dependency files passed security scan${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run this check weekly or before deployments"
    echo "  2. Check for outdated packages: cd control-panel && pip list --outdated"
    echo "  3. Review DEPENDENCY_SECURITY.md for best practices"
    exit 0
else
    echo -e "${RED}✗ Security vulnerabilities found in one or more dependency files${NC}"
    echo ""
    echo "Action required:"
    echo "  1. Review the vulnerabilities listed above"
    echo "  2. Update affected packages to secure versions"
    echo "  3. Test thoroughly after updating"
    echo "  4. See DEPENDENCY_SECURITY.md for update procedures"
    exit 1
fi
