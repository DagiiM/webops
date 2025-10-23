# WebOps Development Guide

## Getting Started with the MVP

The MVP (Minimal Viable Product) is now complete and ready for testing and development.

### Quick Start Commands

```bash
# From the project root
cd control-panel
./quickstart.sh
source venv/bin/activate
python manage.py runserver
```

Visit: Start the development server and access at the default port
Login: `admin` / `admin123`

## Project Status

### ✅ What's Complete (MVP - v0.1.0)

**Core Infrastructure**
- Django 5.2.6+ project with proper structure
- PostgreSQL support (using SQLite for development)
- Celery configuration (ready for background tasks)
- Complete authentication system
- Admin interface
- Pyright strict type checking enabled

**Data Models**
- `BaseModel` - Abstract model with timestamps
- `Deployment` - Application deployments
- `DeploymentLog` - Deployment logs
- `Database` - Database credentials

**Utilities (`apps/core/utils/`)**
- `encryption.py` - Password generation and encryption
- `generators.py` - Secret key and port generation
- `validators.py` - URL and domain validation

**Web Interface**
- Beautiful, responsive UI (pure CSS, no frameworks)
- Dashboard with deployment statistics
- Deployment CRUD operations
- Real-time deployment logs viewer
- Clean navigation and user experience

**Development Tools**
- Quick start script with auto-setup
- Auto-generated encryption keys
- Environment configuration
- Comprehensive documentation

### ⏳ What's Next (Phase 2)

**Priority 1: Deployment Pipeline**
- File: `apps/deployments/services.py`
- Implement: `DeploymentService` class
- Features:
  - Git repository cloning
  - Project type detection
  - Virtual environment creation
  - Dependency installation
  - Service configuration

**Priority 2: Background Tasks**
- File: `apps/deployments/tasks.py`
- Implement: Celery tasks for async operations
- Tasks:
  - `deploy_django_app`
  - `deploy_static_site`
  - `restart_service`
  - `stop_service`

**Priority 3: System Templates**
- Directory: `templates/nginx/` and `templates/systemd/`
- Create: Configuration templates
- Files:
  - `nginx/app.conf.j2`
  - `systemd/app.service.j2`
  - `env.j2`

## Development Workflow

### Adding a New Feature

1. **Plan** - Check TODO.md for feature specifications
2. **Code** - Follow patterns in CLAUDE.md
3. **Test** - Create tests (when test framework is set up)
4. **Document** - Update relevant docs
5. **Commit** - Use clear commit messages

### Code Standards

From CLAUDE.md:

```python
# Always use type hints with Self for methods
from typing import Self, Dict, Any

def my_function(param: str, count: int = 0) -> Dict[str, Any]:
    """Clear docstring explaining the function.

    Args:
        param: Description of the parameter
        count: Description with default value

    Returns:
        Dictionary containing the result data

    Raises:
        ValueError: If param is invalid
    """
    pass

class MyClass:
    def __init__(self: Self, name: str) -> None:
        """Initialize the class.
        
        Args:
            name: The name for this instance
        """
        self.name = name

# Maximum line length: 100 characters
# Use f-strings for formatting
# Follow PEP 8 with Google-style docstrings
# Enable Pyright strict mode for type checking
```

### File Structure Conventions

```
apps/
└── app_name/
    ├── models.py      # Database models
    ├── views.py       # View functions
    ├── urls.py        # URL routing
    ├── services.py    # Business logic (NOT in views!)
    ├── tasks.py       # Celery background tasks
    ├── admin.py       # Django admin config
    ├── utils.py       # Helper functions
    └── tests.py       # Unit tests
```

## Common Development Tasks

### Create a New Django App

```bash
python manage.py startapp app_name apps/app_name
```

Then:
1. Update `apps/app_name/apps.py` - change `name = "apps.app_name"`
2. Add to `INSTALLED_APPS` in `config/settings.py`
3. Create models, views, URLs as needed

### Make Database Changes

```bash
# Create migration
python manage.py makemigrations

# Apply migration
python manage.py migrate

# View SQL that will run
python manage.py sqlmigrate app_name 0001
```

### Add a New View

1. Create view function in `apps/app_name/views.py`
2. Add URL pattern in `apps/app_name/urls.py`
3. Create template in `templates/app_name/`
4. Add navigation link in `templates/base.html`

### Add Utilities

Place reusable functions in `apps/core/utils/`:

```python
# apps/core/utils/my_utils.py
from typing import Optional

def my_utility(param: str) -> Optional[str]:
    """Utility function description."""
    pass
```

Update `apps/core/utils/__init__.py`:

```python
from .my_utils import my_utility

__all__ = ['my_utility', ...]
```

### Working with Static Files

CSS and JavaScript go in `static/`:

```
static/
├── css/
│   └── main.css      # Main stylesheet (NO frameworks!)
└── js/
    └── main.js       # Vanilla JS only (NO npm!)
```

After changes:

```bash
python manage.py collectstatic
```

## Testing

### Manual Testing

```bash
# Start dev server
python manage.py runserver

# In another terminal, test with curl
curl http://127.0.0.1:8000/

# Or use Django shell
python manage.py shell
```

### Unit Tests (When Implemented)

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.deployments

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

## Debugging

### Django Debug Toolbar (Optional)

Add to requirements.txt:
```
django-debug-toolbar==4.2.0
```

### Check for Issues

```bash
# Check for problems
python manage.py check

# Check for security issues
python manage.py check --deploy
```

### View Logs

Development logs go to console. In production, see:
- Application: `control-panel/logs/webops.log`
- Nginx: `/var/log/nginx/`
- Systemd: `journalctl -u webops-web`

## Database Management

### Django Shell

```bash
python manage.py shell
```

```python
# Example queries
from apps.deployments.models import Deployment

# Get all deployments
deployments = ApplicationDeployment.objects.all()

# Create deployment
deployment = ApplicationDeployment.objects.create(
    name='test-app',
    repo_url='https://github.com/user/repo',
    deployed_by=user
)

# Filter
running = ApplicationDeployment.objects.filter(status='running')
```

### Reset Database

```bash
# Development only!
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

## Environment Variables

Edit `.env` in project root:

```bash
# Django
SECRET_KEY=<auto-generated>
DEBUG=True  # False in production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///path/to/db.sqlite3

# Security
ENCRYPTION_KEY=<auto-generated>

# WebOps
MIN_PORT=8001
MAX_PORT=9000
```

## Performance Tips

### Database Queries

```python
# Bad - N+1 queries
for deployment in ApplicationDeployment.objects.all():
    print(deployment.deployed_by.username)

# Good - Use select_related
for deployment in ApplicationDeployment.objects.select_related('deployed_by'):
    print(deployment.deployed_by.username)
```

### Caching (Future)

```python
from django.core.cache import cache

# Set
cache.set('key', value, timeout=300)

# Get
value = cache.get('key')
```

## Contributing to WebOps

### Before You Start

1. Read CLAUDE.md thoroughly
2. Check TODO.md for the task you want to work on
3. Understand the existing code patterns
4. Set up your development environment

### Code Review Checklist

Before committing:

- [ ] Follows CLAUDE.md standards
- [ ] Type hints on all functions
- [ ] Docstrings on public functions/classes
- [ ] No npm dependencies added
- [ ] Pure vanilla JavaScript (if frontend)
- [ ] Tests written (when test framework exists)
- [ ] Documentation updated
- [ ] No console.log or debug statements
- [ ] Proper error handling
- [ ] Security considerations reviewed

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/deployment-service

# Make changes and commit
git add .
git commit -m "Add deployment service with Git cloning"

# Push branch
git push origin feature/deployment-service

# Create pull request on GitHub
```

### Commit Message Format

```
Add deployment service with repository cloning

- Implement DeploymentService.clone_repository()
- Add Git authentication support
- Handle errors and logging
- Update tests

Refs: TODO.md Phase 2.1.1
```

## Helpful Resources

### Documentation
- Django: https://docs.djangoproject.com/
- Celery: https://docs.celeryq.dev/
- PostgreSQL: https://www.postgresql.org/docs/

### WebOps Docs
- `CLAUDE.md` - Coding standards and patterns
- `TODO.md` - Complete feature roadmap
- `PROPOSAL.md` - Architecture and design decisions
- `QUICKSTART.md` - Quick start guide
- `MVP-STATUS.md` - Current implementation status

### Tools
- Django Debug Toolbar
- ipdb (debugging)
- black (code formatting)
- flake8 (linting)

## Troubleshooting

### "No module named 'apps'"

Make sure you're in the `control-panel` directory and virtual environment is activated:

```bash
cd control-panel
source venv/bin/activate
```

### "Database is locked"

Stop all running instances:

```bash
pkill -f "manage.py runserver"
```

### "Port already in use"

Use a different port:

```bash
python manage.py runserver 8001
```

### Static files not loading

```bash
python manage.py collectstatic --clear
DEBUG=True python manage.py runserver
```

### Import errors

Check that `apps/` has `__init__.py` and app config has correct name:

```python
# apps/myapp/apps.py
class MyappConfig(AppConfig):
    name = "apps.myapp"  # Must be "apps.myapp", not "myapp"
```

## Next Steps

### Immediate Priorities

1. **Implement DeploymentService** (`apps/deployments/services.py`)
   - Start with `clone_repository()` method
   - Add `detect_project_type()` method
   - Implement `generate_port()` method

2. **Create Celery Tasks** (`apps/deployments/tasks.py`)
   - Implement `deploy_django_app` task
   - Add proper error handling and logging
   - Update deployment status in database

3. **System Templates** (`templates/nginx/`, `templates/systemd/`)
   - Create Jinja2 templates for Nginx
   - Create systemd service templates
   - Add environment file template

### Long-term Goals

- Phase 2: Complete deployment pipeline
- Phase 3: CLI tool
- Phase 4: Testing and documentation
- Phase 5: Production setup script and polish

## Questions?

- Check QUICKSTART.md for setup issues
- Read CLAUDE.md for coding questions
- Review TODO.md for feature specifications
- See MVP-STATUS.md for current implementation status

---

**Happy Coding!** 🚀

Remember: Zero npm dependencies, pure vanilla JS, and follow Django best practices!