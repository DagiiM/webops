# Migration Guide: v1.0.7 → v2.0.0

This guide helps you migrate from WebOps v1.0.7 to the upcoming v2.0.0 release.

---

## Overview

Version 2.0.0 will remove deprecated APIs and introduce some breaking changes. This guide ensures a smooth migration.

**Current Version:** 1.0.7
**Target Version:** 2.0.0 (planned)
**Estimated Release:** Q2 2026

---

## Breaking Changes

### 1. Deprecated Branding Methods Removed

#### What's Changing
Two internal methods in `BrandingSettings` model will be removed:
- `_apply_theme_preset()`
- `_generate_hex_colors()`

#### Migration Path

**Before (v1.0.7 - deprecated):**
```python
from apps.core.branding.models import BrandingSettings

settings = BrandingSettings.objects.first()
settings._apply_theme_preset()      # DeprecationWarning
settings._generate_hex_colors()     # DeprecationWarning
```

**After (v2.0.0):**
```python
from apps.core.branding.services import BrandingService
from apps.core.branding.models import BrandingSettings

settings = BrandingSettings.objects.first()

# Apply theme preset
preset = BrandingService.apply_theme_preset(settings.theme_preset)
if preset:
    for key, value in preset.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    settings.save()

# Generate hex colors
settings.primary_color = BrandingService.hsl_to_hex(
    settings.primary_hue,
    settings.primary_saturation,
    settings.primary_lightness
)
settings.save()
```

#### Timeline
- **v1.0.7:** Methods deprecated with warnings
- **v1.1.x:** Warnings continue (grace period)
- **v2.0.0:** Methods removed

#### Impact
**Low** - These are internal methods rarely used outside the model.

---

### 2. Backward Compatibility Layer Removal (Planned)

#### What's Changing
The backward compatibility re-exports in `/apps/core/` may be removed:
- `apps/core/models.py` re-exports
- `apps/core/forms.py` re-exports
- `apps/core/views.py` re-exports

#### Migration Path

**Before (v1.0.7 - still works):**
```python
from apps.core.models import BrandingSettings
from apps.core.forms import DatabaseForm
from apps.core.views import some_view
```

**After (v2.0.0 - preferred):**
```python
from apps.core.branding.models import BrandingSettings
from apps.databases.forms import DatabaseForm
from apps.core.branding.views import some_view
```

#### Timeline
- **v1.0.7:** Both old and new imports work
- **v1.1.x:** Deprecation warnings added to old imports
- **v2.0.0:** Old imports removed

#### Impact
**Medium** - May affect many imports, but automated migration possible.

#### Automated Migration
```bash
# Use this script to update imports (v2.0.0 release will include this)
python manage.py migrate_imports --dry-run
python manage.py migrate_imports --apply
```

---

## Deprecation Warnings

### How to Find Deprecated Usage

Run your code with deprecation warnings enabled:

```bash
# Python 3.11+
python -W default::DeprecationWarning manage.py runserver

# Or in code
import warnings
warnings.simplefilter('default', DeprecationWarning)
```

### Common Warning Messages

```
DeprecationWarning: _apply_theme_preset() is deprecated and will be removed
in version 2.0. Use BrandingService.apply_theme_preset() instead.
```

**Action:** Update to use `BrandingService.apply_theme_preset()`

```
DeprecationWarning: _generate_hex_colors() is deprecated and will be removed
in version 2.0. Use BrandingService.hsl_to_hex() instead.
```

**Action:** Update to use `BrandingService.hsl_to_hex()`

---

## New Features in v2.0.0 (Planned)

### 1. Enhanced Security
- [ ] Additional authentication methods
- [ ] Improved RBAC (Role-Based Access Control)
- [ ] Audit logging enhancements

### 2. Performance Improvements
- [ ] Query optimization
- [ ] Caching layer
- [ ] Async support for long-running tasks

### 3. API Improvements
- [ ] RESTful API v2
- [ ] GraphQL endpoint
- [ ] Webhook improvements

### 4. Developer Experience
- [ ] Improved error messages
- [ ] Better type hints
- [ ] Enhanced CLI commands

---

## Migration Checklist

### Before Upgrading

- [ ] Review this migration guide
- [ ] Run deprecation warnings check
- [ ] Update deprecated code
- [ ] Test in development environment
- [ ] Backup production database
- [ ] Review CHANGELOG for v2.0.0

### During Upgrade

- [ ] Update dependencies (`pip install -r requirements.txt`)
- [ ] Run migrations (`python manage.py migrate`)
- [ ] Collect static files (`python manage.py collectstatic`)
- [ ] Run tests (`python manage.py test`)
- [ ] Check for deprecation warnings

### After Upgrade

- [ ] Verify all features working
- [ ] Check logs for errors
- [ ] Monitor performance
- [ ] Update documentation
- [ ] Notify team of changes

---

## Testing Your Migration

### 1. Run Test Suite
```bash
python manage.py test
```

### 2. Check for Deprecation Warnings
```bash
python -W default::DeprecationWarning manage.py check
```

### 3. Manual Testing
- [ ] Database creation (all types)
- [ ] User authentication
- [ ] Deployment workflows
- [ ] Branding/theming
- [ ] API endpoints

### 4. Performance Testing
```bash
# Before upgrade
python manage.py test --timing

# After upgrade
python manage.py test --timing

# Compare results
```

---

## Rollback Plan

If issues occur after upgrading to v2.0.0:

### Quick Rollback
```bash
# 1. Restore database backup
pg_restore -d webops backup_pre_v2.dump

# 2. Revert to v1.0.7
git checkout v1.0.7
pip install -r requirements.txt

# 3. Restart services
./stop_dev.sh
./start_dev.sh
```

### Data Migration Rollback
```bash
# If migrations applied
python manage.py migrate app_name previous_migration_name
```

---

## Getting Help

### Resources
- [Changelog](../CHANGELOG.md)
- [Documentation](../README.md)
- [GitHub Issues](https://github.com/yourorg/webops/issues)
- [Community Forum](https://forum.yourproject.com)

### Support Channels
- **Email:** support@yourproject.com
- **Chat:** Slack/Discord community
- **Phone:** Enterprise customers only

### Reporting Issues
If you encounter issues during migration:
1. Check known issues in CHANGELOG
2. Search GitHub issues
3. Create new issue with:
   - Version numbers (from → to)
   - Error messages
   - Steps to reproduce
   - Environment details

---

## Timeline

| Version | Status | Release Date | Notes |
|---------|--------|--------------|-------|
| 1.0.6 | Released | 2025-10-27 | Previous stable |
| **1.0.7** | **Released** | **2025-10-28** | **Current (you are here)** |
| 1.1.0 | Planned | Q1 2026 | Enhanced warnings |
| 1.2.0 | Planned | Q1 2026 | Feature updates |
| 2.0.0-beta | Planned | Q2 2026 | Beta testing |
| 2.0.0 | Planned | Q2 2026 | Major release |

---

## Frequently Asked Questions

### Q: When will v2.0.0 be released?
**A:** Estimated Q2 2026. Follow the changelog for updates.

### Q: Are there breaking changes in v1.0.7?
**A:** No. Version 1.0.7 only adds deprecation warnings. All features work normally.

### Q: Can I skip from 1.0.6 to 2.0.0?
**A:** Yes, but we recommend upgrading to 1.0.7 first to see deprecation warnings.

### Q: Will v1.x receive security updates after v2.0.0?
**A:** Yes, v1.x will receive security updates for 6 months after v2.0.0 release.

### Q: How long do I have to migrate?
**A:** Deprecated features work in all v1.x releases. You have until v2.0.0 (Q2 2026).

### Q: Can I use both old and new APIs?
**A:** Yes, during v1.x releases. In v2.0.0, only new APIs will work.

### Q: What if I can't update before v2.0.0?
**A:** Stay on latest v1.x release (will be v1.2.x) until you're ready.

---

## Additional Notes

### Semantic Versioning

WebOps follows [Semantic Versioning](https://semver.org/):
- **Major (2.0.0):** Breaking changes
- **Minor (1.1.0):** New features, backward compatible
- **Patch (1.0.7):** Bug fixes, backward compatible

### Deprecation Policy

- **Notice Period:** Minimum 6 months
- **Warnings:** Added in minor version
- **Removal:** Next major version only
- **Documentation:** Always updated

### Support Policy

- **Current Major:** Full support
- **Previous Major:** Security updates for 6 months
- **Older Versions:** Community support only

---

## Summary

**Key Points:**
- ✅ No immediate action required for v1.0.7
- ⚠️ Update deprecated code before v2.0.0
- 📅 Estimated 18 months until v2.0.0
- 🔄 Use deprecation warnings to find issues
- 📚 Keep this guide handy for reference

**Ready to Migrate:**
1. Run with deprecation warnings
2. Fix any warnings
3. Test thoroughly
4. Upgrade when ready

---

**Last Updated:** 2025-10-28
**Next Review:** When v2.0.0-beta is released
**Maintainer:** WebOps Team
