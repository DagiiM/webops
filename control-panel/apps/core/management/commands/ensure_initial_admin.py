"""Create the first administrator on a fresh installation (does nothing when a superuser already exists).

The password comes from --password-file or $WEBOPS_ADMIN_PASSWORD; with neither, a strong one is generated and
written once to --output (mode 0600) instead of being printed, so it never lands in a shared log.
"""
import os
import secrets
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the first superuser if none exists."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("WEBOPS_ADMIN_USERNAME", "admin"))
        parser.add_argument("--email", default=os.environ.get("WEBOPS_ADMIN_EMAIL", "admin@localhost.localdomain"))
        parser.add_argument("--password-file", help="Read the password from this file.")
        parser.add_argument("--output", help="Where to write a generated password (required when none is supplied).")

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True, is_active=True).exists():
            self.stdout.write("An administrator already exists; nothing to do.")
            return
        username = options["username"].strip()
        if not username or User.objects.filter(username=username).exists():
            raise CommandError(f"The username '{username}' is unavailable; pass --username.")
        password = os.environ.get("WEBOPS_ADMIN_PASSWORD", "")
        if options["password_file"]:
            password = Path(options["password_file"]).read_text().strip()
        generated = not password
        if generated:
            if not options["output"]:
                raise CommandError("Give --output (a file for the generated password) or supply a password.")
            password = secrets.token_urlsafe(18)
        elif len(password) < 12:
            raise CommandError("The password must be at least 12 characters.")
        User.objects.create_superuser(username=username, email=options["email"], password=password)
        if generated:
            out = Path(options["output"])
            out.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(f"username: {username}\npassword: {password}\n")
            self.stdout.write(f"Created administrator '{username}'. The generated password is in {out} (change it, then delete the file).")
        else:
            self.stdout.write(f"Created administrator '{username}' with the supplied password.")
