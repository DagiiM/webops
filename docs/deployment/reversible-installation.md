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
The platform Bash CLI also supports the equivalent
sudo /opt/webops/provisioning/versions/v1.0.0/bin/webops uninstall platform --dry-run
and sudo /opt/webops/provisioning/versions/v1.0.0/bin/webops uninstall platform.
The normal addon uninstall command is unchanged.

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


## Installer says an existing config.env was found

An existing /opt/webops/config.env is not a reason to delete the file or
overwrite the install directory. It may contain passwords and server settings.

The updated installer recognizes a preconfigured source tree copied into a
**brand-new** install root. It keeps the source config byte-for-byte and
skips interactive hostname/SSH choices that would conflict with the config.
It also offers restricted --resume support when the verified installation
inventory proves that a pre-install baseline was captured and no host
modifications were started.

To inspect the state without changing anything, on the host run:

    sudo python3 /opt/webops/provisioning/versions/v1.0.0/lifecycle/installation_inventory.py inspect --state-dir /var/backups/webops-install/installation-inventory

Inventory states:
- **missing**: no verified before-state exists. Automatic retry/reinstall is
  intentionally blocked. Inspect logs, services and snapshots; do not delete
  config.env or rerun the installer with force.
- **captured**, **phase=baseline-captured**: it is possible to continue with:

      sudo /opt/webops/provisioning/versions/v1.0.0/lifecycle/install.sh --resume

  This reuses the original baseline and existing configuration. It does not
  recreate the inventory or prompt for new SSH settings.
- **captured**, **phase=system-changes-started**: host modifications may have
  occurred. An automatic replay is unsafe because some setup components are
  not transactionally idempotent. Use the independent rollback snapshots and
  the repair tooling after review.
- **sealed**: installation finished; use management or repair commands, not
  the installer again.
- **removed**: previous tracked install was uninstalled. Review the machine
  before any new install.

When the installed copy does not contain the inspect command, inspect the
inventory JSON's status and phase keys with a read-only JSON parser instead
of replacing the installation directory. Avoid displaying or sharing
config.env's contents because it can contain credentials.

If the original source checkout remains at ~/webops but /opt/webops already
exists, do not copy the checkout over /opt/webops. Operate on the installed
lifecycle script after reviewing the inventory state. An untracked legacy
setup cannot automatically be adopted as if it were a fresh installation.
