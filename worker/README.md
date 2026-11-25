# WebOps build worker

A worker builds approved projects on a machine that is **not** the control panel, so repository code never runs next
to the panel's data. It connects out to the panel, claims one job at a time, builds it, and reports the log.

```
panel  <──HTTPS, bearer token──  worker   (the worker polls; nothing connects in)
```

## Install

On the worker machine, as root, one command (nothing to download first):

```bash
curl -fsSL https://raw.githubusercontent.com/DagiiM/webops/<ref>/worker/install.sh | WEBOPS_PANEL_URL=https://your-panel WEBOPS_REF=<ref> sh
```

or `WEBOPS_PANEL_URL=https://your-panel sh install.sh` from a checkout. The worker generates its own token (kept in
`/etc/webops-worker/token`, mode 0600) and prints one command containing only the token's **hash**; run it once on
the panel:

```bash
cd control-panel && python manage.py register_worker --name '<name>' --digest <hash>
```

The Workers page shows it **Online** within about 30 seconds. (The older flow still works: **Deployments → Workers →
Add a worker** shows a token once; put it in `/etc/webops-worker/token`.) Set `WEBOPS_WORKER_TOKEN` to supply your own
token, for machines that are rebuilt from scratch on every start.

## What a job gets

* Source: the exact commit, fetched by the panel with the requester's GitHub token (the token never leaves the panel).
* Commands: fixed per kind. Rust: `cargo build --release [--locked]`. Node: `npm ci|install --ignore-scripts`, then `npm run build` if defined.
  Python: `python3 -m venv .venv` and `pip install -r requirements.txt` (or `pip install .`). The panel cannot send a command line.
* Isolation (process level): its own throw-away unprivileged user and 0700 directory, privileges dropped before exec
  (no groups, `no_new_privs`, no capabilities), CPU / memory / file / process limits, a wall-clock limit, a disk cap,
  a minimal environment that never contains the worker token or panel address, and a sweep that kills every leftover
  process of that user. The directory and user are deleted afterwards.

## What it does not protect against

* **No network isolation.** Many container platforms (including Runpod pods) forbid user/network namespaces and cgroups,
  so a job can reach the internet and the worker's network neighbours. This is why the panel only schedules repositories
  owned by a trusted owner (the requester's own GitHub account, or owners in `WEBOPS_WORKER_TRUSTED_OWNERS`), and why the
  worker must hold nothing but the agent. Treat it as disposable.
* Memory is limited per process (address space), not as a group.
* It builds; it does not yet serve. A successful build leaves the deployment *stopped*.

## Tests

`python manage.py test apps.deployments.tests.test_worker_agent` includes hostile-command tests of the sandbox and a real
end-to-end job. They need root and `useradd`, and are skipped otherwise.
