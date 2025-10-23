# **webops: A Highly Reliable, Mission-Critical Platform Foundation**  
*Version 1.0 — Designed for Zero Downtime, Full Observability, and Operator Sovereignty*

---

## 🎯 **Vision**

> **Provide a minimal, immutable, and composable base for deploying and operating mission-critical workloads—databases, Kubernetes, VMs—on bare metal or VMs, with built-in high availability, safe lifecycle management, and zero hidden dependencies.**

This is not a convenience tool. It is a **production contract**:  
> _“We give you a secure, auditable, and evolvable foundation. You own the configuration, the data, and the decisions.”_

---

## 🔑 **Core Tenets of High Reliability**

1. **No Single Point of Failure**  
   All critical services support multi-node HA (opt-in, explicit).
2. **Immutable Platform, Mutable State**  
   Code is versioned and replaced atomically; data and config are preserved.
3. **Safe Lifecycle Operations**  
   Install, update, rollback, and uninstall are **atomic, validated, and reversible**.
4. **Defense in Depth**  
   Hardened OS, least-privilege services, secrets isolation, firewall by default.
5. **Observability by Design**  
   Built-in health checks, metrics, and structured logging.
6. **Operator Control**  
   Nothing runs unless explicitly enabled. No auto-upgrades, no magic.
7. **Distro Agnosticism**  
   Runs identically on Ubuntu, Debian, Rocky, Alma—same workflow.
8. **Data Preservation First**  
   Uninstall never deletes data without explicit `--purge`.

---

## 🗂️ **Final Folder Structure**

```
/webops/
│
├── webops                          # CLI (symlink to .webops/current/bin/webops)
├── config.env                      # OPERATOR-OWNED: flat, declarative config (gitignored)
├── secrets/                        # OPERATOR-MANAGED: secrets (mode 600, gitignored)
│   └── *.secret
│
├── .webops/                        # PLATFORM-MANAGED (immutable)
│   ├── current → versions/v1.2.0   # Active version (atomic symlink)
│   └── versions/
│       └── v1.2.0/                 # Full, versioned snapshot
│           ├── bin/webops          # CLI implementation
│           ├── lib/                # Core logic
│           │   ├── common.sh       # Logging, config loader
│           │   ├── state.sh        # Tracks installed components
│           │   └── os.sh           # OS detection & validation
│           ├── os/                 # Distro-specific handlers
│           │   ├── common.sh
│           │   ├── ubuntu.sh
│           │   ├── debian.sh
│           │   └── rocky.sh
│           ├── setup/
│           │   ├── base.sh         # HA-ready OS hardening
│           │   └── validate.sh     # Pre-flight checks
│           └── addons/             # Workload add-ons
│               ├── postgresql.sh   # Standalone or HA (with Patroni)
│               ├── patroni.sh      # PostgreSQL HA (etcd-backed)
│               ├── etcd.sh         # Distributed coordination (HA)
│               ├── kubernetes.sh  # K3s HA control plane
│               ├── kvm.sh          # Hardware virtualization
│               └── monitoring.sh   # node_exporter + agent
│
├── templates/                      # OPERATOR OVERRIDE ZONE (optional)
│   ├── service-templates/          # Custom systemd/nginx configs
│   └── static/                     # Custom assets (500.html, certs)
│
└── LICENSE
```

> ✅ **Critical Boundaries**  
> - **Immutable**: `.webops/versions/` — never modified after install.  
> - **Mutable**: `config.env`, `secrets/`, `templates/` — fully owned by operator.  
> - **Atomic**: Version switch via symlink — zero partial states.

---

## 🧱 **Highly Reliable Base System (`setup/base.sh`)**

### What It Does
- **Time Sync**: `chrony` with multiple NTP sources (critical for distributed consensus).
- **SSH Hardening**: Key-only auth, no root login, `MaxAuthTries=2`.
- **Firewall**: `ufw` (Debian) or `firewalld` (RHEL) — deny all, allow SSH only.
- **Logging**: Persistent `journald` + `rsyslog` to `/var/log/webops/`.
- **Filesystem**: Ensures `noatime` on data partitions (performance + durability).
- **Kernel Tuning**: TCP keepalive, VM dirty ratios for database workloads.

### What It Never Does
- Installs Docker, Python, or language runtimes.
- Enables any workload.
- Modifies user data.

### OS Abstraction
- Auto-detects OS via `/etc/os-release`.
- Delegates to `os/<distro>.sh` for package manager, paths, and quirks.
- Supports override via `OS_OVERRIDE` in `config.env`.

---

## 🔌 **HA-Aware Add-Ons (`addons/*.sh`)**

Each add-on supports **three modes**:

| Mode | Use Case | Reliability Features |
|------|--------|----------------------|
| **Standalone** | Dev, non-critical | Idempotent install, backup hooks |
| **HA** | Production | Multi-node, automatic failover, quorum |
| **K8s-Native** | Cloud-native | Operator-managed, self-healing |

### Examples

#### 🗃️ **PostgreSQL**
- **Standalone**: Single instance, WAL archiving enabled.
- **HA**: Patroni + etcd cluster, synchronous replication, VIP failover.
- **Backup**: Daily `pg_dumpall` + WAL shipping (configurable).

#### ☸️ **Kubernetes**
- **HA**: K3s multi-server with embedded etcd or external DB.
- **Networking**: `--tls-san` for VIP, MetalLB for on-prem load balancing.
- **Storage**: Integrates with Longhorn or Ceph (via separate add-ons).

#### 💾 **etcd**
- **HA**: 3+ node cluster, TLS, snapshotting.
- **Monitoring**: Exposes `/metrics` for Prometheus.

#### 🖥️ **KVM**
- **Live Migration**: Shared storage assumed (NFS, Ceph).
- **Resource Isolation**: CPU pinning, huge pages.

> ✅ **All add-ons are disabled by default** (`*_ENABLED=false`).

---

## 📄 **Configuration: `config.env`**

Flat, POSIX-compliant, human-readable:

```ini
# Base
TIMEZONE=UTC
ENABLE_FIREWALL=true

# PostgreSQL HA
POSTGRES_ENABLED=true
PATRONI_ENABLED=true
PATRONI_CLUSTER_NAME=prod-pg
PATRONI_VIP=10.10.10.100
ETCD_ENDPOINTS=http://node1:2379,http://node2:2379,http://node3:2379
POSTGRES_SUPERUSER_PASSWORD_FILE=/webops/secrets/pg_su.secret
```

### Rules
- **No nesting, no YAML** — parseable with `grep` or `envsubst`.
- **Secrets are file paths only** — never values.
- **All keys uppercase** — avoids shell conflicts.

---

## 🔄 **Lifecycle Management**

### ✅ **Install**
```bash
webops install          # base + enabled add-ons
webops apply postgresql # single add-on
```

### 🔄 **Update**
```bash
webops update --from-github v2.1.0
```
1. Downloads to `.webops/versions/v2.1.0/`
2. Runs new `validate.sh`
3. Atomic symlink switch
4. Re-applies base + add-ons (idempotent)
5. Verifies service health

### ↩️ **Rollback**
```bash
webops rollback v2.0.0  # flips symlink + re-applies in <5s
```

### 🧹 **Uninstall**
```bash
webops uninstall postgresql        # stops service, keeps data
webops uninstall postgresql --purge  # deletes data (explicit)
```
- **Blocks** if dependents exist (e.g., can’t remove etcd if Patroni is active).
- **Never deletes data** without `--purge`.
- **Idempotent** — safe to re-run.

---

## 🛡️ **Security & Compliance**

| Layer | Enforcement |
|------|-------------|
| **Secrets** | Stored in `/webops/secrets/` (mode 600), referenced by path |
| **Network** | Firewall denies all by default; add-ons request ports |
| **Execution** | Services drop privileges; scripts use `sudo` only when needed |
| **Integrity** | Official packages only (PostgreSQL APT, K3s official script) |
| **Audit** | All actions logged to `/var/log/webops/`; config versioned by operator |

---

## 👁️ **Observability**

### Built-In
- **Health Checks**: Patroni `/health`, K3s `/readyz`
- **Metrics**: `node_exporter` (CPU, mem, disk, network)
- **Logging**: Structured logs in `/var/log/webops/`

### Integration
- Add-ons auto-register with Prometheus if `monitoring` is enabled.
- Example alert: `Patroni leader change`, `etcd leader loss`.

---

## 🌐 **Supported Environments**

| OS | Versions | Init | Package Manager |
|----|--------|------|------------------|
| Ubuntu | 20.04, 22.04, 24.04 | systemd | apt |
| Debian | 11, 12 | systemd | apt |
| Rocky Linux | 8, 9 | systemd | dnf |
| AlmaLinux | 8, 9 | systemd | dnf |

> Add new OS by implementing `os/<name>.sh`.

---

## 🚀 **Operator Workflow**

### Bootstrap a 3-Node HA PostgreSQL Cluster
1. On all nodes:
   ```bash
   git clone https://github.com/DagiiM/webops.git /webops
   cd /webops
   cp config.env.example config.env
   echo "mypass" | sudo tee secrets/pg_su.secret && sudo chmod 600 secrets/pg_su.secret
   ```
2. Edit `config.env`:
   ```ini
   ETCD_ENABLED=true
   POSTGRES_ENABLED=true
   PATRONI_ENABLED=true
   PATRONI_VIP=192.168.10.100
   ETCD_ENDPOINTS=http://node1:2379,http://node2:2379,http://node3:2379
   ```
3. Run:
   ```bash
   sudo ./webops install
   ```

### Update Safely
```bash
sudo ./webops update --from-github v2.1.0  # validated, atomic, reversible
```

### Decommission Node
```bash
sudo ./webops uninstall patroni
sudo ./webops uninstall postgresql
sudo ./webops uninstall etcd
# Data preserved for forensic analysis
```

---

## 📜 **CLI: `webops`**

```bash
Usage: webops <command> [options]

Commands:
  install     → Run base + enabled add-ons
  apply <addon> → Install/update a single add-on
  uninstall <addon> [--purge] → Remove service (keep data unless --purge)
  validate    → Pre-flight check
  update      → Update platform version
  rollback    → Revert to previous version
  version     → Show current version
```

---

## ✅ **Why This Is Highly Reliable**

- **No hidden state**: Everything is explicit in `config.env`.
- **No upgrade risk**: Rollback is seconds away.
- **No data loss**: Uninstall preserves data by default.
- **No single point of failure**: HA modes are production-ready.
- **No magic**: Every line of shell is readable, auditable, and testable.

---

## Migration from Legacy Setup

For users migrating from the legacy `setup.sh` script:

### Quick Migration (Recommended)

```bash
# Download and run migration script
wget https://raw.githubusercontent.com/DagiiM/webops/main/migrate-to-v1.sh
sudo chmod +x migrate-to-v1.sh
sudo ./migrate-to-v1.sh
```

### Migration Options

```bash
# Interactive migration (default)
sudo ./migrate-to-v1.sh

# Non-interactive migration
sudo ./migrate-to-v1.sh --force

# Dry run (test without changes)
sudo ./migrate-to-v1.sh --dry-run

# With automatic rollback
sudo ./migrate-to-v1.sh --auto-rollback

# Rollback previous migration
sudo ./migrate-to-v1.sh --rollback

# Check migration status
sudo ./migrate-to-v1.sh --status
```

### Migration Safety Features

1. **Automatic Backup**: Creates timestamped backup before migration
2. **Validation Checks**: Pre-migration system validation
3. **Dry Run Mode**: Test migration without making changes
4. **Rollback Support**: Automatic rollback on failure or manual rollback
5. **Progress Tracking**: Real-time migration progress and logging
6. **Service Continuity**: Minimizes downtime during migration

### Manual Migration Steps

If you prefer manual migration:

1. **Pre-migration Assessment**
   - Document current configuration
   - Note custom modifications
   - Check service dependencies
   - Verify backups are current

2. **Migration Execution**
   - Stop legacy services
   - Install new version
   - Migrate data and configuration
   - Start new services

3. **Post-migration**
   - Remove legacy files
   - Update monitoring
   - Document changes
   - Train operators

See `MIGRATION_GUIDE.md` for detailed manual migration instructions.

---

## 🏁 **Conclusion**

**webops** is not a script collection. It is a **production-grade platform contract** that delivers:

- ✅ **High Availability** (opt-in, explicit, tested)  
- ✅ **Safe Evolution** (atomic updates, instant rollback)  
- ✅ **Data Integrity** (uninstall never deletes without consent)  
- ✅ **Operator Sovereignty** (you own the config, the data, the destiny)  

This is how you build infrastructure that survives **decades**, not just deprecations.

---

> **Next Step**: Would you like this as a **GitHub repository template**, a **runbook for production rollout**, or a **compliance checklist (SOC2, ISO 27001)**?