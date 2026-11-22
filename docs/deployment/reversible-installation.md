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
- **sealed** with **health_verified_at**: installation passed its required
  service, database, Redis and control-panel port checks before success was
  recorded. Retrying the installer is a no-op. This is historical verification,
  not proof that services are still healthy now.
- **sealed** without **health_verified_at**: legacy completion was not
  health-verified, so retry requires diagnosis/repair rather than assuming
  success. The recorded state is preserved and cannot be overwritten.
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

## Self-healing install retries

The installer detects the following conditions when run from a source checkout
while /opt/webops exists:

| State | Automatic behavior |
| --- | --- |
| fresh | Stage a new installation with a private recovery marker |
| staged | Continue a copied, preflight-only installation |
| resume | Reuse the original captured pre-install baseline |
| installed | Exit successfully without reinstalling, only when prior health verification is recorded |
| repair | Refuse automatic replay after system changes started, health failed or legacy success lacked verification |
| manual/unsafe | Refuse untracked or foreign directories |

To diagnose the installation without changes, from the updated source checkout:

    cd ~/webops
    git pull --ff-only
    sudo ./provisioning/versions/v1.0.0/lifecycle/install.sh --doctor

After a harmless preflight interruption on a newly staged installation,
rerunning the installer automatically continues the existing staged copy.
No repository copy or user-data overwrite is attempted.

### Recover an older preflight-only copy

Older installations may have an ownership marker but no recovery journal.
The installer cannot establish that they were stopped before host changes.
It therefore requires an explicit operator-approved recovery:

    cd ~/webops
    git pull --ff-only
    sudo ./provisioning/versions/v1.0.0/lifecycle/install.sh --recover-staged

This is ONLY for copies you have verified were stopped before any host
modifications. The command checks the ownership marker, recorded inventory,
known WebOps services, system configuration, and deployment/data directories.
If eligible, it asks for the exact words RECOVER PREFLIGHT COPY, backs up
existing lifecycle scripts under /var/backups/webops-install, refreshes only
those scripts, and proceeds with existing configuration. It does not delete
the existing installation root, packages or database data.

This action is NOT a way to repair a partially applied OS installation.
Untracked system changes cannot be proven absent. Take a provider snapshot,
confirm out-of-band SSH access, and review installation logs first. A status of
repair, an existing deployment, or conflicting system modifications means a
manual repair plan is required. Do not delete /opt/webops/config.env, remove
/opt/webops, or falsify the private inventory to bypass safety checks.

## Installation success and retry acceptance

WebOps treats installation as successful only after platform setup exits
successfully and required service and connectivity checks pass. It checks
PostgreSQL and Redis service readiness/connectivity, core WebOps systemd units
(web, worker, beat, channels), and the control-panel listener on port 8000.
Only then is the inventory sealed with a health_verified_at timestamp.

A failed setup or health check exits nonzero and leaves the inventory
incomplete. When rerun, WebOps examines the previous inventory and staged
ownership state before making changes. A host that may already have been
modified is classified as repair; it is never silently reinstalled.
A pre-system-change interrupted install can safely resume using the recorded
baseline. A previously health-verified installation is recognized and skipped.

The check reports the state at installation time. It is not an ongoing uptime
monitor, and a complete disposable systemd-VM install/reboot/repair cycle
remains an outstanding release-validation requirement.

Run the isolated lifecycle contracts in Runpod or CI:

    python3 -m unittest discover -v -s provisioning/versions/v1.0.0/tests -p 'test_*.py'


## Fault injection, failure journaling and cleanup hardening

A 3,000+ case installation safety matrix tests independent combinations of
original files, post-install file types, later administrator changes, package
and service failures, symlink replacements, protected data directories,
malformed recovery history, and invalid installation locations.

Installed data directories are never deleted by an ordinary uninstall, even
if they are empty. Configuration restoration refuses symlinked ancestor
directories because those may redirect operations onto unrelated software.
Unsafe installation roots inside operating system paths such as /etc, /usr,
/proc and /var are rejected, even if a forged ownership marker is present.
Uninstall validates the fixed backup index for every tracked configuration
entry before any changes. The recovery classifier requires a timezone-aware,
parseable health verification timestamp, not simply a nonempty value.

If host modifications may have started and installation fails, WebOps does
not run a destructive whole-tree restore. That previously could erase
deployments or uploads created after the backup was taken. The install
failure remains recorded in the protected inventory (failure_reason,
failure_recorded_at), and the system requests operator-guided repair. A
safe preflight-only interruption can still use the original baseline to resume.

The full matrix runs automatically in the reversible-installation GitHub
Actions workflow, including the existing unittest contracts.

    python -m pip install pytest==9.2.0
    python -m pytest -q provisioning/versions/v1.0.0/tests

These tests use isolated temporary fake system roots and command shims.
They test real file operations and lifecycle logic but intentionally never
change the Runpod host's SSH/firewall/packages. A disposable systemd
virtual machine test remains required for evidence of real service recovery.
