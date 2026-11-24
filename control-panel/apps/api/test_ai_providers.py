"""AI providers: SSRF-safe client, key handling and management views."""
import socket
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.api import ai_client
from apps.api.ai_client import BlockedAddress, ProviderError, is_public_ip, validate_base_url
from apps.api.models import AIProvider

User = get_user_model()


def _addr(ip):
    fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(fam, socket.SOCK_STREAM, 6, "", (ip, 443))]


class AddressTests(SimpleTestCase):
    def test_public_and_non_public(self):
        for ip in ("8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"):
            self.assertTrue(is_public_ip(ip), ip)
        for ip in ("127.0.0.1", "10.0.0.5", "172.16.3.1", "192.168.1.1", "169.254.169.254", "100.64.0.1",
                   "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1", "nonsense"):
            self.assertFalse(is_public_ip(ip), ip)

    def test_resolve_requires_every_address_public(self):
        mixed = _addr("8.8.8.8") + _addr("10.0.0.1")
        with mock.patch("socket.getaddrinfo", return_value=mixed):
            with self.assertRaises(BlockedAddress):
                ai_client.resolve_public("example.com", 443)
        with mock.patch("socket.getaddrinfo", return_value=_addr("8.8.8.8")):
            self.assertTrue(ai_client.resolve_public("example.com", 443))


class ValidateUrlTests(SimpleTestCase):
    def check(self, url, ip="8.8.8.8"):
        with mock.patch("socket.getaddrinfo", return_value=_addr(ip)):
            return validate_base_url(url)

    def test_accepts_https_and_trims(self):
        self.assertEqual(self.check("https://api.openai.com/v1/"), "https://api.openai.com/v1")
        self.assertEqual(self.check("https://example.com:8443/openai"), "https://example.com:8443/openai")

    def test_rejects_bad_shapes(self):
        for url in ("", "http://api.openai.com/v1", "ftp://x.com", "https://user:pw@api.openai.com/v1",
                    "https://api.openai.com/v1?x=1", "https://api.openai.com/v1#f", "https://exa mple.com",
                    "api.openai.com/v1", "https://", "https://a_b.com", "https://x.com/" + "a" * 400):
            with self.assertRaises(ProviderError, msg=url):
                self.check(url)

    def test_rejects_internal_targets(self):
        for ip in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "192.168.0.10", "::1"):
            with self.assertRaises(ProviderError, msg=ip):
                self.check("https://internal.example.com/v1", ip)
        for url in ("https://127.0.0.1/v1", "https://localhost/v1", "https://[::1]/v1", "https://169.254.169.254/latest"):
            with self.assertRaises(ProviderError, msg=url):
                validate_base_url(url)

    def test_unresolvable_host(self):
        with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror):
            with self.assertRaises(ProviderError):
                validate_base_url("https://nope.example.invalid/v1")


class ConnectTimeTests(SimpleTestCase):
    def test_rebinding_is_blocked_at_connect(self):
        """A host that was public at validation time but resolves private when connecting is refused."""
        with mock.patch("socket.getaddrinfo", return_value=_addr("127.0.0.1")), \
             mock.patch("socket.socket") as sock:
            with self.assertRaises(BlockedAddress):
                ai_client._safe_socket("rebind.example.com", 443, 5)
            sock.assert_not_called()

    def test_http_scheme_refused_by_session(self):
        import requests
        with self.assertRaises(requests.exceptions.InvalidSchema):
            ai_client.safe_session().get("http://example.com/")

    def test_session_ignores_env_proxy(self):
        self.assertFalse(ai_client.safe_session().trust_env)


class ProviderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")

    def test_key_is_encrypted_and_roundtrips(self):
        p = AIProvider(user=self.user, name="x", kind="external", model="m", base_url="https://api.example.com/v1")
        p.set_api_key("sk-secret-ABCD1234")
        p.save()
        p.refresh_from_db()
        self.assertNotIn("sk-secret", p.api_key_enc)
        self.assertEqual(p.get_api_key(), "sk-secret-ABCD1234")
        self.assertEqual(p.key_hint, "1234")

    def test_empty_key(self):
        p = AIProvider(user=self.user, name="y", kind="external", model="m", base_url="https://api.example.com/v1")
        p.set_api_key("")
        self.assertEqual(p.get_api_key(), "")


class FakeResponse:
    def __init__(self, status=200, body=b"", ):
        import io
        self.status_code = status
        self.raw = io.BytesIO(body)
        self.raw.read_orig = self.raw.read
        self.closed = False

    def close(self):
        self.closed = True


class ExternalChatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.p = AIProvider(user=self.user, name="ext", kind="external", model="gpt-x", base_url="https://api.example.com/v1")
        self.p.set_api_key("sk-test-SECRETKEY")
        self.p.save()

    def run_chat(self, response):
        session = mock.Mock()
        session.post.return_value = response
        with mock.patch.object(ai_client, "safe_session", return_value=session):
            return ai_client.external_chat(self.p, [{"role": "user", "content": "hi"}]), session

    class _R(FakeResponse):
        pass

    def resp(self, status, obj):
        import json
        r = FakeResponse(status, json.dumps(obj).encode())
        r.raw.read = lambda n, decode_content=True, _b=r.raw.read_orig: _b(n)
        return r

    def test_success_sends_bearer_and_parses(self):
        text, session = self.run_chat(self.resp(200, {"choices": [{"message": {"content": "hello"}}]}))
        self.assertEqual(text, "hello")
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], "https://api.example.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test-SECRETKEY")
        self.assertFalse(kwargs["allow_redirects"])

    def test_error_mapping_never_leaks_key(self):
        cases = {401: "rejected the API key", 403: "rejected the API key", 404: "404", 429: "rate limiting"}
        for status, needle in cases.items():
            with self.assertRaises(ProviderError) as cm:
                self.run_chat(self.resp(status, {"error": {"message": "bad key sk-test-SECRETKEY"}}))
            self.assertIn(needle, str(cm.exception))
            self.assertNotIn("SECRETKEY", str(cm.exception))
        with self.assertRaises(ProviderError) as cm:
            self.run_chat(self.resp(500, {"error": {"message": "oops sk-test-SECRETKEY leaked"}}))
        self.assertNotIn("SECRETKEY", str(cm.exception))
        self.assertIn("[key]", str(cm.exception))

    def test_redirect_refused(self):
        with self.assertRaises(ProviderError) as cm:
            self.run_chat(self.resp(302, {}))
        self.assertIn("redirect", str(cm.exception))

    def test_bad_shape_and_oversize(self):
        with self.assertRaises(ProviderError):
            self.run_chat(self.resp(200, {"nope": 1}))
        big = FakeResponse(200, b"x" * (ai_client.MAX_RESPONSE_BYTES + 10))
        big.raw.read = lambda n, decode_content=True, _b=big.raw.read_orig: _b(n)
        with self.assertRaises(ProviderError) as cm:
            self.run_chat(big)
        self.assertIn("too large", str(cm.exception))

    def test_transport_errors_are_safe(self):
        import requests
        for exc in (requests.exceptions.SSLError("cert sk-test-SECRETKEY"), requests.exceptions.ConnectTimeout("t"),
                    requests.exceptions.ConnectionError("Blocked: address is not public")):
            session = mock.Mock()
            session.post.side_effect = exc
            with mock.patch.object(ai_client, "safe_session", return_value=session):
                with self.assertRaises(ProviderError) as cm:
                    ai_client.external_chat(self.p, [{"role": "user", "content": "x"}])
            self.assertNotIn("SECRETKEY", str(cm.exception))

    def test_complete_records_outcome(self):
        with mock.patch.object(ai_client, "external_chat", side_effect=ProviderError("boom")):
            with self.assertRaises(ProviderError):
                ai_client.complete(self.p, [])
        self.p.refresh_from_db()
        self.assertIs(self.p.last_ok, False)
        self.assertEqual(self.p.last_error, "boom")
        with mock.patch.object(ai_client, "external_chat", return_value="ok"):
            ai_client.complete(self.p, [])
        self.p.refresh_from_db()
        self.assertIs(self.p.last_ok, True)


class LocalProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.p = AIProvider.objects.create(user=self.user, name="local", kind="local", model="my-model")

    def test_not_running(self):
        with mock.patch("apps.api.llm_public._ready_models", return_value={}):
            with self.assertRaises(ProviderError):
                ai_client.local_complete(self.p, [{"role": "user", "content": "hi"}])

    def test_runs_on_loopback_with_caps(self):
        dep = mock.Mock(port=9371)
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"choices": [{"text": "hey"}]}
        with mock.patch("apps.api.llm_public._ready_models", return_value={"my-model": dep}), \
             mock.patch("requests.post", return_value=resp) as post:
            out = ai_client.local_complete(self.p, [{"role": "user", "content": "x" * 9000}], max_tokens=5000)
        self.assertEqual(out, "hey")
        url = post.call_args[0][0]
        body = post.call_args[1]["json"]
        self.assertEqual(url, "http://127.0.0.1:9371/v1/completions")
        self.assertEqual(len(body["prompt"]), ai_client.LOCAL_PROMPT_LIMIT)
        self.assertEqual(body["max_tokens"], ai_client.LOCAL_MAX_TOKENS)


@override_settings(ALLOWED_HOSTS=["testserver"])
class ProviderViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.other = User.objects.create_user("other", "x@example.com", "pw-123456-x")
        self.client.force_login(self.user)

    def add(self, **kw):
        data = {"kind": "external", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
                "api_key": "sk-live-ZZZZ9999"}
        data.update(kw)
        with mock.patch("socket.getaddrinfo", return_value=_addr("8.8.8.8")):
            return self.client.post(reverse("ai_providers"), data)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("ai_providers")).status_code, 302)

    def test_add_external_and_key_never_rendered(self):
        r = self.add()
        self.assertEqual(r.status_code, 200)
        p = AIProvider.objects.get()
        self.assertTrue(p.is_default)
        self.assertNotIn(b"sk-live-ZZZZ9999", r.content)
        self.assertIn("9999", r.content.decode())
        self.assertNotIn("sk-live", p.api_key_enc)
        page = self.client.get(reverse("ai_providers")).content
        self.assertNotIn(b"sk-live", page)

    def test_rejects_private_url_and_http(self):
        for url in ("https://127.0.0.1/v1", "http://api.openai.com/v1"):
            r = self.client.post(reverse("ai_providers"), {"kind": "external", "name": "bad", "base_url": url, "model": "m"})
            self.assertEqual(r.status_code, 400, url)
            self.assertContains(r, "ui-formerror", status_code=400)
        self.assertEqual(AIProvider.objects.count(), 0)

    def test_duplicate_and_limit(self):
        self.add()
        self.assertEqual(self.add().status_code, 400)
        for i in range(9):
            self.assertEqual(self.add(name=f"p{i}").status_code, 200)
        self.assertEqual(self.add(name="overflow").status_code, 400)

    def test_local_must_be_a_ready_model(self):
        r = self.client.post(reverse("ai_providers"), {"kind": "local", "name": "L", "local_model": "ghost"})
        self.assertEqual(r.status_code, 400)
        with mock.patch("apps.api.ai_views._ready_models", return_value={"real": object()}):
            r = self.client.post(reverse("ai_providers"), {"kind": "local", "name": "L", "local_model": "real"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AIProvider.objects.get().kind, "local")

    def test_ownership_enforced(self):
        self.add(name="ui-cell-owned-name")
        p = AIProvider.objects.get()
        self.client.force_login(self.other)
        for name in ("ai_provider_test", "ai_provider_default", "ai_provider_delete", "ai_provider_key"):
            self.assertEqual(self.client.post(reverse(name, args=[p.pk]), {"api_key": "x"}).status_code, 404, name)
        self.assertEqual(AIProvider.objects.count(), 1)
        self.assertNotContains(self.client.get(reverse("ai_providers")), "ui-cell-owned-name")

    def test_get_not_allowed_on_actions(self):
        self.add()
        p = AIProvider.objects.get()
        for name in ("ai_provider_test", "ai_provider_default", "ai_provider_delete", "ai_provider_key"):
            self.assertEqual(self.client.get(reverse(name, args=[p.pk])).status_code, 405)

    def test_default_delete_and_key_replace(self):
        self.add()
        self.add(name="Second")
        a, b = AIProvider.objects.order_by("id")
        self.client.post(reverse("ai_provider_default", args=[b.pk]))
        a.refresh_from_db(); b.refresh_from_db()
        self.assertFalse(a.is_default); self.assertTrue(b.is_default)
        self.client.post(reverse("ai_provider_delete", args=[b.pk]))
        a.refresh_from_db()
        self.assertTrue(a.is_default)
        self.client.post(reverse("ai_provider_key", args=[a.pk]), {"api_key": "sk-new-0000AAAA"})
        a.refresh_from_db()
        self.assertEqual(a.get_api_key(), "sk-new-0000AAAA")
        self.assertEqual(a.key_hint, "AAAA")

    def test_test_button_reports_and_rate_limits(self):
        self.add()
        p = AIProvider.objects.get()
        with mock.patch("apps.api.ai_views.complete", return_value="ok"):
            r = self.client.post(reverse("ai_provider_test", args=[p.pk]))
        self.assertContains(r, "answered")
        with mock.patch("apps.api.ai_views.complete", side_effect=ProviderError("The provider rejected the API key (HTTP 401).")):
            r = self.client.post(reverse("ai_provider_test", args=[p.pk]))
        self.assertContains(r, "rejected the API key")
        last = None
        with mock.patch("apps.api.ai_views.complete", return_value="ok"):
            for _ in range(8):
                last = self.client.post(reverse("ai_provider_test", args=[p.pk]))
        self.assertEqual(last.status_code, 429)


@override_settings(ALLOWED_HOSTS=["testserver"])
class FormShapeTests(TestCase):
    def test_single_model_field_per_type(self):
        user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")
        self.client.force_login(user)
        html = self.client.get(reverse("ai_providers")).content.decode()
        self.assertEqual(html.count('name="model"'), 1)
        self.assertEqual(html.count('name="local_model"'), 1)
        self.assertNotIn("<script>", html)
