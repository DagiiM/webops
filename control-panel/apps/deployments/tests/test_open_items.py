"""Operator decline, staff review access, the 'cannot run here' panel and the backfill command."""
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.deployments.models import ApplicationDeployment, BaseDeployment

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver"], WEBOPS_WORKLOAD_POLICY="restricted")
class DeclineTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.op = User.objects.create_user("op", "op@example.com", "pw-123456-x", is_staff=True)
        self.other = User.objects.create_user("other", "x@example.com", "pw-123456-x")
        self.d = ApplicationDeployment.objects.create(name="care", repo_url="https://github.com/o/care", branch="main",
                                                      deployed_by=self.owner, status="requested", static_only=False)

    def decline(self, user, reason="Needs an isolated worker.", pk=None):
        self.client.force_login(user)
        return self.client.post(reverse("deployments:deployment_decline", args=[pk or self.d.pk]), {"reason": reason})

    def test_operator_declines_with_a_reason_the_requester_can_read(self):
        r = self.decline(self.op)
        self.assertRedirects(r, reverse("deployments:deployment_list"), fetch_redirect_response=False)
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "failed")
        log = self.d.logs.get()
        self.assertEqual(log.level, "error")
        self.assertIn("declined by op: Needs an isolated worker.", log.message)
        self.client.force_login(self.owner)
        page = self.client.get(reverse("deployments:deployment_detail", args=[self.d.pk])).content.decode()
        self.assertIn("Needs an isolated worker.", page)

    def test_default_reason_and_control_characters_and_length(self):
        self.decline(self.op, reason="\x00\x1b" + "x" * 500)
        self.assertLessEqual(len(self.d.logs.get().message), 260)
        self.assertNotIn("\x1b", self.d.logs.get().message)

    def test_only_operators_and_only_requested_and_only_post(self):
        self.assertEqual(self.decline(self.owner).status_code, 403)
        self.assertEqual(self.decline(self.other).status_code, 403)
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "requested")
        self.client.force_login(self.op)
        self.assertEqual(self.client.get(reverse("deployments:deployment_decline", args=[self.d.pk])).status_code, 405)
        self.assertEqual(self.decline(self.op).status_code, 302)
        self.assertEqual(self.decline(self.op).status_code, 404)           # already processed
        running = ApplicationDeployment.objects.create(name="live", repo_url="https://github.com/o/live", branch="main", deployed_by=self.owner, status="running")
        self.assertEqual(self.decline(self.op, pk=running.pk).status_code, 404)

    def test_operator_can_open_a_request_but_not_someone_elses_running_deployment(self):
        self.client.force_login(self.op)
        page = self.client.get(reverse("deployments:deployment_detail", args=[self.d.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "This server cannot run this project")
        self.assertContains(page, "Operator decision")
        self.assertNotContains(page, "Approve and deploy")                  # policy forbids it, so no dead-end button
        running = ApplicationDeployment.objects.create(name="live", repo_url="https://github.com/o/live", branch="main", deployed_by=self.owner, status="running")
        self.assertEqual(self.client.get(reverse("deployments:deployment_detail", args=[running.pk])).status_code, 404)

    def test_other_users_cannot_open_it(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("deployments:deployment_detail", args=[self.d.pk])).status_code, 404)

    def test_requester_sees_why_it_is_waiting_but_has_no_decision_controls(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse("deployments:deployment_detail", args=[self.d.pk]))
        self.assertContains(page, "This server cannot run this project")
        self.assertNotContains(page, "Operator decision")

    def test_dashboard_and_list_offer_review_and_decline_to_operators(self):
        self.client.force_login(self.op)
        for name in ("deployments:deployment_list", "dashboard"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertIn(reverse("deployments:deployment_decline", args=[self.d.pk]), html, name)
            self.assertIn(reverse("deployments:deployment_detail", args=[self.d.pk]), html, name)
            self.assertNotIn(reverse("deployments:deployment_approve", args=[self.d.pk]), html, name)


@override_settings(WEBOPS_WORKLOAD_POLICY="restricted")
class BackfillCommandTests(TestCase):
    def setUp(self):
        u = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.d = ApplicationDeployment.objects.create(name="care", repo_url="https://github.com/o/care", branch="main", deployed_by=u, status="requested")
        self.done = ApplicationDeployment.objects.create(name="has-report", repo_url="https://github.com/o/x", branch="main", deployed_by=u,
                                                         status="requested", safety_report={"verdict": "review"})

    def test_adds_a_report_to_requests_that_lack_one(self):
        facts = {"private": True, "archived": False, "default_branch": "main", "ref": "main", "description": "", "language": "Rust",
                 "root": {"Cargo.toml": {"type": "file", "size": 5}, ".env": {"type": "file", "size": 5}}, "files": {}}
        out = StringIO()
        with mock.patch("apps.deployments.services.ai_assist.fetch_repo", return_value=facts):
            call_command("review_requested", stdout=out)
        self.d.refresh_from_db()
        self.done.refresh_from_db()
        self.assertEqual(self.d.safety_report["decision"], "needs_operator")
        self.assertEqual(self.done.safety_report, {"verdict": "review"})         # untouched
        self.assertIn("1 request(s) reviewed", out.getvalue())

    def test_a_failing_review_is_reported_not_raised(self):
        from apps.deployments.services.ai_assist import AssistError
        out = StringIO()
        with mock.patch("apps.deployments.services.ai_assist.fetch_repo", side_effect=AssistError("boom")):
            call_command("review_requested", stdout=out)
        self.d.refresh_from_db()
        self.assertEqual(self.d.safety_report, {})
