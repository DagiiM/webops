# Remote build workers

Executable builds never run on the panel's own host. When the host's workload policy is restricted, an approved
request for a project that runs code is queued for a **worker**: a separate machine running `worker/webops_worker.py`.

## Flow

1. A request for a non-static project is saved and safety-reviewed as before.
2. An operator approves it. The panel checks that a worker is online, that the repository owner is trusted, that the
   project is a supported kind (Rust, Node, Python) and pins the branch to an exact commit. Failing any check, the
   request stays put with the reason.
3. The job is queued. A worker claims it, downloads the source through the panel, builds it in a per-job sandbox and
   streams the log back. The deployment shows *building*, then *stopped* (built) or *failed*.
4. Leases protect against lost workers: a job a worker stops reporting on is re-queued, up to three attempts.

## Trust model

* The worker token is hashed at rest, shown once, revocable, and valid only for `/api/worker/v1/`.
* Jobs carry a *kind*, never a command. The agent owns the command catalog and clamps resource limits to its own ceilings.
* The requester's GitHub token stays on the panel; the worker receives a signed archive stream for one job.
* Only repositories from trusted owners run: the requester's connected GitHub account plus `WEBOPS_WORKER_TRUSTED_OWNERS`
  (comma separated). This is because worker isolation is process-level, with no network isolation.

## Operating it

Deployments → Workers lists workers, their last contact, recent jobs and logs. Revoke a worker to invalidate its token
and re-queue anything it held. Cancel a job to return the request to the operator.

## Not yet

Serving applications from a worker, databases reachable from a worker (managed databases are local to the panel host),
and stronger isolation (microVMs or containers on a host that allows them).
