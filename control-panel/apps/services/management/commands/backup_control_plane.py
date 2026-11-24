from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.services.recovery import create_snapshot, verify_snapshot, stage_restore

class Command(BaseCommand):
    help = "Create/verify private SQLite snapshots or stage a non-destructive restore."

    def add_arguments(self, parser):
        subs = parser.add_subparsers(dest="operation", required=True)
        create = subs.add_parser("create")
        create.add_argument("--destination", required=True)
        verify = subs.add_parser("verify")
        verify.add_argument("snapshot")
        restore = subs.add_parser("restore-stage")
        restore.add_argument("snapshot")
        restore.add_argument("--destination", required=True)

    def handle(self, *args, **opts):
        try:
            op = opts["operation"]
            if op == "create":
                database = settings.DATABASES["default"]
                if database["ENGINE"] != "django.db.backends.sqlite3":
                    raise ValueError("This command supports SQLite only")
                queue = getattr(settings, "WEBOPS_QUEUE_PATH", Path(settings.WEBOPS_INSTALL_PATH) / "queue" / "jobs.sqlite3")
                result = create_snapshot(Path(database["NAME"]), Path(queue), opts["destination"])
                self.stdout.write("Snapshot created: " + str(result))
            elif op == "verify":
                verify_snapshot(opts["snapshot"])
                self.stdout.write("Snapshot checksums and SQLite integrity verified.")
            else:
                result, count = stage_restore(opts["snapshot"], opts["destination"])
                self.stdout.write(f"Staged restore: {result}; quarantined jobs: {count}. No live files changed.")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc))
