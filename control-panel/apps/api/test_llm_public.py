import hashlib
import secrets
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.api.models import APIToken, LLMAccessKey, MCPAccessToken
from apps.deployments.models import LLMDeployment

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
SETTINGS = dict(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})


def make_key(user, **kw):
    raw = "wops_llm_" + secrets.token_urlsafe(32)
    key = LLMAccessKey.objects.create(
        user=user, name=kw.get("name", "test"), digest=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=kw.get("expires_at", timezone.now() + timezone.timedelta(days=1)),
        revoked_at=kw.get("revoked_at"))
    return raw, key


def upstream(status=200, payload=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload if payload is not None else {"choices": [{"text": " world"}]}
    return response


@override_settings(**SETTINGS)
class PublicLLMAPITests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.owner = U.objects.create_user(username="llm-owner")
        self.other = U.objects.create_user(username="llm-other")
        self.mine = LLMDeployment.objects.create(name="smol-mine", deployed_by=self.owner, status="running", port=9101, model_name=MODEL)
        self.theirs = LLMDeployment.objects.create(name="smol-theirs", deployed_by=self.other, status="running", port=9102, model_name=MODEL)
        self.stopped = LLMDeployment.objects.create(name="smol-stopped", deployed_by=self.owner, status="stopped", port=9103, model_name=MODEL)
        self.unreviewed = LLMDeployment.objects.create(name="big-unreviewed", deployed_by=self.owner, status="running", port=9104, model_name="meta/Unreviewed-70B")
        self.raw, self.key = make_key(self.owner)
        runtime = MagicMock()
        runtime.status.return_value = {"active": True, "enabled": True}
        patcher = patch("apps.api.llm_public.portable_runtime", return_value=runtime)
        self.runtime = runtime
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, path="/api/llm/v1/models", raw=None, **kw):
        headers = {"HTTP_AUTHORIZATION": "Bearer " + raw} if raw else {}
        return self.client.get(path, secure=True, **headers, **kw)

    def post(self, body=None, raw="default", content_type="application/json", **kw):
        raw = self.raw if raw == "default" else raw
        headers = {"HTTP_AUTHORIZATION": "Bearer " + raw} if raw else {}
        data = body if isinstance(body, (str, bytes)) else __import__("json").dumps(body if body is not None else {})
        return self.client.post("/api/llm/v1/completions", data, content_type=content_type, secure=True, **headers, **kw)

    # ---- authentication ----
    def test_requires_a_valid_llm_key(self):
        self.assertEqual(self.get().status_code, 401)
        self.assertEqual(self.get(raw="wops_llm_nope").status_code, 401)
        self.assertEqual(self.get(raw=self.raw).status_code, 200)
        self.assertIn("Bearer", self.get().headers["WWW-Authenticate"])

    def test_revoked_expired_and_inactive_user_keys_are_rejected(self):
        raw, _ = make_key(self.owner, revoked_at=timezone.now())
        self.assertEqual(self.get(raw=raw).status_code, 401)
        raw, _ = make_key(self.owner, expires_at=timezone.now() - timezone.timedelta(seconds=1))
        self.assertEqual(self.get(raw=raw).status_code, 401)
        raw, _ = make_key(self.other)
        self.other.is_active = False
        self.other.save()
        self.assertEqual(self.get(raw=raw).status_code, 401)

    def test_other_credentials_are_not_accepted(self):
        api = APIToken.objects.create(user=self.owner, name="rest")
        self.assertEqual(self.get(raw=api.token).status_code, 401)
        mcp = "wops_mcp_" + secrets.token_urlsafe(24)
        MCPAccessToken.objects.create(user=self.owner, name="m", digest=hashlib.sha256(mcp.encode()).hexdigest(),
                                      expires_at=timezone.now() + timezone.timedelta(days=1))
        self.assertEqual(self.get(raw=mcp).status_code, 401)

    def test_key_is_stored_hashed_and_last_used_updates(self):
        self.assertNotIn(self.raw, [self.key.digest])
        self.assertEqual(len(self.key.digest), 64)
        self.get(raw=self.raw)
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used)

    def test_https_is_required(self):
        response = self.client.get("/api/llm/v1/models", HTTP_AUTHORIZATION="Bearer " + self.raw)
        self.assertIn(response.status_code, (301, 403))

    def test_wrong_method_is_rejected(self):
        self.assertEqual(self.client.post("/api/llm/v1/models", "{}", content_type="application/json", secure=True).status_code, 405)
        self.assertEqual(self.get("/api/llm/v1/completions", raw=self.raw).status_code, 405)

    # ---- models ----
    def test_models_lists_only_my_running_reviewed_models(self):
        data = self.get(raw=self.raw).json()
        self.assertEqual(data["object"], "list")
        self.assertEqual([m["id"] for m in data["data"]], ["smol-mine"])

    def test_models_skips_inactive_runtime(self):
        self.runtime.status.return_value = {"active": False}
        self.assertEqual(self.get(raw=self.raw).json()["data"], [])

    # ---- completions ----
    @patch("apps.api.llm_public.requests.post")
    def test_completion_success_shape_and_forwarded_fields_only(self, post):
        post.return_value = upstream()
        response = self.post({"model": "smol-mine", "prompt": "Hello", "max_tokens": 8, "temperature": 0, "user": "x", "logit_bias": {"1": 9}})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["object"], "text_completion")
        self.assertEqual(body["model"], "smol-mine")
        self.assertEqual(body["choices"][0]["text"], " world")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://127.0.0.1:9101/v1/completions")
        self.assertEqual(kwargs["json"], {"prompt": "Hello", "max_tokens": 8, "temperature": 0})
        self.assertFalse(kwargs["allow_redirects"])

    @patch("apps.api.llm_public.requests.post")
    def test_model_is_optional_when_exactly_one_is_ready(self, post):
        post.return_value = upstream()
        self.assertEqual(self.post({"prompt": "Hi"}).status_code, 200)

    @patch("apps.api.llm_public.requests.post")
    def test_cannot_use_someone_elses_stopped_or_unreviewed_model(self, post):
        for name in ("smol-theirs", "smol-stopped", "big-unreviewed", "nope"):
            self.assertEqual(self.post({"model": name, "prompt": "Hi"}).status_code, 404, name)
        post.assert_not_called()

    @patch("apps.api.llm_public.requests.post")
    def test_input_limits(self, post):
        post.return_value = upstream()
        bad = [{}, {"prompt": ""}, {"prompt": "x" * 4097}, {"prompt": "a", "max_tokens": 129}, {"prompt": "a", "max_tokens": 0},
               {"prompt": "a", "max_tokens": True}, {"prompt": "a", "max_tokens": "8"}, {"prompt": "a", "temperature": 3},
               {"prompt": "a", "temperature": True}, {"prompt": ["a"]}, {"prompt": "a", "stream": True}, {"prompt": "a", "model": 5}, [1]]
        for body in bad:
            cache.clear()  # these cases are about validation, not the burst limit
            self.assertEqual(self.post(body).status_code, 400, body)
        cache.clear()
        self.assertEqual(self.post("{not json").status_code, 400)
        cache.clear()
        self.assertEqual(self.post({"prompt": "a"}, content_type="text/plain").status_code, 415)
        cache.clear()
        self.assertEqual(self.post({"prompt": "x" * 20000}).status_code, 413)
        post.assert_not_called()

    @patch("apps.api.llm_public.requests.post")
    def test_upstream_failures_are_safe(self, post):
        post.return_value = upstream(429)
        busy = self.post({"prompt": "a"})
        self.assertEqual(busy.status_code, 429)
        self.assertEqual(busy.headers["Retry-After"], "2")
        post.return_value = upstream(500, {"detail": "Traceback /home/secret/path"})
        broken = self.post({"prompt": "a"})
        self.assertEqual(broken.status_code, 502)
        self.assertNotIn("secret", broken.content.decode())
        post.return_value = upstream(200, {"unexpected": 1})
        self.assertEqual(self.post({"prompt": "a"}).status_code, 502)
        post.side_effect = requests.ConnectionError("connect to 127.0.0.1:9101 refused")
        down = self.post({"prompt": "a"})
        self.assertEqual(down.status_code, 503)
        self.assertNotIn("9101", down.content.decode())

    @patch("apps.api.llm_public.requests.post")
    def test_rate_limit_applies_per_key(self, post):
        post.return_value = upstream()
        codes = [self.post({"prompt": "a"}).status_code for _ in range(14)]
        self.assertIn(429, codes)
        self.assertEqual(codes[0], 200)


@override_settings(**SETTINGS)
class LLMKeyManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.me = U.objects.create_user(username="keys-me", password="pw-keys-12345")
        self.other = U.objects.create_user(username="keys-other", password="pw-keys-12345")
        self.client.force_login(self.me)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/llm/keys/").status_code, 302)

    def test_create_shows_key_once_and_stores_only_a_hash(self):
        response = self.client.post("/api/llm/keys/", {"name": "my app"})
        self.assertEqual(response.status_code, 200)
        issued = response.context["issued"]
        self.assertTrue(issued.startswith("wops_llm_"))
        self.assertContains(response, issued)
        self.assertEqual(response["Referrer-Policy"], "same-origin")  # no-referrer makes browsers send Origin: null and fail CSRF
        key = LLMAccessKey.objects.get(user=self.me)
        self.assertEqual(key.digest, hashlib.sha256(issued.encode()).hexdigest())
        self.assertNotContains(self.client.get("/api/llm/keys/"), issued)

    def test_name_validation_and_key_cap(self):
        self.assertEqual(self.client.post("/api/llm/keys/", {"name": "  "}).status_code, 400)
        for i in range(10):
            make_key(self.me, name=f"k{i}")
        self.assertEqual(self.client.post("/api/llm/keys/", {"name": "eleventh"}).status_code, 400)

    def test_revoke_own_key_only(self):
        _, mine = make_key(self.me)
        _, theirs = make_key(self.other)
        self.assertEqual(self.client.post(f"/api/llm/keys/{theirs.pk}/revoke/").status_code, 404)
        self.client.post(f"/api/llm/keys/{mine.pk}/revoke/")
        mine.refresh_from_db()
        self.assertIsNotNone(mine.revoked_at)
        self.assertEqual(self.client.get(f"/api/llm/keys/{mine.pk}/revoke/").status_code, 405)

    def test_keys_list_is_per_user(self):
        make_key(self.other, name="not-mine")
        self.assertNotContains(self.client.get("/api/llm/keys/"), "not-mine")
