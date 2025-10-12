#!/bin/bash
# WebOps Quick Start Script for Development
# This script sets up the development environment

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== WebOps Development Quick Start ===${NC}\n"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment not found!${NC}"
    echo "Please run from the control-panel directory"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Generate encryption key if not exists
if [ ! -f "../.env" ]; then
    echo -e "${BLUE}Generating encryption key and creating .env file...${NC}"
    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    SECRET_KEY=$(python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '!@#\$%^&*(-_=+)') for _ in range(50)))")

    cat > ../.env << EOF
# Django Settings
SECRET_KEY=${SECRET_KEY}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (using SQLite for development)
DATABASE_URL=sqlite:///$(pwd)/db.sqlite3

# Celery (optional for development)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# WebOps Settings
WEBOPS_INSTALL_PATH=/opt/webops
WEBOPS_USER=hosting
MIN_PORT=8001
MAX_PORT=9000
EOF
    echo -e "${GREEN}Created .env file with generated keys${NC}"
fi

# Run migrations if needed
echo -e "\n${BLUE}Running database migrations...${NC}"
python manage.py migrate --no-input

# Create superuser if it doesn't exist
echo -e "\n${BLUE}Setting up admin user...${NC}"
python manage.py shell << 'PYEOF'
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@webops.local', 'admin123')
    print("✓ Created superuser: admin/admin123")
else:
    print("✓ Superuser already exists")
PYEOF

# Collect static files
echo -e "\n${BLUE}Collecting static files...${NC}"
python manage.py collectstatic --no-input --clear > /dev/null 2>&1

echo -e "\n${GREEN}=== Setup Complete! ===${NC}"
echo -e "\n${BLUE}To start the development server:${NC}"
echo -e "  cd control-panel"
echo -e "  source venv/bin/activate"
echo -e "  python manage.py runserver"
echo -e "\n${BLUE}Then visit:${NC} http://127.0.0.1:8000"
echo -e "${BLUE}Login with:${NC} admin / admin123"
echo -e "\n${BLUE}Admin panel:${NC} http://127.0.0.1:8000/admin/"