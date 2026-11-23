# Grafana startup failure: isolated Runpod verification (2026-11-23)

## Scope and results

- Source: `DagiiM/webops`, v1.0.0 installer and monitoring addon.
- Disposable host: Ubuntu 24.04 Runpod CPU container, 2 vCPU, 10 GB root filesystem.
- **Real Grafana OSS 13.3.1** installed from the current signed Grafana APT repository.
- Executed WebOps' Grafana configuration function and started the real Grafana binary as the `grafana` service account, without mock HTTP or mock database.
- `GET http://127.0.0.1:3000/api/health`: **HTTP 200, database "ok"**.
- Re-running `configure_grafana` preserved the existing configuration's SHA256; admin credentials did not change.
- New isolated monitoring suite: 19 executable tests for slow readiness, failed service startup, HTTP 200 from unrelated software, unhealthy database, protected diagnostics, service-only recovery, credential stability and third-party configuration preservation.
- Staged recovery test suite: 8 tests exercising actual file copy and backup behavior.
- Early preflight test suite: 6 tests covering no ICMP, real HTTPS/DNS, booted systemd check and early safe failure.

## Real `make install` and `make deploy-install` attempts

1. **Real `make install`**, fresh: WebOps copied the repository's *unchanged tracked* `config.env` to `/opt/webops` despite its `WEBOPS_ROOT=/webops`. Its own validation rejected the copied config as existing host configuration. **Fixed:** only ignore exact unchanged bundled source config on a fresh install, never customized config.
2. **Real `make deploy-install`**, staged retry: refreshed lifecycle scripts and respected the staged ownership marker. It reached the interactive wizard and preflight. Preflight reported <20 GB disk (test Pod only has 10 GB) and erroneously reported no internet from a blocked/missing ICMP ping, although GitHub and Grafana HTTPS worked. **Fixed:** check actual HTTPS and DNS.
3. **Real `make install` after fixes:** successfully copied code, entered wizard, and reached preflight. HTTPS/DNS passed. It correctly rejected the container's 10 GB root and **absence of booted systemd** (PID 1 is `sleep`). The inventory remained `captured / baseline-captured` rather than the previous unsafe `system-changes-started`.
4. **Real `make deploy-install` retry:** detected existing inventory and **automatically resumed** from original pre-system-change state without asking for configuration again. It failed at the same true systemd/disk prerequisites; the inventory remained `captured / baseline-captured`, available for safe retry.

### Limitations (release blocking)

**A container whose PID 1 is `sleep` is not a booted systemd virtual machine.** It cannot exercise actual `systemctl start grafana-server`, the whole WebOps systemd stack, kernel/firewall changes or VM power-loss recovery. A full install to sealed/healthy state and live uninstall have **not** been demonstrated. The failure reported on the user's separate VPS cannot be diagnosed from a photo alone; its actual Grafana journal remains unavailable.

Do not advertise `make install` as fully verified on Ubuntu VPS until a separate booted systemd-based VM passes a complete clean install, forced failures, recovery and uninstall. The current tests confirm **real Grafana startup and HTTP**, **actual installer command dispatch**, **staged retry**, and **safe preflight refusal** only.

## Operator runbook for an affected installation

From a current trusted source checkout, use:

```bash
cd /root/webops
git pull --ff-only origin main
make monitoring-doctor     # read-only health check
make monitoring-repair     # starts ONLY grafana-server if needed
```

If Grafana remains unhealthy, the installer now keeps a private report under
`/var/log/webops/grafana-startup-*.log` (mode 0600). **Redact credentials
and private data before sharing that report.** The two manual direct diagnostics
are `sudo systemctl status grafana-server --no-pager -l` and
`sudo journalctl -u grafana-server -b -n 100 --no-pager`.

Do not delete the pre-install inventory, data directories or PostgreSQL/Redis
to work around the monitoring failure; an older interrupted system-change
install needs controlled recovery.

## Final Runpod regression summary

- v1 platform lifecycle/monitoring/staged recovery suite: **3,124 passed; 6 subtests passed** on the disposable Ubuntu 24.04 Runpod container (pytest 9.2.0).
- CLI regressions: **3,173 passed; 41 subtests passed; 100% statement coverage** over 5,083 measured statements.
- Shell syntax checks passed and the monitoring repair command was invoked against actual healthy Grafana with no config changes.
- The staged refresh now updates the audited install, monitoring, CLI and preflight scripts rather than leaving stale monitoring code in copied installations. This refresh is allowed only before host changes.

These tests are not evidence of a complete successful systemd WebOps deployment.
