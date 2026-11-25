"""Back up every running managed database to WEBOPS_DATABASE_BACKUP_DIR (run it periodically)."""
from django.core.management.base import BaseCommand

from apps.databases import provisioner


class Command(BaseCommand):
    help = "Back up all running managed databases and prune old backups."

    def handle(self, *args, **options):
        results = provisioner.backup_all()
        for name, outcome in results:
            self.stdout.write(f"{name}: {outcome}")
        if not results:
            self.stdout.write("No managed databases.")
