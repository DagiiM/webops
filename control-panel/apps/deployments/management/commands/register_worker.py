"""Register a build worker from a token HASH, so the token itself never has to leave the worker.

On the worker, `worker/install.sh` generates the token locally and prints a ready-to-run command that calls this.
"""
import re

from django.core.management.base import BaseCommand, CommandError

from apps.deployments.models import WorkerNode


class Command(BaseCommand):
    help = "Register (or re-key) a build worker by the SHA-256 digest of its token."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--digest", required=True, help="64 hex characters: sha256 of the worker's token.")

    def handle(self, *args, **options):
        name, digest = options["name"].strip(), options["digest"].strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CommandError("The digest must be 64 hexadecimal characters.")
        if not 2 <= len(name) <= 60 or not all(c.isalnum() or c in "-_ ." for c in name):
            raise CommandError("Use 2 to 60 characters: letters, digits, spaces, dots, hyphens or underscores.")
        other = WorkerNode.objects.filter(digest=digest).exclude(name=name).first()
        if other:
            raise CommandError("That token is already registered to another worker.")
        node = WorkerNode.objects.filter(name=name).first()
        if node:
            node.digest, node.revoked_at = digest, None
            node.save(update_fields=["digest", "revoked_at"])
            self.stdout.write(f"Re-keyed worker '{name}'.")
        else:
            WorkerNode.objects.create(name=name, digest=digest)
            self.stdout.write(f"Registered worker '{name}'.")
