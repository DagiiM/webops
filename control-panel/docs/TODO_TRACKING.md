# TODO Tracking Document

**Created:** 2025-10-28
**Status:** Phase 3 - Code Quality Cleanup
**Total Items:** 20

---

## Overview

This document tracks all TODO/FIXME markers in the WebOps codebase, categorized by priority and area. Each item should be converted to a GitHub issue for proper tracking.

---

## Summary Statistics

| Category | Count | Priority Distribution |
|----------|-------|----------------------|
| KVM Addon | 11 | P2: 8, P3: 3 |
| Deployment System | 4 | P2: 3, P3: 1 |
| Database Management | 1 | P3: 1 |
| Compliance/Security | 1 | P3: 1 |
| Notifications | 1 | P2: 1 |
| Code Formatting | 3 | P4: 3 (not real TODOs) |

**Priority Legend:**
- **P1 (Critical):** Blocks core functionality - 0 items
- **P2 (High):** Important features, should implement soon - 12 items
- **P3 (Medium):** Nice to have, not blocking - 5 items
- **P4 (Low):** Documentation/formatting only - 3 items

---

## Priority 2 (High) - 12 Items

### KVM Addon - Virtualization Features

#### 1. Backup Restoration
**File:** `addons/kvm/backup.py:318`
```python
# TODO: Implement full restoration
```

**Description:** Backup creation is implemented, but full restore functionality is missing.

**Impact:** Users can create backups but cannot restore VMs from them.

**Suggested Issue Title:** `[KVM] Implement full VM restoration from backups`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`

**Estimated Effort:** 1-2 days

**Acceptance Criteria:**
- [ ] Restore VM from backup file
- [ ] Verify restored VM configuration
- [ ] Handle disk restoration
- [ ] Update VM metadata after restore
- [ ] Add restore progress tracking

---

#### 2. Libvirt Snapshot Cleanup
**File:** `addons/kvm/backup.py:366`
```python
# TODO: Delete libvirt snapshot
```

**Description:** Snapshots are created but not properly cleaned up after backup.

**Impact:** Disk space accumulation from orphaned snapshots.

**Suggested Issue Title:** `[KVM] Implement libvirt snapshot cleanup after backup`

**Labels:** `bug`, `kvm-addon`, `P2-high`

**Estimated Effort:** 4 hours

**Acceptance Criteria:**
- [ ] Delete libvirt snapshot after successful backup
- [ ] Handle cleanup on backup failure
- [ ] Add error logging for failed deletions
- [ ] Verify no orphaned snapshots remain

---

#### 3. Migration Rollback
**File:** `addons/kvm/migration.py:139`
```python
# TODO: Rollback on failure
```

**Description:** VM migration doesn't have rollback mechanism on failure.

**Impact:** Failed migration could leave VM in inconsistent state.

**Suggested Issue Title:** `[KVM] Add rollback mechanism for failed VM migrations`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`, `reliability`

**Estimated Effort:** 1 day

**Acceptance Criteria:**
- [ ] Detect migration failures
- [ ] Restore original VM state
- [ ] Clean up partial migration artifacts
- [ ] Log rollback actions
- [ ] Notify user of rollback

---

#### 4. Migration Connectivity Check
**File:** `addons/kvm/migration.py:271`
```python
# TODO: Add actual connectivity check
```

**Description:** Migration proceeds without verifying target host connectivity.

**Impact:** Migrations can fail late in process, wasting time/resources.

**Suggested Issue Title:** `[KVM] Add pre-migration connectivity validation`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`

**Estimated Effort:** 4 hours

**Acceptance Criteria:**
- [ ] Ping target host before migration
- [ ] Verify SSH access to target
- [ ] Check target resources (CPU, RAM, disk)
- [ ] Validate network configuration
- [ ] Display clear error if checks fail

---

#### 5. SSH Tunnel for Remote VMs
**File:** `addons/kvm/vnc_proxy.py:123`
```python
# TODO: Implement SSH tunnel for remote VMs
```

**Description:** VNC proxy only works for local VMs, not remote hosts.

**Impact:** Cannot access VMs on remote hypervisors via VNC.

**Suggested Issue Title:** `[KVM] Add SSH tunnel support for remote VM VNC access`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`, `networking`

**Estimated Effort:** 2 days

**Acceptance Criteria:**
- [ ] Create SSH tunnel to remote host
- [ ] Forward VNC port through tunnel
- [ ] Handle SSH authentication (keys, passwords)
- [ ] Clean up tunnels on disconnect
- [ ] Add tunnel status monitoring

---

#### 6. Shared VNC Access
**File:** `addons/kvm/vnc_proxy.py:177`
```python
# TODO: Add shared access / team permissions
```

**Description:** VNC access is single-user only, no team collaboration.

**Impact:** Teams cannot share VM console access.

**Suggested Issue Title:** `[KVM] Implement shared VNC access with team permissions`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`, `auth`

**Estimated Effort:** 1-2 days

**Acceptance Criteria:**
- [ ] Allow multiple concurrent VNC connections
- [ ] Add permission levels (view-only, control)
- [ ] Integrate with team/user management
- [ ] Show who is currently connected
- [ ] Add session expiration

---

#### 7. PayPal Payment Integration
**File:** `addons/kvm/billing.py:282`
```python
# TODO: Implement PayPal integration
```

**Description:** Only Stripe payment is implemented, no PayPal option.

**Impact:** Users who prefer PayPal cannot use billing features.

**Suggested Issue Title:** `[KVM] Add PayPal payment integration`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`, `billing`

**Estimated Effort:** 2-3 days

**Acceptance Criteria:**
- [ ] Integrate PayPal SDK
- [ ] Add PayPal payment flow
- [ ] Handle webhooks for payment confirmation
- [ ] Store PayPal transaction IDs
- [ ] Add refund support
- [ ] Test in sandbox environment

---

#### 8. Network Configuration (ifcfg)
**File:** `addons/kvm/bridge_networking.py:363`
```python
# TODO: Implement ifcfg configuration
```

**Description:** Only supports certain network configuration methods.

**Impact:** Some Linux distributions use ifcfg format, currently unsupported.

**Suggested Issue Title:** `[KVM] Add ifcfg network configuration support`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`, `networking`

**Estimated Effort:** 1 day

**Acceptance Criteria:**
- [ ] Detect if system uses ifcfg
- [ ] Generate ifcfg configuration files
- [ ] Apply network configuration
- [ ] Handle RHEL/CentOS variants
- [ ] Test bridge creation with ifcfg

---

### Deployment System

#### 9. Service Restart Logic
**File:** `apps/deployments/tasks/application.py:95`
```python
# TODO: Implement service restart logic (Phase 2.5)
```

**Description:** Service restart functionality is incomplete.

**Impact:** Cannot programmatically restart application deployments.

**Suggested Issue Title:** `[Deployments] Implement service restart functionality`

**Labels:** `enhancement`, `deployments`, `P2-high`

**Estimated Effort:** 1 day

**Acceptance Criteria:**
- [ ] Graceful service restart
- [ ] Zero-downtime restart if possible
- [ ] Update service status during restart
- [ ] Log restart actions
- [ ] Handle restart failures
- [ ] Add restart cooldown period

---

#### 10. Service Stop Logic
**File:** `apps/deployments/tasks/application.py:140`
```python
# TODO: Implement service stop logic (Phase 2.5)
```

**Description:** Service stop functionality is incomplete.

**Impact:** Cannot properly stop application deployments.

**Suggested Issue Title:** `[Deployments] Implement service stop functionality`

**Labels:** `enhancement`, `deployments`, `P2-high`

**Estimated Effort:** 4-8 hours

**Acceptance Criteria:**
- [ ] Graceful service shutdown
- [ ] Send SIGTERM then SIGKILL if needed
- [ ] Update service status to stopped
- [ ] Clean up PID files
- [ ] Log stop actions
- [ ] Handle stop failures

---

### Notifications

#### 11. Email/Slack Notifications
**File:** `apps/deployments/shared/monitoring.py:214`
```python
# TODO: Implement email/Slack notifications
```

**Description:** Monitoring system doesn't send notifications.

**Impact:** Users aren't alerted about deployment issues.

**Suggested Issue Title:** `[Monitoring] Add email and Slack notification support`

**Labels:** `enhancement`, `monitoring`, `P2-high`, `notifications`

**Estimated Effort:** 1-2 days

**Acceptance Criteria:**
- [ ] Email notifications for critical events
- [ ] Slack webhook integration
- [ ] Configurable notification rules
- [ ] Template-based messages
- [ ] Rate limiting to avoid spam
- [ ] Test notification functionality

---

### KVM Addon - Monitoring

#### 12. Actual Uptime Calculation
**File:** `addons/kvm/tasks.py:51`
```python
# TODO: Get actual uptime from libvirt
```

**Description:** VM uptime is not accurately tracked from libvirt.

**Impact:** Incorrect uptime reporting in dashboard.

**Suggested Issue Title:** `[KVM] Get accurate VM uptime from libvirt API`

**Labels:** `enhancement`, `kvm-addon`, `P2-high`, `monitoring`

**Estimated Effort:** 4 hours

**Acceptance Criteria:**
- [ ] Query libvirt for VM uptime
- [ ] Parse and format uptime data
- [ ] Display in human-readable format
- [ ] Handle VM state changes
- [ ] Cache uptime data appropriately

---

## Priority 3 (Medium) - 5 Items

### KVM Addon

#### 13. VM Auto-Delete Decision
**File:** `addons/kvm/tasks.py:156`
```python
# TODO: Decide whether to auto-delete or just log
```

**Description:** Unclear behavior for handling failed VM operations.

**Impact:** May leave orphaned resources or accidentally delete VMs.

**Suggested Issue Title:** `[KVM] Define VM cleanup policy for failed operations`

**Labels:** `discussion`, `kvm-addon`, `P3-medium`

**Estimated Effort:** 2 hours (discussion + implementation)

**Acceptance Criteria:**
- [ ] Document cleanup policy
- [ ] Implement chosen strategy
- [ ] Add configuration option
- [ ] Log all cleanup actions
- [ ] Add manual cleanup command

---

#### 14. Actual Disk Size Calculation
**File:** `addons/kvm/deployment_service.py:324`
```python
disk_size_mb=0,  # TODO: Calculate actual size
```

**Description:** VM disk size is not calculated, hardcoded to 0.

**Impact:** Inaccurate storage usage reporting.

**Suggested Issue Title:** `[KVM] Calculate actual VM disk sizes`

**Labels:** `enhancement`, `kvm-addon`, `P3-medium`

**Estimated Effort:** 4 hours

**Acceptance Criteria:**
- [ ] Query disk file size from filesystem
- [ ] Get virtual size from qcow2 metadata
- [ ] Calculate and display both sizes
- [ ] Update on disk resize
- [ ] Show in dashboard

---

### Deployment System

#### 15. Celery Service Detection
**File:** `apps/deployments/views/application_deployment.py:34`
```python
# TODO: Implement proper Celery service detection if needed
```

**Description:** Celery task queue detection is incomplete.

**Impact:** May not detect if Celery is running for background tasks.

**Suggested Issue Title:** `[Deployments] Improve Celery service detection`

**Labels:** `enhancement`, `deployments`, `P3-medium`

**Estimated Effort:** 4 hours

**Acceptance Criteria:**
- [ ] Check if Celery worker is running
- [ ] Verify Celery beat if needed
- [ ] Display Celery status in UI
- [ ] Handle Celery connection failures
- [ ] Add Celery health check endpoint

---

### Database Management

#### 16. User Cleanup on Database Deletion
**File:** `apps/databases/services.py:204`
```python
# TODO: Clean up user
```

**Description:** Database user is not cleaned up when database is deleted.

**Impact:** Orphaned database users accumulate over time.

**Suggested Issue Title:** `[Databases] Clean up database users on deletion`

**Labels:** `bug`, `databases`, `P3-medium`

**Estimated Effort:** 2 hours

**Acceptance Criteria:**
- [ ] Delete database user when deleting database
- [ ] Handle case where user is shared
- [ ] Log user deletion
- [ ] Add option to keep user
- [ ] Handle deletion failures gracefully

---

### Compliance

#### 17. Security Scan Execution
**File:** `apps/compliance/views.py:417`
```python
# TODO: Implement actual scan execution
```

**Description:** Compliance scanning UI exists but execution is not implemented.

**Impact:** Security compliance features are incomplete.

**Suggested Issue Title:** `[Compliance] Implement security scan execution`

**Labels:** `enhancement`, `compliance`, `P3-medium`, `security`

**Estimated Effort:** 2-3 days

**Acceptance Criteria:**
- [ ] Integrate security scanning tool (e.g., OpenVAS, Lynis)
- [ ] Execute scans on schedule
- [ ] Parse and store scan results
- [ ] Display results in UI
- [ ] Generate compliance reports
- [ ] Add scan history tracking

---

## Priority 4 (Low) - 3 Items (Not Real TODOs)

### Code Formatting Comments

#### 18. Format TOTP Code Display
**File:** `apps/core/auth/services.py:247`
```python
# Format as XXXX-XXXX
```

**Type:** Code comment, not a TODO

**Action:** Leave as-is (documentation comment)

---

#### 19. Format TOTP Code Display (Duplicate)
**File:** `apps/core/services/auth_service.py:247`
```python
# Format as XXXX-XXXX
```

**Type:** Code comment, not a TODO

**Action:** Leave as-is (documentation comment)

---

#### 20. Format TOTP Code Display (Duplicate 2)
**File:** `apps/core/services/security_services.py:294`
```python
# Format as XXXX-XXXX
```

**Type:** Code comment, not a TODO

**Action:** Leave as-is (documentation comment)

---

## Implementation Plan

### Phase 3A: Documentation & Tracking (Current)
- [x] Extract all TODO markers
- [x] Categorize by priority and area
- [x] Create detailed tracking document
- [ ] Replace TODO comments with issue references
- [ ] Create GitHub issue templates

### Phase 3B: Quick Wins (Optional)
Items that can be done quickly (< 4 hours):
1. Libvirt snapshot cleanup (#2)
2. Migration connectivity check (#4)
3. Actual uptime from libvirt (#12)
4. User cleanup on database deletion (#16)

### Phase 3C: Future Sprints
Larger items to schedule in future development:
1. Full backup restoration (#1)
2. Migration rollback (#3)
3. SSH tunnel for VNC (#5)
4. Shared VNC access (#6)
5. PayPal integration (#7)
6. Service restart/stop logic (#9, #10)
7. Email/Slack notifications (#11)
8. Security scan execution (#17)

---

## Conversion Template

When creating GitHub issues, use this template:

```markdown
## Description
[Brief description from TODO comment]

## Current Behavior
[What currently happens]

## Expected Behavior
[What should happen after implementation]

## Impact
[How this affects users/system]

## Location
File: `path/to/file.py:line`

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests added
- [ ] Documentation updated

## Estimated Effort
[Time estimate]

## Priority
P2-high / P3-medium / etc.

## Labels
enhancement, [area], [priority]

## Related Issues
[Link any related issues]
```

---

## Notes

1. **Not Converting Yet:** We're documenting TODOs first, will create GitHub issues in future sprint
2. **KVM Addon:** Most TODOs (11/20) are in optional KVM addon, not blocking core functionality
3. **Formatting Comments:** 3 items marked "Format as XXXX-XXXX" are code comments, not actual TODOs
4. **Priority 2 Items:** Should be addressed in next 1-2 months
5. **Priority 3 Items:** Can be addressed when resources available

---

## Maintenance

This document should be updated when:
- New TODOs are added to codebase
- GitHub issues are created (add issue numbers)
- TODOs are resolved (mark as complete)
- Priorities change

**Last Updated:** 2025-10-28
**Next Review:** After Phase 3 completion
