# Control-plane recovery runbook

The SQLite preview has two independent databases: the Django control-plane database and the durable job queue. The new management command uses SQLite's online backup API, records SHA-256 checksums and sizes, and verifies SQLite integrity. Snapshot directories are private (0700), database files are 0600. Checksums detect accidental corruption; they are not a substitute for authenticated/encrypted storage.

Run as the WebOps service account using the deployed settings:

    python manage.py backup_control_plane create --destination /private/recovery/snapshots
    python manage.py backup_control_plane verify /private/recovery/snapshots/snapshot-ID
    python manage.py backup_control_plane restore-stage /private/recovery/snapshots/snapshot-ID --destination /private/recovery/staging

The destination parent must be private and should be on a separate durable filesystem. Use a maintenance window with web writes and the worker stopped for consistent cross-database capture. Online snapshots are individually consistent, not a single atomic transaction across both databases.

Restore-stage creates a new directory and never overwrites the running database. All pending/started queue jobs in the restored copy are marked failed and the old worker heartbeat is removed. Reconcile deployment records against real processes/provider resources before accepting new work. Do not automatically replay interrupted tasks.

## Full disaster recovery remains a release gate

These snapshots include only the two SQLite databases. They may contain sensitive records: never publish or commit them. Store encrypted copies off-host with access controls, retention and versioning. Separately protect the matching application encryption key, Django secret, deployment data, model assets, runtime configuration and provider assignments. A snapshot on the same ephemeral pod is not disaster recovery. Restore those assets and configuration on a replacement host, verify the exact application revision and migration compatibility, run Django checks and reconcile all workload state before directing traffic to the replacement. Test recovery from actual pod deletion before declaring this gate passed.

Current verification: four automated recovery tests (restore, quarantine, tamper detection, private permissions and symlink rejection) and a real online backup/staged restore of the running pod. No live files were replaced. Full cross-host recovery, durable volume provisioning, encryption/key escrow, scheduled off-host backups and recovery time/point objectives remain open.
