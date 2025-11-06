#!/bin/bash
set -e

# WebOps CLI Docker Entrypoint Script
# Handles initialization and startup for the CLI container

echo "🚀 Starting WebOps CLI..."

# Function to test CLI functionality
test_cli() {
    echo "🔍 Testing CLI functionality..."
    if webops --help > /dev/null 2>&1; then
        echo "✅ CLI is working correctly"
    else
        echo "❌ CLI test failed"
        exit 1
    fi
}

# Function to check API connectivity (if API_URL is set)
check_api_connectivity() {
    if [ -n "${API_URL:-}" ]; then
        echo "🔗 Checking API connectivity to ${API_URL}..."
        if curl -f -s -m 10 "${API_URL}/api/health/" > /dev/null 2>&1; then
            echo "✅ API is reachable"
        else
            echo "⚠️ API is not reachable (this may be expected in some environments)"
        fi
    else
        echo "ℹ️ No API_URL set, skipping connectivity check"
    fi
}

# Function to validate configuration
validate_config() {
    echo "⚙️ Validating configuration..."
    
    # Check if WEBOPS_API_TOKEN is set
    if [ -n "${WEBOPS_API_TOKEN:-}" ]; then
        echo "✅ API token is configured"
    else
        echo "ℹ️ No API token configured (CLI will work in local mode)"
    fi
    
    # Check if WEBOPS_CONFIG_PATH exists
    if [ -n "${WEBOPS_CONFIG_PATH:-}" ] && [ -f "${WEBOPS_CONFIG_PATH}" ]; then
        echo "✅ Configuration file exists at ${WEBOPS_CONFIG_PATH}"
    else
        echo "ℹ️ No configuration file found (using defaults)"
    fi
}

# Function to initialize CLI environment
init_cli() {
    echo "🛠️ Initializing CLI environment..."
    
    # Create config directory if it doesn't exist
    mkdir -p /app/config
    
    # Set proper permissions
    chown -R webops:webops /app/config
    
    echo "✅ CLI environment initialized"
}

# Main execution
main() {
    echo "🎯 WebOps CLI Container Starting..."
    
    # Initialize environment
    init_cli
    
    # Test CLI functionality
    test_cli
    
    # Check API connectivity
    check_api_connectivity
    
    # Validate configuration
    validate_config
    
    echo "🎉 WebOps CLI is ready!"
    
    # If no arguments provided, show help
    if [ $# -eq 0 ]; then
        echo ""
        echo "📖 WebOps CLI Commands:"
        echo "  webops list                    - List all deployments"
        echo "  webops deploy --name <name>    - Deploy a new application"
        echo "  webops status <name>           - Get deployment status"
        echo "  webops logs <name>             - View deployment logs"
        echo "  webops --help                  - Show all commands"
        echo ""
        echo "🔧 Environment Variables:"
        echo "  API_URL                        - Control panel API URL"
        echo "  WEBOPS_API_TOKEN               - API authentication token"
        echo "  WEBOPS_CONFIG_PATH             - Path to configuration file"
        echo ""
        exec webops --help
    fi
    
    # Execute the main command
    exec "$@"
}

# Run main function with all arguments
main "$@"