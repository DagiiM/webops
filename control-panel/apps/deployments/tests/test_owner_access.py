import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from apps.deployments.models import ApplicationDeployment
from apps.services.runtime.static_publish import extract_static_archive
from apps.api.rate_limiting import RateLimiter

@override_settings(WEBOPS_RUNTIME="supervisor", WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL=True,
                   CHANNEL_LAYERS={"default":{"BACKEND":"channels.layers.InMemoryChannelLayer"}})
class OwnerAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner")
        self.other = User.objects.create_user(username="other")
        self.operator = User.objects.create_user(username="operator", is_staff=True)
        self.client.force_login(self.owner)

    def test_owner_submits_and_cancels_unapproved_request(self):
        with patch("apps.deployments.views.application_deployment.queue_deployment") as queue:
            r = self.client.post(reverse("deployments:deployment_create"),
                {"name":"owner-request","repo_url":"https://github.com/example/repo","branch":"main"})
            self.assertEqual(r.status_code,302)
            d = ApplicationDeployment.objects.get(name="owner-request")
            self.assertEqual(d.deployed_by,self.owner)
            self.assertEqual(d.status,"requested")
            queue.assert_not_called()
            self.assertEqual(self.client.post(reverse("deployments:deployment_approve",args=[d.pk])).status_code,403)
            self.assertEqual(self.client.post(reverse("deployments:deployment_start",args=[d.pk])).status_code,403)
            self.assertEqual(self.client.post(reverse("deployments:deployment_delete",args=[d.pk])).status_code,302)
            d.refresh_from_db()
            self.assertTrue(d.is_deleted)

    def test_operator_approval_queues_once(self):
        d=ApplicationDeployment.objects.create(name="reviewed-app",repo_url="https://github.com/example/repo",deployed_by=self.owner,status="requested")
        self.client.force_login(self.operator)
        with patch("apps.deployments.views.application_deployment.queue_deployment") as queue:
            self.assertEqual(self.client.post(reverse("deployments:deployment_approve",args=[d.pk])).status_code,302)
            self.assertEqual(self.client.post(reverse("deployments:deployment_approve",args=[d.pk])).status_code,404)
            queue.assert_called_once()
        d.refresh_from_db()
        self.assertEqual(d.status,"building")

    def test_nonowner_cannot_read_or_control_deployment(self):
        d=ApplicationDeployment.objects.create(name="other-app",repo_url="https://github.com/example/repo",deployed_by=self.other,status="running")
        for name in ("deployment_detail","deployment_env_manage","deployment_files","deployment_editor","deployment_monitoring"):
            self.assertEqual(self.client.get(reverse("deployments:"+name,args=[d.pk])).status_code,404,name)
        for name in ("deployment_start","deployment_stop","deployment_restart"):
            self.assertEqual(self.client.post(reverse("deployments:"+name,args=[d.pk])).status_code,404,name)

    def test_static_publication_queues_for_nonstaff(self):
        clean=io.BytesIO()
        with zipfile.ZipFile(clean,"w") as archive: archive.writestr("repo-main/index.html","<h1>hello</h1>")
        with patch("apps.deployments.services.safety_review.fetch_archive",return_value=clean.getvalue()), \
             patch("apps.deployments.views.application_deployment.queue_deployment") as queue:
            r=self.client.post(reverse("deployments:deployment_create"),{"name":"static-owner","repo_url":"https://github.com/example/repo","static_only":"on"})
            self.assertEqual(r.status_code,302)
            d=ApplicationDeployment.objects.get(name="static-owner")
            self.assertTrue(d.static_only)
            self.assertEqual(d.status,"pending")
            queue.assert_called_once()

    def test_host_configuration_denied(self):
        self.assertEqual(self.client.get(reverse("monitoring:configuration_list")).status_code,403)

class StaticArchiveTests(SimpleTestCase):
    def archive(self, entries):
        result=io.BytesIO()
        with zipfile.ZipFile(result,"w") as archive:
            for name,data in entries.items(): archive.writestr(name,data)
        return result.getvalue()

    def test_only_assets_are_extracted(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"site"
            extract_static_archive(self.archive({"repo/index.html":"ok","repo/setup.py":"not run","repo/.env":"hidden"}),dest)
            self.assertEqual((dest/"index.html").read_text(),"ok")
            self.assertFalse((dest/"setup.py").exists())
            self.assertFalse((dest/".env").exists())

    def test_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"site"
            with self.assertRaises(ValueError):
                extract_static_archive(self.archive({"repo/index.html":"ok","repo/../../escape.html":"bad"}),dest)
            self.assertFalse(dest.exists())
            self.assertFalse((Path(temp)/"escape.html").exists())

    def test_separate_rate_limit_namespaces(self):
        cache.clear()
        first=RateLimiter(max_requests=1,namespace="test-first")
        second=RateLimiter(max_requests=1,namespace="test-second")
        self.assertTrue(first.is_allowed("same-user")[0])
        self.assertFalse(first.is_allowed("same-user")[0])
        self.assertTrue(second.is_allowed("same-user")[0])
