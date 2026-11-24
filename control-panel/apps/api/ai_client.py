"""OpenAI-compatible chat client for user-configured AI providers.

Two kinds of provider (see AIProvider):

* ``local``    the user's own running, reviewed CPU model, called on 127.0.0.1. Nothing leaves the host.
* ``external`` any OpenAI-compatible HTTPS endpoint. The URL is typed by a user, so the server must not
               become a way to reach internal services (SSRF). Defences, all enforced here:
                 - https only, no credentials/query/fragment in the URL
                 - the hostname is resolved and EVERY address must be public (no loopback, private,
                   link-local, CGNAT, multicast, unspecified; IPv4-mapped IPv6 is unwrapped)
                 - the same check runs again when the socket is opened and only a vetted address is
                   connected to, so DNS rebinding between check and connect cannot help
                 - no redirects, no environment proxies, bounded response size and timeouts
               Error messages are user-safe: they never include the API key or raw upstream bodies.
"""
import ipaddress
import json
import logging
import re
import socket
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NameResolutionError, NewConnectionError

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 256 * 1024
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 60
MAX_URL_LENGTH = 300
LOCAL_PROMPT_LIMIT = 4096       # the reviewed CPU model server's own limit
LOCAL_MAX_TOKENS = 128


class ProviderError(Exception):
    """A failure whose message is safe to show to the user."""


class BlockedAddress(OSError):
    """The destination resolved to a non-public address."""


# ───────────────────────────── address checks ─────────────────────────────

def is_public_ip(value) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return bool(addr.is_global) and not addr.is_multicast


def resolve_public(host: str, port: int):
    """Resolve host and return its addresses. Raises BlockedAddress unless ALL of them are public."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise NameResolutionError(host, None, exc) from exc
    if not infos:
        raise BlockedAddress("no address")
    if not all(is_public_ip(info[4][0]) for info in infos):
        raise BlockedAddress("address is not public")
    return infos


_HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


def validate_base_url(raw: str, *, resolve: bool = True) -> str:
    """Return the normalised base URL (no trailing slash) or raise ProviderError."""
    text = (raw or "").strip()
    if not text or len(text) > MAX_URL_LENGTH or any(c.isspace() or ord(c) < 32 for c in text):
        raise ProviderError("Enter the provider's base URL, for example https://api.openai.com/v1")
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise ProviderError("That is not a valid URL.")
    if parts.scheme != "https":
        raise ProviderError("The base URL must start with https://")
    if parts.username or parts.password or "@" in parts.netloc:
        raise ProviderError("Do not put credentials in the URL. Use the API key field.")
    if parts.query or parts.fragment:
        raise ProviderError("The base URL must not contain a query string or fragment.")
    host = parts.hostname or ""
    if not host or not (_HOST_RE.match(host) or ":" in host or re.match(r"^\d+(\.\d+){3}$", host)):
        raise ProviderError("That host name is not valid.")
    if resolve:
        try:
            resolve_public(host, port or 443)
        except NameResolutionError:
            raise ProviderError("That host name could not be resolved. Check the spelling.")
        except BlockedAddress:
            raise ProviderError("That address is not a public internet address. Only public HTTPS endpoints "
                                "are allowed; use a Local provider for models on this server.")
    path = parts.path.rstrip("/")
    return f"https://{parts.netloc}{path}"


# ───────────────────────────── safe transport ─────────────────────────────

def _safe_socket(host, port, timeout):
    """Connect only to a vetted public address (re-resolved here, so rebinding cannot swap it)."""
    infos = resolve_public(host, port)
    last = None
    for family, socktype, proto, _canon, sockaddr in infos:
        sock = socket.socket(family, socktype, proto)
        try:
            if timeout is None or isinstance(timeout, (int, float)):
                sock.settimeout(timeout)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last = exc
            sock.close()
    raise last or BlockedAddress("could not connect")


class SafeHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        try:
            return _safe_socket(self._dns_host, self.port, self.timeout)
        except NameResolutionError:
            raise
        except BlockedAddress as exc:
            raise NewConnectionError(self, f"Blocked: {exc}") from exc
        except socket.timeout as exc:
            raise ConnectTimeoutError(self, f"Connection to {self.host} timed out.") from exc
        except OSError as exc:
            raise NewConnectionError(self, f"Failed to establish a new connection: {exc}") from exc


class SafeHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = SafeHTTPSConnection


class _SafeAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"https": SafeHTTPSPool}


class _RefuseAdapter(HTTPAdapter):
    def send(self, *args, **kwargs):
        raise requests.exceptions.InvalidSchema("Only https is allowed.")


def safe_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False          # never route through an environment proxy: it would bypass the checks
    session.mount("https://", _SafeAdapter())
    session.mount("http://", _RefuseAdapter())
    return session


# ───────────────────────────── calls ─────────────────────────────

def _mask(text: str, secret: str) -> str:
    return text.replace(secret, "[key]") if secret else text


def _clean(text) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or "")).strip()[:200]


def _read_capped(response) -> bytes:
    body = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ProviderError("The provider's response was too large.")
    return body


def external_chat(provider, messages, *, max_tokens=512, temperature=0.2) -> str:
    """POST {base_url}/chat/completions and return the assistant text."""
    try:
        key = provider.get_api_key()
    except ValueError:
        raise ProviderError("The stored API key can no longer be read. Edit the provider and enter the key again.")
    base = validate_base_url(provider.base_url, resolve=False)   # resolution is enforced at connect time
    if not provider.model:
        raise ProviderError("This provider has no model name set.")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    payload = {"model": provider.model, "messages": messages, "max_tokens": int(max_tokens), "temperature": float(temperature)}
    try:
        response = safe_session().post(base + "/chat/completions", data=json.dumps(payload), headers=headers,
                                       timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), allow_redirects=False, stream=True)
    except requests.exceptions.SSLError:
        raise ProviderError("The provider's TLS certificate could not be verified.")
    except requests.exceptions.Timeout:
        raise ProviderError("The provider did not answer in time.")
    except requests.exceptions.RequestException as exc:
        cause = repr(exc)
        if "Blocked" in cause:
            raise ProviderError("That address is not a public internet address, so the request was blocked.")
        if "NameResolution" in cause or "Name or service" in cause:
            raise ProviderError("The provider's host name could not be resolved.")
        raise ProviderError("Could not reach the provider.")
    try:
        status = response.status_code
        if 300 <= status < 400:
            raise ProviderError("The provider tried to redirect the request, which is not allowed.")
        raw = _read_capped(response)
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            data = None
        if status == 401 or status == 403:
            raise ProviderError("The provider rejected the API key (HTTP %d)." % status)
        if status == 404:
            raise ProviderError("The provider returned 404. Check the base URL and model name.")
        if status == 429:
            raise ProviderError("The provider is rate limiting this key. Try again shortly.")
        if status != 200 or not isinstance(data, dict):
            detail = ""
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                detail = _mask(_clean(data["error"].get("message")), key)
            raise ProviderError(f"The provider returned HTTP {status}." + (f" {detail}" if detail else ""))
        try:
            choice = data["choices"][0]
            text = (choice.get("message") or {}).get("content") if isinstance(choice.get("message"), dict) else choice.get("text")
        except (KeyError, IndexError, TypeError, AttributeError):
            text = None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("The provider's reply was not in the OpenAI format.")
        return text
    finally:
        response.close()


def local_complete(provider, messages, *, max_tokens=128, temperature=0.2) -> str:
    """Run a bounded completion on the user's own ready CPU model (text completions only)."""
    from apps.api.llm_public import _ready_models
    ready = _ready_models(provider.user)
    deployment = ready.get(provider.model)
    if deployment is None:
        raise ProviderError("That local model is not running. Start it from LLM models, or pick another provider.")
    prompt = "\n\n".join(m["content"] for m in messages if m.get("content"))[-LOCAL_PROMPT_LIMIT:]
    try:
        response = requests.post(f"http://127.0.0.1:{int(deployment.port)}/v1/completions",
                                 json={"prompt": prompt, "max_tokens": max(1, min(int(max_tokens), LOCAL_MAX_TOKENS)),
                                       "temperature": float(temperature)},
                                 timeout=60, allow_redirects=False)
    except requests.RequestException:
        raise ProviderError("The local model is unavailable. Check its status.")
    if response.status_code == 429:
        raise ProviderError("The local model is busy. Try again shortly.")
    try:
        if response.status_code != 200:
            raise ValueError
        text = response.json()["choices"][0]["text"]
        if not isinstance(text, str):
            raise ValueError
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("The local model did not return a valid response.")
    return text


def complete(provider, messages, *, max_tokens=512, temperature=0.2) -> str:
    """Run a chat on ``provider`` and record the outcome. Raises ProviderError with a user-safe message."""
    from django.utils import timezone
    try:
        if provider.kind == provider.LOCAL:
            text = local_complete(provider, messages, max_tokens=max_tokens, temperature=temperature)
        else:
            text = external_chat(provider, messages, max_tokens=max_tokens, temperature=temperature)
    except ProviderError as exc:
        provider.last_ok, provider.last_error, provider.last_used = False, str(exc)[:240], timezone.now()
        provider.save(update_fields=["last_ok", "last_error", "last_used"])
        raise
    provider.last_ok, provider.last_error, provider.last_used = True, "", timezone.now()
    provider.save(update_fields=["last_ok", "last_error", "last_used"])
    logger.info("AI provider call ok provider_id=%s kind=%s", provider.pk, provider.kind)
    return text
