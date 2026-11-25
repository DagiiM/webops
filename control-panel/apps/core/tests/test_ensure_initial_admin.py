import stat
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

User = get_user_model()


class EnsureInitialAdminTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "sub" / "initial-admin.txt"

    def test_generates_a_password_into_a_private_file_and_never_prints_it(self):
        from io import StringIO
        buf = StringIO()
        with mock.patch.dict("os.environ", {}, clear=False):
            call_command("ensure_initial_admin", "--output", str(self.out), stdout=buf)
        user = User.objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        text = self.out.read_text()
        password = text.split("password: ")[1].strip()
        self.assertGreaterEqual(len(password), 20)
        self.assertTrue(user.check_password(password))
        self.assertNotIn(password, buf.getvalue())
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o600)

    def test_does_nothing_when_an_admin_exists(self):
        User.objects.create_superuser("boss", "b@example.com", "pw-123456-x-long")
        call_command("ensure_initial_admin", "--output", str(self.out))
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(self.out.exists())

    def test_supplied_password_from_file_and_short_ones_refused(self):
        pwfile = self.tmp / "pw"
        pwfile.write_text("a-long-enough-password\n")
        call_command("ensure_initial_admin", "--username", "root1", "--password-file", str(pwfile))
        self.assertTrue(User.objects.get(username="root1").check_password("a-long-enough-password"))
        User.objects.all().delete()
        pwfile.write_text("short")
        with self.assertRaises(CommandError):
            call_command("ensure_initial_admin", "--password-file", str(pwfile))

    def test_needs_somewhere_to_put_a_generated_password(self):
        with self.assertRaises(CommandError):
            call_command("ensure_initial_admin")
        self.assertEqual(User.objects.count(), 0)
