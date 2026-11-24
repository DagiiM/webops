"""Remote build workers: tokens, queue, leases, source streaming, worker API and the approval path."""
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.deployments.models import ApplicationDeployment, BuildJob, DeploymentLog, WorkerNode
from apps.deployments.services import worker_queue as wq

User = get_user_model()
SHA = "a" * 40


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.op = User.objects.create_user("op", "op@example.com", "pw-123456-x", is_staff=True)
        self.d = ApplicationDeployment.objects.create(name="care", repo_url="https://github.com/ifinsta/care", branch="main",
                                                      deployed_by=self.owner, status="requested")
        self.node, self.token = wq.create_worker("worker-1", self.op)
        wq.heartbeat(self.node, {"agent": "t"})

    def job(self, **kw):
        defaults = dict(deployment=self.d, kind="rust", commit=SHA, limits=dict(wq.DEFAULT_LIMITS))
        defaults.update(kw)
        return BuildJob.objects.create(**defaults)


class TokenTests(Base):
    def test_token_is_hashed_and_prefixed(self):
        self.assertTrue(self.token.startswith("wops_wrk_"))
        self.assertNotIn(self.token, self.node.digest)
        self.assertEqual(wq.authenticate(self.token), self.node)

    def test_bad_missing_oversized_and_revoked_tokens(self):
        for bad in ("", None, "nope", "wops_wrk_wrong", "wops_wrk_" + "x" * 500):
            self.assertIsNone(wq.authenticate(bad), bad)
        wq.revoke(self.node)
        self.assertIsNone(wq.authenticate(self.token))

    def test_name_rules(self):
        for bad in ("", "a", "x" * 61, "bad;name", "w\nrk"):
            with self.assertRaises(wq.WorkerError):
                wq.create_worker(bad, self.op)
        with self.assertRaises(wq.WorkerError):
            wq.create_worker("worker-1", self.op)

    def test_heartbeat_keeps_only_known_clean_fields(self):
        wq.heartbeat(self.node, {"agent": "a" * 100, "cpus": 8, "memory_gb": 31.96, "evil": "x", "os": 5, "free_disk_gb": True})
        self.node.refresh_from_db()
        self.assertEqual(self.node.info, {"agent": "a" * 40, "cpus": 8.0, "memory_gb": 32.0})
        self.assertTrue(self.node.is_online)

    def test_online_window(self):
        self.node.last_seen = timezone.now() - timedelta(seconds=WorkerNode.ONLINE_SECONDS + 5)
        self.node.save()
        self.assertFalse(self.node.is_online)
        self.assertFalse(wq.worker_ready())


class QueueTests(Base):
    def test_claim_oldest_first_and_only_once(self):
        a, b = self.job(), self.job()
        other, _ = wq.create_worker("worker-2", self.op)
        first = wq.claim(self.node)
        self.assertEqual(first["id"], a.pk)
        self.assertEqual((first["kind"], first["commit"], first["attempt"]), ("rust", SHA, 1))
        self.assertEqual(wq.claim(other)["id"], b.pk)
        self.assertIsNone(wq.claim(self.node))
        a.refresh_from_db()
        self.assertEqual((a.status, a.worker), ("claimed", self.node))

    def test_nothing_to_claim(self):
        self.assertIsNone(wq.claim(self.node))

    def test_expired_lease_is_requeued_then_given_up_on(self):
        j = self.job()
        for attempt in range(1, BuildJob.MAX_ATTEMPTS + 1):
            claimed = wq.claim(self.node)
            self.assertEqual(claimed["attempt"], attempt)
            BuildJob.objects.filter(pk=j.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(wq.claim(self.node))
        j.refresh_from_db()
        self.assertEqual(j.status, "failed")
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "failed")
        self.assertTrue(DeploymentLog.objects.filter(deployment=self.d, message__contains="Giving up").exists())

    def test_log_appends_extends_the_lease_and_is_capped(self):
        j = self.job()
        wq.claim(self.node)
        wq.append_log(j.pk, self.node, "line 1\n")
        wq.append_log(j.pk, self.node, "line 2\x00\n")
        j.refresh_from_db()
        self.assertEqual((j.log, j.status), ("line 1\nline 2\n", "building"))
        wq.append_log(j.pk, self.node, "x" * 20_000)
        for _ in range(12):
            wq.append_log(j.pk, self.node, "y" * 20_000)
        j.refresh_from_db()
        self.assertLessEqual(len(j.log), BuildJob.MAX_LOG + 40)
        self.assertIn("[log truncated]", j.log)

    def test_only_the_owning_worker_can_touch_a_job(self):
        j = self.job()
        wq.claim(self.node)
        other, _ = wq.create_worker("worker-2", self.op)
        with self.assertRaises(wq.WorkerError):
            wq.append_log(j.pk, other, "x")
        with self.assertRaises(wq.WorkerError):
            wq.complete(j.pk, other, ok=True)

    def test_complete_success_and_failure_update_the_deployment(self):
        j = self.job()
        wq.claim(self.node)
        wq.complete(j.pk, self.node, ok=True, exit_code=0, summary="cargo build ok", artifacts=["target/release/care"])
        j.refresh_from_db(); self.d.refresh_from_db()
        self.assertEqual((j.status, self.d.status, j.result["artifacts"]), ("succeeded", "stopped", ["target/release/care"]))
        self.assertTrue(DeploymentLog.objects.filter(deployment=self.d, level="success").exists())
        with self.assertRaises(wq.WorkerError):                      # finished jobs are closed
            wq.append_log(j.pk, self.node, "x")
        j2 = self.job()
        wq.claim(self.node)
        wq.complete(j2.pk, self.node, ok=False, exit_code=101, summary="compile error")
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "failed")

    def test_revoking_a_worker_requeues_what_it_held(self):
        j = self.job()
        wq.claim(self.node)
        wq.revoke(self.node)
        j.refresh_from_db()
        self.assertEqual((j.status, j.worker), ("queued", None))

    def test_cancel_returns_the_request_to_the_operator(self):
        j = self.job()
        BuildJob.objects.filter(pk=j.pk).update()
        ApplicationDeployment.objects.filter(pk=self.d.pk).update(status="building")
        wq.cancel(j)
        j.refresh_from_db(); self.d.refresh_from_db()
        self.assertEqual((j.status, self.d.status), ("cancelled", "requested"))

    def test_enqueue_rejects_unknown_kinds(self):
        with self.assertRaises(wq.WorkerError):
            wq.enqueue(self.d, "bash", SHA)


class AssessTests(Base):
    facts = {"private": True, "archived": False, "default_branch": "main", "ref": "main", "description": "", "language": "Rust",
             "root": {"Cargo.toml": {"type": "file", "size": 1}}, "files": {}}

    def assess(self, root=None, owner_setting="ifinsta", sha=SHA, status=200, repo="https://github.com/ifinsta/care"):
        self.d.repo_url = repo
        facts = {**self.facts, "root": root or self.facts["root"]}
        resp = mock.Mock(status_code=status)
        resp.json.return_value = {"sha": sha}
        with override_settings(WEBOPS_WORKER_TRUSTED_OWNERS=owner_setting), \
             mock.patch("apps.deployments.services.ai_assist.fetch_repo", return_value=facts), \
             mock.patch.object(wq, "_github", return_value=resp):
            return wq.assess(self.d)

    def test_detect_kind(self):
        self.assertEqual(wq.detect_kind({"Cargo.toml": 1}), "rust")
        self.assertEqual(wq.detect_kind({"package.json": 1}), "node")
        self.assertEqual(wq.detect_kind({"requirements.txt": 1}), "python")
        self.assertEqual(wq.detect_kind({"pyproject.toml": 1}), "python")
        self.assertIsNone(wq.detect_kind({"Makefile": 1, "main.go": 1}))

    def test_ok_pins_the_commit(self):
        self.assertEqual(self.assess(), (True, "", "rust", SHA))

    def test_no_online_worker(self):
        wq.revoke(self.node)
        ok, reason, *_ = self.assess()
        self.assertFalse(ok)
        self.assertIn("No worker is online", reason)
        self.assertIn("isolated worker", reason)

    def test_untrusted_owner_is_refused(self):
        ok, reason, *_ = self.assess(repo="https://github.com/stranger/thing")
        self.assertFalse(ok)
        self.assertIn("trusted owners", reason)
        self.assertIn("WEBOPS_WORKER_TRUSTED_OWNERS", reason)

    def test_the_requesters_own_github_account_is_trusted(self):
        from apps.core.integrations.models import GitHubConnection
        GitHubConnection.objects.create(user=self.owner, github_user_id=1, username="Stranger", access_token="x")
        with mock.patch("apps.core.integrations.services.GitHubIntegrationService.get_access_token", return_value=None):
            ok, *_ = self.assess(repo="https://github.com/stranger/thing", owner_setting="")
        self.assertTrue(ok)

    def test_ssh_unsupported_kind_and_bad_sha_refused(self):
        self.assertFalse(self.assess(repo="git@github.com:ifinsta/care.git")[0])
        self.assertIn("not supported", self.assess(root={"main.go": {}})[1])
        self.assertFalse(self.assess(sha="zz")[0])
        self.assertFalse(self.assess(status=404, sha="")[0])


class SourceTests(Base):
    def stream(self, first, second):
        calls = []

        def fake_get(url, **kw):
            calls.append((url, kw))
            return first if len(calls) == 1 else second
        return fake_get, calls

    def test_streams_from_codeload_without_forwarding_the_token(self):
        j = self.job()
        first = mock.Mock(status_code=302, headers={"Location": "https://codeload.github.com/ifinsta/care/legacy.zip/abc"})
        second = mock.MagicMock(status_code=200)
        second.iter_content.return_value = [b"PK", b"data"]
        with mock.patch.object(wq, "_github", return_value=first) as gh, mock.patch.object(wq.requests, "get", return_value=second) as g, \
             mock.patch("apps.core.integrations.services.GitHubIntegrationService.get_access_token", return_value="ghp_SECRET"):
            data = b"".join(wq.open_source(j))
        self.assertEqual(data, b"PKdata")
        self.assertIn(f"/zipball/{SHA}", gh.call_args[0][0])
        self.assertEqual(gh.call_args[0][1], "ghp_SECRET")
        self.assertNotIn("headers", g.call_args[1])                       # the signed URL is used as is; no Authorization
        self.assertFalse(g.call_args[1]["allow_redirects"])

    def test_unexpected_redirect_host_or_status_refused(self):
        j = self.job()
        for first in (mock.Mock(status_code=302, headers={"Location": "https://evil.example/x.zip"}), mock.Mock(status_code=404, headers={})):
            with mock.patch.object(wq, "_github", return_value=first):
                with self.assertRaises(wq.WorkerError):
                    wq.open_source(j)

    def test_size_cap_stops_the_stream(self):
        j = self.job()
        first = mock.Mock(status_code=302, headers={"Location": "https://codeload.github.com/x"})
        second = mock.MagicMock(status_code=200)
        second.iter_content.return_value = [b"x" * 65536] * 5
        with mock.patch.object(wq, "MAX_SOURCE_BYTES", 100_000), mock.patch.object(wq, "_github", return_value=first), \
             mock.patch.object(wq.requests, "get", return_value=second):
            self.assertLess(len(b"".join(wq.open_source(j))), 200_000)


@override_settings(ALLOWED_HOSTS=["testserver"], DEBUG=False)
class ApiTests(Base):
    def call(self, path, method="post", token=None, secure=True, **kw):
        headers = {"HTTP_AUTHORIZATION": "Bearer " + (token if token is not None else self.token)}
        fn = getattr(self.client, method)
        if method == "post":
            kw.setdefault("content_type", "application/json")
            if "data" in kw and not isinstance(kw["data"], (str, bytes)):
                kw["data"] = json.dumps(kw["data"])
        return fn(path, secure=secure, **headers, **kw)

    def test_authentication_and_transport(self):
        self.assertEqual(self.client.post("/api/worker/v1/claim", secure=True).status_code, 401)
        self.assertEqual(self.call("/api/worker/v1/claim", token="wops_wrk_bad").status_code, 401)
        self.assertEqual(self.call("/api/worker/v1/claim", secure=False).status_code, 403)       # HTTPS only
        self.assertEqual(self.call("/api/worker/v1/claim", method="get").status_code, 405)
        wq.revoke(self.node)
        self.assertEqual(self.call("/api/worker/v1/claim").status_code, 401)

    def test_claim_log_complete_round_trip(self):
        j = self.job()
        self.assertEqual(self.call("/api/worker/v1/claim").json()["id"], j.pk) if False else None
        r = self.call("/api/worker/v1/claim")
        self.assertEqual((r.status_code, r.json()["id"], r.json()["kind"]), (200, j.pk, "rust"))
        self.assertEqual(self.call("/api/worker/v1/claim").status_code, 204)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/log", data={"text": "compiling\n"}).status_code, 200)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/complete", data={"ok": True, "exit_code": 0, "summary": "done", "artifacts": ["a"]}).status_code, 200)
        j.refresh_from_db()
        self.assertEqual((j.status, j.log), ("succeeded", "compiling\n"))
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/log", data={"text": "late"}).status_code, 409)

    def test_validation_and_ownership(self):
        j = self.job()
        self.call("/api/worker/v1/claim")
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/log", data={"text": 5}).status_code, 400)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/log", data="not json").status_code, 400)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/complete", data={"ok": "yes"}).status_code, 400)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/log", data={"text": "x" * 70_000}).status_code, 400)       # body cap
        other, tok = wq.create_worker("worker-2", self.op)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/log", token=tok, data={"text": "x"}).status_code, 409)
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/source", method="get", token=tok).status_code, 404)

    def test_source_streams_only_to_the_holder(self):
        j = self.job()
        self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/source", method="get").status_code, 404)     # not claimed yet
        self.call("/api/worker/v1/claim")
        with mock.patch.object(wq, "open_source", return_value=iter([b"PK", b"zip"])):
            r = self.call(f"/api/worker/v1/jobs/{j.pk}/source", method="get")
        self.assertEqual((r.status_code, b"".join(r.streaming_content), r["Content-Type"]), (200, b"PKzip", "application/zip"))
        with mock.patch.object(wq, "open_source", side_effect=wq.WorkerError("GitHub did not provide the source archive.")):
            self.assertEqual(self.call(f"/api/worker/v1/jobs/{j.pk}/source", method="get").status_code, 502)

    def test_heartbeat_updates_presence(self):
        WorkerNode.objects.filter(pk=self.node.pk).update(last_seen=None)
        self.assertEqual(self.call("/api/worker/v1/heartbeat", data={"cpus": 8, "agent": "1.0"}).status_code, 200)
        self.node.refresh_from_db()
        self.assertTrue(self.node.is_online)
        self.assertEqual(self.node.info["cpus"], 8.0)

    def test_worker_token_does_not_open_the_rest_of_the_api(self):
        for path in ("/api/llm/v1/models", "/api/v1/deployments/"):
            r = self.client.get(path, secure=True, HTTP_AUTHORIZATION="Bearer " + self.token)
            self.assertIn(r.status_code, (401, 403, 404, 302), path)


@override_settings(ALLOWED_HOSTS=["testserver"], WEBOPS_WORKLOAD_POLICY="restricted", WEBOPS_WORKER_TRUSTED_OWNERS="ifinsta")
class ApprovalTests(Base):
    def approve(self):
        self.client.force_login(self.op)
        return self.client.post(reverse("deployments:deployment_approve", args=[self.d.pk]))

    def test_approval_enqueues_a_pinned_job_instead_of_running_here(self):
        with mock.patch.object(wq, "assess", return_value=(True, "", "rust", SHA)), mock.patch("apps.deployments.views.application_deployment.queue_deployment") as local:
            r = self.approve()
        self.assertEqual(r.status_code, 302)
        job = BuildJob.objects.get()
        self.assertEqual((job.kind, job.commit, job.status), ("rust", SHA, "queued"))
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "building")
        local.assert_not_called()                                         # nothing runs on the panel host

    def test_no_worker_means_the_old_refusal_and_the_request_stays_put(self):
        wq.revoke(self.node)
        r = self.approve()
        self.assertEqual(r.status_code, 403)
        self.assertIn(b"isolated worker", r.content)
        self.d.refresh_from_db()
        self.assertEqual(self.d.status, "requested")
        self.assertFalse(BuildJob.objects.exists())

    def test_untrusted_owner_is_refused(self):
        self.d.repo_url = "https://github.com/stranger/thing"
        self.d.save()
        with mock.patch("apps.deployments.services.ai_assist.fetch_repo") as fetch:
            r = self.approve()
        self.assertEqual(r.status_code, 403)
        self.assertIn(b"trusted owners", r.content)
        fetch.assert_not_called()

    def test_operator_screens_offer_approve_when_a_worker_is_online(self):
        self.client.force_login(self.op)
        html = self.client.get(reverse("deployments:deployment_list")).content.decode()
        self.assertIn(reverse("deployments:deployment_approve", args=[self.d.pk]), html)
        wq.revoke(self.node)
        html = self.client.get(reverse("deployments:deployment_list")).content.decode()
        self.assertNotIn(reverse("deployments:deployment_approve", args=[self.d.pk]), html)


@override_settings(ALLOWED_HOSTS=["testserver"])
class WorkerPagesTests(Base):
    def test_only_operators_see_or_use_the_workers_page(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("deployments:workers")).status_code, 403)
        self.assertEqual(self.client.post(reverse("deployments:workers"), {"name": "x1"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("deployments:worker_revoke", args=[self.node.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("deployments:workers")).status_code, 302)

    def test_creating_a_worker_shows_the_token_once_and_stores_only_a_hash(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse("deployments:workers"), {"name": "build-2"})
        self.assertEqual(r.status_code, 200)
        token = r.context["issued"]
        self.assertTrue(token.startswith("wops_wrk_"))
        self.assertContains(r, token)
        node = WorkerNode.objects.get(name="build-2")
        self.assertNotIn(token, node.digest)
        self.assertNotContains(self.client.get(reverse("deployments:workers")), token)        # never again
        self.assertEqual(wq.authenticate(token), node)

    def test_bad_names_stay_on_the_page_with_the_error(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse("deployments:workers"), {"name": "bad;name"})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "ui-formerror", status_code=400)

    def test_revoke_and_job_pages(self):
        j = self.job()
        wq.claim(self.node)
        wq.append_log(j.pk, self.node, "compiling care\n")
        self.client.force_login(self.op)
        page = self.client.get(reverse("deployments:job_detail", args=[j.pk]))
        self.assertContains(page, "compiling care")
        self.assertContains(page, "Cancel job")
        self.client.force_login(self.owner)                                                      # the requester may read their own build log
        self.assertEqual(self.client.get(reverse("deployments:job_detail", args=[j.pk])).status_code, 200)
        self.assertNotContains(self.client.get(reverse("deployments:job_detail", args=[j.pk])), "Cancel job")
        stranger = User.objects.create_user("stranger", "s@example.com", "pw-123456-x")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("deployments:job_detail", args=[j.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("deployments:job_cancel", args=[j.pk])).status_code, 403)
        self.client.force_login(self.op)
        self.client.post(reverse("deployments:job_cancel", args=[j.pk]))
        j.refresh_from_db()
        self.assertEqual(j.status, "cancelled")
        self.client.post(reverse("deployments:worker_revoke", args=[self.node.pk]))
        self.node.refresh_from_db()
        self.assertIsNotNone(self.node.revoked_at)
        self.assertEqual(self.client.get(reverse("deployments:deployment_list")).status_code, 200)


@override_settings(ALLOWED_HOSTS=["testserver"], WEBOPS_WORKER_TRUSTED_OWNERS="ifinsta")
class RetryTests(Base):
    def setUp(self):
        super().setUp()
        self.j = self.job()
        wq.claim(self.node)
        wq.complete(self.j.pk, self.node, ok=False, exit_code=1, summary="boom")

    def test_operator_retries_on_the_latest_commit(self):
        self.client.force_login(self.op)
        page = self.client.get(reverse("deployments:job_detail", args=[self.j.pk]))
        self.assertContains(page, "Retry on latest commit")
        with mock.patch.object(wq, "assess", return_value=(True, "", "rust", "c" * 40)):
            r = self.client.post(reverse("deployments:job_retry", args=[self.j.pk]))
        new = BuildJob.objects.exclude(pk=self.j.pk).get()
        self.assertRedirects(r, reverse("deployments:job_detail", args=[new.pk]), fetch_redirect_response=False)
        self.assertEqual((new.commit, new.status), ("c" * 40, "queued"))

    def test_retry_is_operator_only_and_only_for_finished_failures(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("deployments:job_retry", args=[self.j.pk])).status_code, 403)
        self.client.force_login(self.op)
        running = self.job()
        r = self.client.post(reverse("deployments:job_retry", args=[running.pk]), follow=True)
        self.assertContains(r, "Only a failed or cancelled job")
        self.assertEqual(BuildJob.objects.count(), 2)

    def test_retry_runs_the_same_checks_as_approval(self):
        self.client.force_login(self.op)
        wq.revoke(self.node)
        r = self.client.post(reverse("deployments:job_retry", args=[self.j.pk]), follow=True)
        self.assertContains(r, "No worker is online")
        self.assertEqual(BuildJob.objects.count(), 1)
