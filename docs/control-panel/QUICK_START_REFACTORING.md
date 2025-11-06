# Quick Start: Legacy Code Refactoring

This is a condensed action plan for immediately addressing critical legacy code. For the full report, see [LEGACY_CODE_REPORT.md](./LEGACY_CODE_REPORT.md).

---

## Critical Tasks (Do This Week)

### 1. Remove Legacy Database Creation View (2 hours)

**Why:** Security risk - creates databases without validation

```bash
# Step 1: Remove the legacy view function
# Edit apps/databases/views.py and delete lines 155-180

# Step 2: Remove the URL route
# Edit apps/databases/urls.py and delete line 9:
# path('create-legacy/', views.database_create_legacy, name='database_create_legacy'),

# Step 3: Test
./venv/bin/python manage.py test apps.databases

# Step 4: Commit
git add apps/databases/views.py apps/databases/urls.py
git commit -m "Remove legacy database_create_legacy view

BREAKING CHANGE: Removed deprecated database_create_legacy view.
All database creation now uses DatabaseCreateView class-based view.

- Removed database_create_legacy function (views.py:155-180)
- Removed create-legacy/ URL route
- All functionality available in new create/ endpoint

Refs: LEGACY_CODE_REPORT.md"
```

---

### 2. Replace Print Statements with Logging (1 day)

**Why:** Security & operational risk - may leak sensitive data

#### Step 2.1: Set up logging configuration (30 min)

Add to `config/settings.py`:

```python
import os

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            'class': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            'class': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'webops.log'),
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'errors.log'),
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'apps': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

#### Step 2.2: Update apps/databases/views.py (2 hours)

```python
# Add at top of file
import logging

logger = logging.getLogger(__name__)

# Replace all print statements with logger calls

# Before:
print(f"User authenticated: {request.user.is_authenticated}")

# After:
logger.debug("User authenticated: %s", request.user.is_authenticated,
             extra={'user_id': request.user.id if request.user.is_authenticated else None})

# Before:
print(f"Database created successfully: {form.instance.name}")

# After:
logger.info("Database created successfully: %s", form.instance.name,
            extra={'database_id': form.instance.id, 'user_id': self.request.user.id})

# Before:
print(f"Error creating database: {e}")

# After:
logger.error("Error creating database: %s", str(e),
             exc_info=True,  # Include stack trace
             extra={'form_data': form.cleaned_data})
```

#### Step 2.3: Script to find all print statements

```bash
# Create a file with all print statements
grep -rn "print(" apps/ --include="*.py" | grep -v "venv" | grep -v "__pycache__" > print_statements.txt

# Count by file
grep -rn "print(" apps/ --include="*.py" | grep -v "venv" | cut -d: -f1 | sort | uniq -c | sort -rn

# Output:
#  14 apps/databases/views.py
#   5 apps/deployments/views/application_deployment.py
#   ... etc
```

#### Step 2.4: Replace systematically

**Priority order:**
1. `apps/databases/views.py` (14 prints)
2. `apps/deployments/views/application_deployment.py` (5+ prints)
3. `apps/deployments/tasks/application.py`
4. All other files

**Test after each file:**
```bash
./venv/bin/python manage.py test apps.databases
./venv/bin/python manage.py test apps.deployments
```

---

### 3. Test Everything (2 hours)

```bash
# Run all tests
./venv/bin/python manage.py test

# Check for any missed prints
grep -rn "print(" apps/ --include="*.py" | grep -v "venv" | grep -v "test" | wc -l

# Manual testing
./start_dev.sh
# Navigate to http://localhost:8000/databases/
# Test database creation
# Check logs/webops.log for proper logging
```

---

## 🟡 Medium Priority (Next Week)

### 4. Remove Duplicate Dependency UI (4 hours)

**Files to edit:**
- `templates/databases/create.html`
- `templates/databases/list.html`

**What to remove:**

In `create.html`:
1. Delete lines 83-103 (Legacy dependency warning div)
2. Delete JavaScript functions:
   - `updateLegacyWarning()` method (lines 668-689)
   - Remove calls to `updateLegacyWarning()` (lines 525-526, 607)

In `list.html`:
1. Delete similar legacy warning section
2. Remove legacy JavaScript methods

**Test:**
```bash
# Manual testing required
./start_dev.sh

# Test PostgreSQL database creation:
# 1. Select PostgreSQL
# 2. Verify new dependency UI shows
# 3. Verify old warning doesn't appear
# 4. Test dependency installation
# 5. Create database successfully
```

---

### 5. Add .gitignore for logs (5 min)

```bash
# Add to .gitignore
echo "logs/" >> .gitignore
echo "*.log" >> .gitignore

git add .gitignore
git commit -m "Add logs directory to .gitignore"
```

---

## 🟢 Low Priority (This Month)

### 6. Convert TODOs to GitHub Issues (1 day)

```bash
# Extract all TODOs
grep -rn "TODO\|FIXME" --include="*.py" apps/ addons/ | grep -v "venv" > todos.txt

# For each TODO, create a GitHub issue:
# 1. Copy location and description
# 2. Add labels: enhancement, tech-debt
# 3. Add to project board
# 4. Replace TODO with issue reference

# Example:
# Before:
# TODO: Implement service restart logic (Phase 2.5)

# After:
# See issue #42 - Implement service restart logic
```

---

### 7. Add Deprecation Warnings (4 hours)

For backward compatibility layers in `apps/core/`:

```python
import warnings

class BrandingSettings(models.Model):
    # ... model fields ...

    def deprecated_method(self):
        """Deprecated: Use BrandingService instead.

        This method will be removed in version 2.0.
        """
        warnings.warn(
            "BrandingSettings.deprecated_method() is deprecated and will be "
            "removed in version 2.0. Use BrandingService.method() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return BrandingService().method()
```

---

## 📊 Progress Tracking

Create a checklist to track progress:

```markdown
## Week 1: Critical Cleanup

- [ ] Remove legacy database_create_legacy view
- [ ] Set up Django logging configuration
- [ ] Replace print statements in apps/databases/views.py
- [ ] Replace print statements in apps/deployments/views/
- [ ] Replace print statements in all other files
- [ ] Run full test suite
- [ ] Manual testing of critical paths
- [ ] Update CHANGELOG.md

## Week 2: UI Cleanup

- [ ] Remove legacy dependency UI from create.html
- [ ] Remove legacy dependency UI from list.html
- [ ] Remove legacy JavaScript functions
- [ ] Test dependency installation flow
- [ ] Update user documentation
- [ ] Add screenshots to docs

## Week 3: Code Quality

- [ ] Extract all TODOs to todos.txt
- [ ] Create GitHub issues for each TODO
- [ ] Replace TODO comments with issue references
- [ ] Add deprecation warnings to models
- [ ] Update API documentation
- [ ] Code review with team

## Week 4: Documentation & Monitoring

- [ ] Update CLAUDE.md
- [ ] Update README.md
- [ ] Create migration guide
- [ ] Set up log monitoring
- [ ] Performance benchmarking
- [ ] Security audit
- [ ] Deploy to staging
- [ ] Monitor and fix issues
- [ ] Deploy to production
```

---

## 🚀 Quick Commands

```bash
# Find legacy code
make find-legacy  # If you have a Makefile

# Or manually:
grep -rn "legacy\|deprecated\|TODO\|print(" --include="*.py" apps/ | grep -v "venv"

# Run tests
./venv/bin/python manage.py test

# Check code quality
flake8 apps/ --exclude=venv,migrations
pylint apps/ --ignore=venv,migrations

# Count lines of code
find apps -name "*.py" -type f ! -path "*/venv/*" ! -path "*/migrations/*" | xargs wc -l
```

---

## 📈 Success Metrics

Track these metrics before and after refactoring:

```bash
# Before refactoring
echo "=== BEFORE REFACTORING ===" > metrics.txt
echo "Print statements: $(grep -rn 'print(' apps/ --include='*.py' | wc -l)" >> metrics.txt
echo "TODO markers: $(grep -rn 'TODO\|FIXME' apps/ --include='*.py' | wc -l)" >> metrics.txt
echo "Legacy functions: $(grep -rn 'legacy' apps/ --include='*.py' | wc -l)" >> metrics.txt
echo "Test coverage: $(./venv/bin/python -m coverage run --source=apps manage.py test && ./venv/bin/python -m coverage report | tail -1)" >> metrics.txt
cat metrics.txt

# After refactoring (run same commands)
echo "=== AFTER REFACTORING ===" >> metrics.txt
# ... same commands ...
```

---

## ⚠️ Important Notes

1. **Backup First:** Always create a git branch before refactoring
2. **Test Frequently:** Run tests after each change
3. **Commit Often:** Make small, atomic commits
4. **Document Everything:** Update CHANGELOG.md and docs
5. **Code Review:** Get team review before merging

---

## 🆘 Troubleshooting

### Tests failing after removing print statements

```bash
# Check if tests depend on print output
grep -rn "print" apps/*/tests.py

# Update tests to use logging instead
# Or mock logger in tests
```

### Logging not working

```bash
# Check logs directory exists
mkdir -p logs

# Check permissions
chmod 755 logs

# Test logging manually
./venv/bin/python manage.py shell
>>> import logging
>>> logger = logging.getLogger('apps')
>>> logger.info('Test message')
>>> exit()

# Check log file
cat logs/webops.log
```

### Database creation broken after removing legacy view

```bash
# Ensure new view is working
./venv/bin/python manage.py shell
>>> from apps.databases.views import DatabaseCreateView
>>> # Should not raise ImportError

# Check URLs
./venv/bin/python manage.py show_urls | grep database
```

---

## 📚 Additional Resources

- [Full Legacy Code Report](./LEGACY_CODE_REPORT.md)
- [Django Logging Documentation](https://docs.djangoproject.com/en/5.0/topics/logging/)
- [WebOps AGENTS.md](../AGENTS.md)
- [WebOps CONTRIBUTING.md](../CONTRIBUTING.md)

---

**Last Updated:** 2025-10-28
**Next Review:** After Phase 1 completion
