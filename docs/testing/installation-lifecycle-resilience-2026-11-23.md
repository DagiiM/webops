# WebOps installation lifecycle resilience campaign — 23 November 2026

## Purpose

Test success reporting, safe retries after interruption, system configuration
restoration, and uninstall preservation with a deterministic fault matrix far
beyond the requested 1,000-case goal.

## Environment and execution

- Repository: DagiiM/webops, main
- Runpod: isolated Pod pakpefj1ikfld0, CPU3 compute optimized, 2 vCPU,
  Debian-based Python 3.11 container
- Test runner: pytest 9.2.0; temporary directories as fake system roots;
  command shims for systemctl, Redis, PostgreSQL, and network listeners
- Command: python -m pytest -q provisioning/versions/v1.0.0/tests/
- Result: **3,067 passed, zero failed**, approximately 28 seconds
- Existing CLI regression: **3,173 passed, 41 subtests passed**, and
  **100.00% statement coverage** (5,083 measured statements)

## Distinct test families

| Test category | Parametrized cases |
| --- | ---: |
| Configuration before/after/operator changes (30×4×4×4) | 1,920 |
| Protected data directories and optional purge (14×8×2) | 224 |
| Corrupted original backups (24×4) | 96 |
| Recovery classification with unrelated host edits (11×8) | 88 |
| Dangerous relative tracked paths | 40 |
| Symlinked ancestor substitutions (16×2×3) | 96 |
| Prohibited system installation roots | 33 |
| Forged backup indices in journals (28×5) | 140 |
| Ownership-marker variations and invalid bytes (7×3+3) | 24 |
| Failure-stage/type journal preservation (16×8×2) | 256 |
| Invalid failure-journal transitions (3×3) | 9 |
| Destructive rollback protection | 1 |
| Malformed installation journals | 37 |
| Invalid health-success timestamps | 18 |
| **Parametrized resilience matrix subtotal** | **2,982** |
| Earlier executable lifecycle and uninstall contracts | 85 |
| **Total** | **3,067** |

All cases have reproducible pytest node IDs and independent temporary
filesystems. These are distinct parameterized scenarios, not subtest-count
inflation or repeated identical assertions.

## Defects discovered and corrected

1. **Empty data directories deleted on normal uninstall:** generic rmdir
   cleanup ignored the protected-directory allowlist when data directories
   were empty. These are now preserved unless explicitly purged.
2. **Symlink-parent escape from system configuration:** replacing a tracked
   /etc parent directory with a link to unrelated software could cause
   uninstall to delete matching external files. Cleanup now skips targets
   below symlinked system ancestors.
3. **Destructive failure rollback:** automatically restoring a historical
   entire installation tree could erase data written after the snapshot.
   Rollback now fails closed, keeping data and evidence for manual recovery.
4. **Overly broad installation-root paths:** unsafe roots within /etc, /var,
   /proc, /usr, /sys and other system directories are now refused.
5. **Untrusted journal data:** malformed fields, forged backup indices, and
   Python boolean/int equality could bypass intended schema validation.
   These are validated before any mutation.
6. **Ownership-marker ambiguity:** arbitrary/symlinked ownership markers
   no longer prove a tree belongs to WebOps.
7. **Unverifiable installation success:** a nonempty but malformed
   health_verified_at value no longer qualifies as successful history.
8. **Unreported installation failures:** a controlled exit trap now records
   failure_reason and failure_recorded_at for tracked incomplete installs.

## CI policy

The reversible-installation.yml GitHub Actions workflow now installs a
pinned pytest runner and executes all lifecycle and resilience cases
on relevant pushes to main and pull requests.

## Limitations

The container is not a systemd-booted VPS. Test commands are shimmed
or confined to temporary directories. The campaign does not manipulate
host SSH, production firewall settings, real package managers, or live
PostgreSQL. A full disposable-VM install, reboot, forced interruption,
repair and uninstall campaign is still required for production-wide
restoration guarantees.

Passing this matrix greatly reduces regression risk but is not proof of
zero vulnerabilities on arbitrary operating systems.
