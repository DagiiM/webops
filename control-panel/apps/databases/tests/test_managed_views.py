"""Managed database pages: deploy, lifecycle actions, detail and permanent delete."""
import re
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.databases import provisioner as pv
from apps.databases.models import Database

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver"])
class ManagedViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = Path(tempfile.mkdtemp(prefix="wo-mv-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        o = override_settings(WEBOPS_DATABASES_ROOT=str(self.tmp))
        o.enable()
        self.addCleanup(o.disable)
        self.user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.other = User.objects.create_user("other", "x@example.com", "pw-123456-x")
        self.client.force_login(self.user)

    def deploy(self, **data):
        body = {"engine": "sqlite", "name": "notes"}
        body.update(data)
        return self.client.post(reverse("database_deploy"), body)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("database_deploy")).status_code, 302)

    def test_page_lists_engines_and_disables_missing_ones(self):
        with mock.patch.object(pv, "_pg_bin", return_value=None), mock.patch.object(pv, "_redis_bin", return_value=None):
            html = self.client.get(reverse("database_deploy")).content.decode()
        self.assertIn("apt-get install postgresql", html)
        self.assertRegex(html, r'value="postgresql"\s+disabled')
        self.assertNotRegex(html, r'value="sqlite"\s+disabled')
        self.assertNotIn("<script>", html)

    def test_deploy_sqlite_end_to_end(self):
        r = self.deploy()
        db = Database.objects.get(name="notes")
        self.assertRedirects(r, reverse("database_detail", args=[db.pk]), fetch_redirect_response=False)
        self.assertTrue(db.managed)
        self.assertEqual(db.created_by, self.user)
        self.assertTrue(Path(db.database_name).is_file())
        page = self.client.get(reverse("database_detail", args=[db.pk])).content.decode()
        self.assertIn("Managed by WebOps", page)
        self.assertIn("sqlite:///" + db.database_name, page)
        self.assertIn("Running", page)

    def test_name_is_normalised(self):
        self.deploy(name="My-Notes")
        self.assertTrue(Database.objects.filter(name="my_notes").exists())

    def test_validation_errors_leave_nothing_behind(self):
        for body, needle in (({"name": "1bad"}, "letter first"), ({"name": "x"}, "2 to 30"), ({"engine": "oracle"}, "Choose a database type"),
                             ({"name": "a;b"}, "letter first")):
            r = self.deploy(**body)
            self.assertEqual(r.status_code, 400, body)
            self.assertContains(r, needle, status_code=400)
            self.assertContains(r, "ui-formerror", status_code=400)
        self.assertEqual(Database.objects.count(), 0)
        self.assertFalse(any(self.tmp.iterdir()))

    def test_duplicate_name_rejected(self):
        self.deploy()
        r = self.deploy()
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "already exists", status_code=400)
        self.assertEqual(Database.objects.count(), 1)

    def test_engine_missing_is_rejected_with_hint(self):
        with mock.patch.object(pv, "_pg_bin", return_value=None):
            r = self.deploy(engine="postgresql", name="shop")
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "apt-get install postgresql", status_code=400)
        self.assertEqual(Database.objects.count(), 0)

    def test_per_user_limit(self):
        for i in range(pv.MAX_PER_USER):
            self.assertEqual(self.deploy(name=f"db{i}").status_code, 302)
        r = self.deploy(name="overflow")
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "up to", status_code=400)

    def test_provision_failure_removes_the_record_and_frees_the_name(self):
        with mock.patch.object(pv, "provision", side_effect=pv.ProvisionError("PostgreSQL did not start.")):
            r = self.deploy()
        self.assertEqual(r.status_code, 502)
        self.assertContains(r, "did not start", status_code=502)
        self.assertEqual(Database.objects.count(), 0)
        self.assertEqual(self.deploy().status_code, 302)          # same name works afterwards

    def test_unexpected_crash_is_reported_safely(self):
        with mock.patch.object(pv, "provision", side_effect=RuntimeError("secret internals")):
            r = self.deploy()
        self.assertEqual(r.status_code, 500)
        self.assertNotContains(r, "secret internals", status_code=500)
        self.assertEqual(Database.objects.count(), 0)

    def _managed(self, name="notes"):
        self.deploy(name=name)
        return Database.objects.get(name=name)

    def test_actions_are_post_only_owned_and_whitelisted(self):
        db = self._managed()
        url = reverse("database_action", args=[db.pk, "check"])
        self.assertEqual(self.client.get(url).status_code, 405)
        r = self.client.post(url, follow=True)
        self.assertContains(r, "Opened the file")
        self.assertEqual(self.client.post(f"/databases/{db.pk}/format/").status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("database_status", args=[db.pk])).status_code, 404)

    def test_start_stop_restart_call_the_provisioner(self):
        db = self._managed()
        for action in ("start", "stop", "restart"):
            with mock.patch.dict(managed_actions(), {action: mock.Mock()}) as m:
                r = self.client.post(reverse("database_action", args=[db.pk, action]), follow=True)
            self.assertContains(r, f"{action} done")
        with mock.patch.dict(managed_actions(), {"start": mock.Mock(side_effect=pv.ProvisionError("Redis did not start."))}):
            r = self.client.post(reverse("database_action", args=[db.pk, "start"]), follow=True)
        self.assertContains(r, "Redis did not start.")

    def test_status_endpoint(self):
        db = self._managed()
        self.assertEqual(self.client.get(reverse("database_status", args=[db.pk])).json(), {"status": "running"})

    def test_list_shows_live_status(self):
        db = self._managed()
        html = self.client.get(reverse("database_list")).content.decode()
        self.assertIn("Running", html)
        shutil.rmtree(pv.instance_dir(db))
        self.assertIn("Files missing", self.client.get(reverse("database_list")).content.decode())
        self.assertIn(reverse("database_deploy"), html)

    def test_delete_requires_typed_name_then_removes_files_and_record(self):
        db = self._managed()
        url = reverse("database_delete", args=[db.pk])
        for body in ({"confirm": "yes"}, {"confirm": "yes", "confirm_name": "wrong"}, {"confirm_name": "notes"}):
            self.assertEqual(self.client.post(url, body).status_code, 400, body)
        self.assertTrue(pv.instance_dir(db).exists())
        r = self.client.post(url, {"confirm": "yes", "confirm_name": "notes"})
        self.assertRedirects(r, reverse("database_list"), fetch_redirect_response=False)
        self.assertFalse(pv.instance_dir(db).exists())
        self.assertFalse(Database.objects.filter(pk=db.pk).exists())
        self.assertEqual(self.deploy().status_code, 302)           # name is free again

    def test_delete_failure_keeps_the_record(self):
        db = self._managed()
        with mock.patch.object(pv, "destroy", side_effect=pv.ProvisionError("PostgreSQL did not stop cleanly.")):
            r = self.client.post(reverse("database_delete", args=[db.pk]), {"confirm": "yes", "confirm_name": "notes"})
        self.assertEqual(r.status_code, 502)
        self.assertTrue(Database.objects.filter(pk=db.pk).exists())

    def test_cannot_delete_someone_elses(self):
        db = self._managed()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("database_delete", args=[db.pk]), {"confirm": "yes", "confirm_name": "notes"}).status_code, 404)
        self.assertTrue(pv.instance_dir(db).exists())

    def test_delete_form_actually_submits_the_confirmation(self):
        """Regression: the checkbox had no name, so the form never sent confirm=yes and delete always failed."""
        db = self._managed()
        html = self.client.get(reverse("database_delete", args=[db.pk])).content.decode()
        self.assertRegex(html, r'<input type="checkbox" id="confirm-checkbox" name="confirm" value="yes"')
        self.assertIn('name="confirm_name"', html)
        ext = Database.objects.create(name="external", db_type="postgresql", host="h", port=5432, username="u", created_by=self.user)
        html = self.client.get(reverse("database_delete", args=[ext.pk])).content.decode()
        self.assertIn('name="confirm" value="yes"', html)
        self.assertNotIn('name="confirm_name"', html)

    def test_external_databases_keep_working(self):
        ext = Database.objects.create(name="external", db_type="postgresql", host="h", port=5432, username="u", created_by=self.user)
        page = self.client.get(reverse("database_detail", args=[ext.pk])).content.decode()
        self.assertNotIn("Managed by WebOps", page)
        self.assertIn("External" if False else "external", page)
        self.assertEqual(self.client.post(reverse("database_delete", args=[ext.pk]), {"confirm": "yes"}).status_code, 302)


def managed_actions():
    from apps.databases import managed_views
    return managed_views.ACTIONS
