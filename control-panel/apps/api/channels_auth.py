"""
Channels middleware for token-based authentication over WebSocket.

This middleware extracts a Bearer token from the WebSocket connection
headers and resolves it to a Django User, attaching the user to the
connection scope as `scope['user']`.

Clients should send `Authorization: Bearer <token>` when connecting.
"""

from __future__ import annotations

from typing import Any, Iterable, Tuple
from django.contrib.auth.models import AnonymousUser, User
from channels.db import database_sync_to_async

from .authentication import get_user_from_token


class TokenAuthMiddleware:
    """ASGI middleware for token-based WebSocket auth."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict, receive: Any, send: Any) -> Any:
        token = self._extract_bearer_token(scope.get("headers", ()))
        if token:
            user = await self._get_user(token)
            scope["user"] = user or AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)

    @staticmethod
    def _extract_bearer_token(headers: Iterable[Tuple[bytes, bytes]]) -> str | None:
        """Parse `Authorization: Bearer <token>` from ASGI headers."""
        for name, value in headers:
            if name.lower() == b"authorization":
                try:
                    auth_header = value.decode("utf-8")
                except Exception:
                    continue
                if auth_header.startswith("Bearer "):
                    return auth_header.split(" ", 1)[1].strip()
        return None

    @database_sync_to_async
    def _get_user(self, token: str) -> User | None:
        return get_user_from_token(token)


def TokenAuthMiddlewareStack(inner: Any) -> TokenAuthMiddleware:
    """Helper to wrap an ASGI app with TokenAuthMiddleware."""
    return TokenAuthMiddleware(inner)