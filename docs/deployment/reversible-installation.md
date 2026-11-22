# Reversible WebOps installation and safe uninstall

New WebOps v1 installations made with the updated installer maintain a
root-owned, private inventory of the system before and after installation.
This enables guarded cleanup, not a guarantee of byte-for-byte machine
restoration.

## Installation safeguards

* Fresh installation refuses to overwrite an existing install root or
  existing WebOps configuration. Use the separate update/repair path.
* Before changing hostname, SSH, firewall, packages and services, the installer
  records original managed files/directories, service status, hostname,
  firewall status and OS package baseline.
* Installed state and WebOps-owned files are recorded after successful setup.
  Inventory lives in
  /var/backups/webops-install/installation-inventory/inventory.json
  with root-only permissions, outside the project directory.
* An incomplete/missing inventory blocks automated removal. Failed installs
  may need recovery using /var/backups/webops-install/ snapshots.

## Uninstall

Use the platform lifecycle script, not the Python CLI addon subcommand.

    sudo /opt/webops/provisioning/versions/v1.0.0/lifecycle/uninstall.sh --dry-run
    sudo /opt/webops/provisioning/versions/v1.0.0/lifecycle/uninstall.sh

The preview does not modify the system. The normal command requests the exact
word UNINSTALL. The tool restores allowlisted configuration only if it still
matches the recorded installed state, removes unchanged files in a proven
WebOps-owned installation root, and keeps databases, deployments, logs,
backups, media and other user-data directories.

Files changed after installation and untracked files are preserved.

To additionally delete managed data, use:

    sudo /opt/webops/provisioning/versions/v1.0.0/lifecycle/uninstall.sh --purge-data

This requires the phrase PURGE WEBOPS DATA. Unattended purging requires
--purge-data --force --confirm-purge together, plus proven root ownership.
Untracked files in the root are never deleted.

## Limits and operator checks

* Shared OS packages are deliberately retained to avoid disrupting unrelated
  applications. The installed package difference is reported. No blanket apt,
  dnf or autoremove is performed.
* Files outside the tracked allowlist, third-party addon changes, system users,
  some runtime settings, and cloud resources need manual review. Exact
  whole-machine restoration is not guaranteed.
* Independently verify SSH and firewall connectivity after removal. Conflicting
  later edits are left untouched. Runtime commands that fail are reported.
* Older installs without a trusted inventory fail closed and require manual
  migration/recovery.
* Take a provider-level snapshot and ensure out-of-band SSH access before
  running a production uninstall.

## Verification

    python3 -m unittest discover -v -s provisioning/versions/v1.0.0/tests -p test_install_uninstall.py
    bash -n provisioning/versions/v1.0.0/lifecycle/install.sh
    bash -n provisioning/versions/v1.0.0/lifecycle/uninstall.sh

Isolated tests cover restoration, conflict preservation, legacy refusal,
preview, backup corruption, initial system settings, user data, opt-in purge,
symlinks, package retention and repeat uninstall rejection. Disposable full-VM
Ubuntu and RHEL integration tests remain necessary before a production-wide
exact rollback claim.
