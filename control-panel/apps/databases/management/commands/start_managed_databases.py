"""Start managed databases that should be running (run after a host restart)."""
from django.core.management.base import BaseCommand

from apps.databases import provisioner


class Command(BaseCommand):
    help = "Start every managed database that is stopped."

    def handle(self, *args, **options):
        results = provisioner.reconcile()
        for name, outcome in results:
            self.stdout.write(f"{name}: {outcome}")
        if not results:
            self.stdout.write("No managed databases.")
