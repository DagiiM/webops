#!/bin/bash
# WebOps Quick Start Script for Development
# This script sets up the development environment

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Detect script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate from provisioning/versions/v1.0.0/dev to webops root
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
CONTROL_PANEL_DIR="${PROJECT_ROOT}/control-panel"
ENV_FILE="${PROJECT_ROOT}/.env"

# Total steps for progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}[${CURRENT_STEP}/${TOTAL_STEPS}] $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠  $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Cleanup function on failure
cleanup_on_failure() {
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}  Setup failed!${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "\n${YELLOW}To clean up and retry:${NC}"
    echo "  cd ${CONTROL_PANEL_DIR}"
    echo "  rm -rf venv"
    echo "  cd ${PROJECT_ROOT}"
    echo "  rm -f ${ENV_FILE}"
    echo "  rm -f control-panel/db.sqlite3"
    echo "  provisioning/versions/v1.0.0/dev/quickstart.sh"
    exit 1
}

trap cleanup_on_failure ERR

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  WebOps Development Quick Start${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\n${BLUE}Project root:${NC} ${PROJECT_ROOT}"
echo -e "${BLUE}Control panel:${NC} ${CONTROL_PANEL_DIR}"
echo -e "${BLUE}Dev scripts:${NC} ${SCRIPT_DIR}"

# Change to control panel directory
cd "$CONTROL_PANEL_DIR" || {
    echo -e "${RED}Failed to change to control panel directory: ${CONTROL_PANEL_DIR}${NC}"
    exit 1
}

# Step 1: Pre-flight checks
print_step "Running pre-flight checks..."

# Check Python version (require 3.11+)
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo -e "${BLUE}Python version:${NC} $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    print_error "Python 3.11+ required (found $PYTHON_VERSION)"
    echo ""
    echo "Please upgrade Python:"
    echo "  Ubuntu 22.04+: sudo apt-get install python3.11 python3.11-venv"
    echo "  Or use pyenv to install Python 3.11+"
    exit 1
fi

print_success "Python version compatible"

# Check for required commands
for cmd in python3 pip3 git; do
    if ! command -v $cmd &> /dev/null; then
        print_error "Required command not found: $cmd"
        exit 1
    fi
done

print_success "Required commands available"

# Check disk space (need ~1GB for venv + dependencies)
AVAILABLE_SPACE=$(df "$SCRIPT_DIR" | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_SPACE" -lt 1048576 ]; then
    print_warning "Low disk space (< 1GB available)"
fi

# Detect OS and check for system dependencies (only on Debian-based systems)
if command -v dpkg &> /dev/null; then
    echo -e "\n${BLUE}Checking system dependencies...${NC}"
    MISSING_PACKAGES=()

    # Check for critical packages
    for pkg in python3-dev build-essential libpq-dev; do
        if ! dpkg -l 2>/dev/null | grep -q "^ii  $pkg "; then
            MISSING_PACKAGES+=("$pkg")
        fi
    done

    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        print_warning "Missing recommended system packages:"
        for pkg in "${MISSING_PACKAGES[@]}"; do
            echo "  - $pkg"
        done
        echo ""
        echo "Install with: sudo apt-get install ${MISSING_PACKAGES[*]}"
        echo ""

        # Allow non-interactive mode via environment variable
        if [ "${WEBOPS_SKIP_DEPENDENCY_CHECK:-}" = "1" ]; then
            print_warning "Skipping dependency check (WEBOPS_SKIP_DEPENDENCY_CHECK=1)"
        else
            read -p "Continue anyway? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        print_success "System dependencies available"
    fi
fi

# Step 2: Create or verify virtual environment
print_step "Setting up virtual environment..."

# Check if virtual environment exists AND is valid (has activate script)
if [ ! -f "venv/bin/activate" ]; then
    if [ -d "venv" ]; then
        print_warning "Virtual environment directory exists but is corrupted, recreating..."
        rm -rf venv
    fi
    echo -e "${BLUE}Creating virtual environment (this may take a minute)...${NC}"
    python3 -m venv venv || {
        print_error "Failed to create virtual environment"
        echo ""
        echo "Please ensure python3-venv is installed:"
        echo "  Ubuntu/Debian: sudo apt-get install python3-venv"
        echo "  Rocky/Alma: sudo dnf install python3-virtualenv"
        exit 1
    }
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"

# Step 3: Install dependencies
print_step "Installing Python dependencies (this may take 2-3 minutes)..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt || {
    print_error "Failed to install dependencies"
    echo ""
    echo "This usually means missing system packages. Please install:"
    echo "  Ubuntu/Debian: sudo apt-get install python3-dev build-essential libpq-dev"
    echo "  Rocky/Alma: sudo dnf install python3-devel gcc make postgresql-devel"
    exit 1
}
print_success "Dependencies installed"

# Step 4: Generate .env file if not exists
print_step "Configuring environment..."

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Generating encryption keys and creating .env file...${NC}"

    # Generate encryption key (cryptography is now installed)
    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    SECRET_KEY=$(python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '!@#\$%^&*(-_=+)') for _ in range(50)))")

    # Validate keys were generated
    if [ -z "$ENCRYPTION_KEY" ] || [ -z "$SECRET_KEY" ]; then
        print_error "Failed to generate encryption keys"
        exit 1
    fi

    cat > "$ENV_FILE" << EOF
# Django Settings
SECRET_KEY=${SECRET_KEY}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (using SQLite for development)
# Path is relative to manage.py location
DATABASE_URL=sqlite:///db.sqlite3

# Celery (optional for development)
# If Redis is not available, set WEBOPS_BG_PROCESSOR=memory
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# WebOps Settings
WEBOPS_INSTALL_PATH=/opt/webops
WEBOPS_USER=hosting

# Deployment port allocation (for deployed apps, not the control panel)
MIN_PORT=8001
MAX_PORT=9000

# Background Processor (optional)
# Use "celery" for full features (requires Redis) or "memory" for simple dev
# WEBOPS_BG_PROCESSOR=memory
EOF
    print_success "Created .env file with generated keys"
else
    print_success "Using existing .env file"
fi

# Step 5: Check optional services
print_step "Checking optional services..."

# Check if Redis is available
if python -c "import redis; r = redis.Redis(); r.ping()" 2>/dev/null; then
    print_success "Redis is available (Celery background tasks enabled)"
else
    print_warning "Redis is not running (optional for development)"
    echo -e "${BLUE}Background tasks will use in-memory processor${NC}"
    echo -e "${BLUE}To enable Celery features, install and start Redis:${NC}"
    echo "  sudo apt-get install redis-server"
    echo "  sudo systemctl start redis-server"
fi

# Step 6: Run migrations
print_step "Setting up database..."
python manage.py migrate --no-input || {
    print_error "Database migration failed"
    echo "This might indicate a database schema issue."
    exit 1
}
print_success "Database migrations complete"

# Step 7: Create superuser
print_step "Setting up admin user..."

# SECURITY FIX: Generate random password instead of default 'admin123'
# Check if password file already exists
PASSWORD_FILE=".dev_admin_password"
if [ -f "$PASSWORD_FILE" ]; then
    ADMIN_PASSWORD=$(cat "$PASSWORD_FILE")
    echo "Using existing admin password from $PASSWORD_FILE"
else
    # Generate secure random password (20 characters, alphanumeric + special chars)
    ADMIN_PASSWORD=$(openssl rand -base64 20 | tr -d "=+/" | cut -c1-20)
    echo "$ADMIN_PASSWORD" > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
    echo "Generated new admin password and saved to $PASSWORD_FILE"
fi

python manage.py shell << PYEOF 2>&1 | tee /tmp/webops-superuser.log
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@webops.local', '$ADMIN_PASSWORD')
    print("✓ Created superuser: admin")
else:
    print("✓ Superuser already exists")
PYEOF

# Check if superuser creation succeeded
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    print_error "Failed to create superuser"
    echo "This might be due to missing migrations or database issues."
    echo "Check /tmp/webops-superuser.log for details"
    exit 1
fi

# Step 8: Collect static files
print_step "Collecting static files..."
python manage.py collectstatic --no-input --clear > /dev/null 2>&1
print_success "Static files collected"

# Verify stop_dev.sh exists
if [ ! -f "./stop_dev.sh" ]; then
    print_warning "stop_dev.sh not found (needed to stop services)"
elif [ ! -x "./stop_dev.sh" ]; then
    chmod +x ./stop_dev.sh
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${RED}⚠️  IMPORTANT: Server is NOT running yet!${NC}"
echo -e "${YELLOW}You must manually start the development server:${NC}\n"

echo -e "${BLUE}Start the server (REQUIRED):${NC}"
echo -e "  cd control-panel"
echo -e "  ./start_dev.sh\n"

echo -e "${BLUE}Alternative - Django only (without Celery):${NC}"
echo -e "  source venv/bin/activate"
echo -e "  python manage.py runserver\n"

echo -e "${BLUE}To stop all services:${NC}"
echo -e "  ./stop_dev.sh\n"

echo -e "${BLUE}After starting, access the application:${NC}"
echo -e "  Web UI:      http://127.0.0.1:8000"
echo -e "  Admin panel: http://127.0.0.1:8000/admin/"
echo -e "  ${GREEN}Login:${NC}"
echo -e "    Username: ${GREEN}admin${NC}"
echo -e "    Password: ${GREEN}$(cat $PASSWORD_FILE)${NC}"
echo -e ""
echo -e "  ${YELLOW}⚠  Password saved to: $PASSWORD_FILE${NC}"
echo -e "  ${YELLOW}⚠  Keep this file secure and do not commit it to version control${NC}"

echo -e "\n${YELLOW}Note:${NC} start_dev.sh runs on port 8000 by default"
echo -e "      Customize with: ./start_dev.sh 8080"
echo -e "\n${BLUE}For more help, see: POST_INSTALLATION.md${NC}"
