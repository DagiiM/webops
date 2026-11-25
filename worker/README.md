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

## Persistent volumes (a worker that survives stops)

A pod's own disk is wiped on every stop or restart, so a worker normally has to be reinstalled. To have it rebuild
itself, mount a small network volume and give the pod these environment variables and this start command:

```bash
# environment
WEBOPS_PANEL_URL=https://<panel address>   WEBOPS_WORKER_NAME=<name>   WEBOPS_WORKER_STATE=/workspace/webops-worker   WEBOPS_REF=<ref>
# start command
sh -c 'curl -fsSL https://raw.githubusercontent.com/DagiiM/webops/${WEBOPS_REF}/worker/install.sh | sh; exec sleep infinity'
```

The first start installs everything (a couple of minutes) and prints the one `register_worker` command. Every later
start restores the same token and comes back Online with nothing to do.

**What is, and is not, kept on the volume, and why.** A network volume does **not** enforce file permissions: any user on
the machine can read (and write) any file on it, and build jobs run as unprivileged users on the same machine as the
agent. So the volume holds only the worker token, **encrypted** with a key derived from `RUNPOD_API_KEY`, which Runpod
puts in the environment of the container's root process and which jobs never receive. The plaintext token lives only on
the container's own disk (root, mode 0600). Job directories, the Rust toolchain and the agent also stay on the container
disk: anything on the volume could be read or tampered with by a build, which would let one job poison the next.
The price is a minute or two of reinstalling packages on each start. If the pod's key ever changes, the worker makes a
new token and prints a new `register_worker` command instead of failing silently.

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
