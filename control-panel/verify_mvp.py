#!/usr/bin/env python
"""
WebOps MVP Verification Script

This script verifies that the MVP is correctly installed and configured.
Run this after ./quickstart.sh to ensure everything is working.

Usage:
    python verify_mvp.py
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Color codes for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def log_success(message: str):
    print(f"{GREEN}✓{NC} {message}")

def log_error(message: str):
    print(f"{RED}✗{NC} {message}")

def log_info(message: str):
    print(f"{BLUE}ℹ{NC} {message}")

def log_warning(message: str):
    print(f"{YELLOW}⚠{NC} {message}")

def check_django_setup():
    """Check if Django is properly set up."""
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        django.setup()
        log_success("Django setup successful")
        return True
    except Exception as e:
        log_error(f"Django setup failed: {e}")
        return False

def check_database():
    """Check if database is accessible."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        log_success("Database connection successful")
        return True
    except Exception as e:
        log_error(f"Database connection failed: {e}")
        return False

def check_models():
    """Check if models are properly defined."""
    try:
        from apps.core.common.models import BaseModel
        from apps.deployments.models import BaseDeployment, ApplicationDeployment,  DeploymentLog
        from apps.databases.models import Database
        log_success("All models imported successfully")
        return True
    except Exception as e:
        log_error(f"Model import failed: {e}")
        return False

def check_admin_user():
    """Check if admin user exists."""
    try:
        from django.contrib.auth.models import User
        if User.objects.filter(username='admin').exists():
            log_success("Admin user exists")
            return True
        else:
            log_warning("Admin user not found (run ./quickstart.sh)")
            return False
    except Exception as e:
        log_error(f"User check failed: {e}")
        return False

def check_static_files():
    """Check if static files exist."""
    static_css = Path('static/css/main.css')
    static_js = Path('static/js/main.js')

    checks = [
        (static_css.exists(), f"Static CSS exists: {static_css}"),
        (static_js.exists(), f"Static JS exists: {static_js}"),
    ]

    all_passed = True
    for passed, message in checks:
        if passed:
            log_success(message)
        else:
            log_error(message)
            all_passed = False

    return all_passed

def check_templates():
    """Check if templates exist."""
    templates = [
        Path('templates/base.html'),
        Path('templates/dashboard.html'),
        Path('templates/auth/login.html'),
        Path('templates/deployments/list.html'),
    ]

    all_exist = True
    for template in templates:
        if template.exists():
            log_success(f"Template exists: {template}")
        else:
            log_error(f"Template missing: {template}")
            all_exist = False

    return all_exist

def check_environment():
    """Check environment configuration."""
    # Resolve .env file robustly:
    # 1) Use Django BASE_DIR if available
    # 2) Search upwards from current file for a parent containing manage.py
    # 3) Fallback to repo root assumptions
    env_file = _resolve_env_file()

    if env_file and env_file.exists():
        log_success(f"Environment file exists: {env_file}")

        # Check for required variables
        with open(env_file) as f:
            content = f.read()
            required_vars = ['SECRET_KEY', 'DEBUG', 'DATABASE_URL', 'ENCRYPTION_KEY']
            all_found = True
            for var in required_vars:
                if var in content:
                    log_success(f"  {var} is configured")
                else:
                    log_error(f"  {var} is missing")
                    all_found = False
            return all_found
    else:
        log_error(f"Environment file not found")
        log_info("Run ./quickstart.sh to create it")
        return False

def _resolve_env_file() -> Optional[Path]:
    """Attempt to locate .env file relative to project layout."""
    # Try Django settings for BASE_DIR
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        django.setup()
        from django.conf import settings as dj_settings
        base_dir = Path(getattr(dj_settings, 'BASE_DIR', Path(__file__).resolve().parent))
        candidate = base_dir / '.env'
        if candidate.exists():
            return candidate
    except Exception:
        pass

    # Walk upwards from this file to find a directory with manage.py or .env
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        manage_py = parent / 'manage.py'
        env_candidate = parent / '.env'
        if env_candidate.exists():
            return env_candidate
        if manage_py.exists():
            # Prefer .env next to manage.py
            candidate = parent / '.env'
            if candidate.exists():
                return candidate
            # Or one level up
            up_candidate = parent.parent / '.env'
            if up_candidate.exists():
                return up_candidate

    # Fallback to repo root assumed two levels up
    fallback = Path(__file__).resolve().parents[1] / '.env'
    return fallback if fallback.exists() else None

def check_utilities():
    """Check if core utilities are working."""
    try:
        from apps.core.utils import generate_password, generate_port, validate_repo_url

        # Test password generation
        password = generate_password(16)
        if len(password) == 16:
            log_success("Password generation working")
        else:
            log_error("Password generation failed")
            return False

        # Test port generation
        port = generate_port()
        if 8001 <= port <= 9000:
            log_success(f"Port generation working (got {port})")
        else:
            log_error("Port generation failed")
            return False

        # Test validation
        if validate_repo_url('https://github.com/user/repo'):
            log_success("URL validation working")
        else:
            log_error("URL validation failed")
            return False

        return True
    except Exception as e:
        log_error(f"Utilities check failed: {e}")
        return False

def run_verification():
    """Run all verification checks."""
    print(f"\n{BLUE}=== WebOps MVP Verification ==={NC}\n")

    checks = [
        ("Django Setup", check_django_setup),
        ("Database Connection", check_database),
        ("Models", check_models),
        ("Admin User", check_admin_user),
        ("Static Files", check_static_files),
        ("Templates", check_templates),
        ("Environment Config", check_environment),
        ("Core Utilities", check_utilities),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n{BLUE}Checking: {name}{NC}")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            log_error(f"Check failed with exception: {e}")
            results.append((name, False))

    # Summary
    print(f"\n{BLUE}=== Verification Summary ==={NC}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = f"{GREEN}PASS{NC}" if result else f"{RED}FAIL{NC}"
        print(f"  {status} - {name}")

    print(f"\n{BLUE}Results: {passed}/{total} checks passed{NC}\n")

    if passed == total:
        print(f"{GREEN}✓ All checks passed! MVP is ready to use.{NC}")
        print(f"\n{BLUE}To start the server:{NC}")
        print(f"  source venv/bin/activate")
        print(f"  python manage.py runserver")
        print(f"\n{BLUE}Then visit:{NC} http://127.0.0.1:8000")
        print(f"{BLUE}Login:{NC} admin / admin123\n")
        return 0
    else:
        print(f"{YELLOW}⚠ Some checks failed. Please review the errors above.{NC}")
        print(f"\n{BLUE}Try running:{NC}")
        print(f"  ./quickstart.sh\n")
        return 1

if __name__ == '__main__':
    sys.exit(run_verification())