# Legacy Code Summary

Quick reference for legacy code in WebOps. For detailed report, see [LEGACY_CODE_REPORT.md](./LEGACY_CODE_REPORT.md).

---

## 🔴 Critical Issues (Fix This Week)

| Issue | Location | Risk | Effort |
|-------|----------|------|--------|
| Legacy database creation view | `apps/databases/views.py:155-180` | **HIGH** - No validation | 2 hours |
| Debug print statements | 66 instances across codebase | **MEDIUM** - May leak data | 1 day |

---

## 🟡 Medium Priority (Fix Next Week)

| Issue | Location | Risk | Effort |
|-------|----------|------|--------|
| Duplicate dependency UI | `templates/databases/create.html:83-103` | **MEDIUM** - Maintenance burden | 4 hours |
| Legacy dependency JS | `templates/databases/create.html:525-689` | **LOW** - Confusion | 2 hours |

---

## 🟢 Low Priority (Fix This Month)

| Issue | Count | Risk | Effort |
|-------|-------|------|--------|
| TODO markers | 19+ | **LOW** - Tracked | 1 day |
| Backward compat layers | 3 files | **LOW** - Intentional | 2 days |
| Deprecated model methods | Few | **LOW** - Documented | 4 hours |

---

## Quick Action Items

### Today
```bash
# Remove legacy database view
# Edit: apps/databases/views.py (delete lines 155-180)
# Edit: apps/databases/urls.py (delete line 9)
```

### This Week
```bash
# Set up logging
# Edit: config/settings.py (add LOGGING config)

# Replace print statements
# Files: apps/databases/views.py, apps/deployments/views/*.py
```

### Next Week
```bash
# Remove duplicate UI
# Files: templates/databases/create.html, templates/databases/list.html
```

---

## Files to Modify

### High Priority
- `apps/databases/views.py` - Remove legacy view, add logging
- `apps/databases/urls.py` - Remove legacy URL
- `config/settings.py` - Add logging configuration
- `apps/deployments/views/application_deployment.py` - Replace prints

### Medium Priority
- `templates/databases/create.html` - Remove duplicate UI
- `templates/databases/list.html` - Remove duplicate UI

### Low Priority
- `apps/core/branding/models.py` - Add deprecation warnings
- All files with TODO markers - Create issues

---

## Estimated Timeline

- **Week 1:** Critical cleanup (remove legacy view, add logging)
- **Week 2:** UI cleanup (remove duplicate dependency UI)
- **Week 3:** Code quality (TODOs → Issues, deprecation warnings)
- **Week 4:** Documentation and testing

**Total:** 3-4 weeks

---

## Success Criteria

- ✅ Zero legacy database creation usage
- ✅ Zero print() statements in production code
- ✅ Single dependency UI system
- ✅ All TODOs converted to tracked issues
- ✅ Proper logging throughout
- ✅ Documentation updated
- ✅ All tests passing

---

## Resources

- [Full Legacy Code Report](./LEGACY_CODE_REPORT.md) - Comprehensive analysis
- [Quick Start Guide](./QUICK_START_REFACTORING.md) - Step-by-step instructions
- [CLAUDE.md](../CLAUDE.md) - Project overview
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines

---

**Last Updated:** 2025-10-28
