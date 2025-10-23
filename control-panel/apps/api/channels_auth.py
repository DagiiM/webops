"""
Channels middleware for token-based and session-based authentication over WebSocket.

This middleware supports two authentication methods:
1. Bearer token from Authorization header (for API clients)
2. Django session cookies (for web UI)

Clients can send `Authorization: Bearer <token>` or rely on session cookies.
"""

from __future__ import annotations

from typing import Any, Iterable, Tuple
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.models import Session
from channels.db import database_sync_to_async
from http.cookies import SimpleCookie

from .authentication import get_user_from_token


class TokenOrSessionAuthMiddleware:
    """ASGI middleware for token-based or session-based WebSocket auth."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict, receive: Any, send: Any) -> Any:
        import logging
        logger = logging.getLogger('webops.websocket.auth')
        
        # Log connection attempt details
        client_ip = scope.get('client', ['unknown', 0])[0]
        path = scope.get('path', 'unknown')
        headers = scope.get("headers", ())
        logger.info(f"WebSocket connection attempt from {client_ip} to {path}")
        logger.debug(f"WebSocket headers: {headers}")

        # Try token authentication first
        token = self._extract_bearer_token(headers)
        
        # Also check for token in query parameters
        if not token:
            token = self._extract_token_from_query(scope)

        if token:
            logger.debug(f"WebSocket connection attempt with token: {token[:10]}...")
            user = await self._get_user_from_token(token)
            if user:
                logger.info(f"WebSocket authenticated via token for user: {user.username}")
                scope["user"] = user
                return await self.inner(scope, receive, send)
            else:
                logger.warning(f"WebSocket authentication failed - invalid token")

        # Fall back to session authentication
        session_key = self._extract_session_key(headers)
        logger.debug(f"Extracted session key: {session_key}")

        if session_key:
            logger.debug(f"WebSocket connection attempt with session cookie: {session_key[:10]}...")
            user = await self._get_user_from_session(session_key)
            if user:
                logger.info(f"WebSocket authenticated via session for user: {user.username}")
                scope["user"] = user
                return await self.inner(scope, receive, send)
            else:
                logger.warning(f"WebSocket authentication failed - invalid session")

        # No valid authentication found
        logger.warning(f"WebSocket connection missing valid authentication (no token or session) from {client_ip}")
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

    @staticmethod
    def _extract_session_key(headers: Iterable[Tuple[bytes, bytes]]) -> str | None:
        """Extract Django session key from Cookie header."""
        for name, value in headers:
            if name.lower() == b"cookie":
                try:
                    cookie_string = value.decode("utf-8")
                    cookies = SimpleCookie(cookie_string)

                    # Try sessionid cookie (default Django session cookie name)
                    if "sessionid" in cookies:
                        return cookies["sessionid"].value
                except Exception:
                    continue
        return None

    @staticmethod
    def _extract_token_from_query(scope: dict) -> str | None:
        """Extract token from query parameters."""
        query_string = scope.get('query_string', b'').decode('utf-8')
        if not query_string:
            return None
            
        # Parse query parameters
        from urllib.parse import parse_qs
        query_params = parse_qs(query_string)
        
        # Get token from query parameters
        token_list = query_params.get('token', [])
        if token_list:
            return token_list[0]
        
        return None

    @database_sync_to_async
    def _get_user_from_token(self, token: str) -> User | None:
        """Get user from API token."""
        return get_user_from_token(token)

    @database_sync_to_async
    def _get_user_from_session(self, session_key: str) -> User | None:
        """Get user from Django session."""
        import logging
        logger = logging.getLogger('webops.websocket.auth')

        try:
            session = Session.objects.get(session_key=session_key)
            logger.debug(f"Found session in database")

            # Check if session is expired
            from django.utils import timezone
            if session.expire_date < timezone.now():
                logger.warning(f"Session expired: {session.expire_date} < {timezone.now()}")
                return None

            # Decode session data to get user_id
            session_data = session.get_decoded()
            logger.debug(f"Session data keys: {list(session_data.keys())}")
            user_id = session_data.get('_auth_user_id')
            logger.debug(f"User ID from session: {user_id}")

            if user_id:
                user = User.objects.get(pk=user_id)
                logger.debug(f"Found user: {user.username}, is_active: {user.is_active}")
                if user.is_active:
                    return user
                else:
                    logger.warning(f"User {user.username} is not active")
            else:
                logger.warning("No _auth_user_id in session data")
        except Session.DoesNotExist:
            logger.warning(f"Session not found in database: {session_key}")
        except User.DoesNotExist:
            logger.warning(f"User not found: {user_id}")
        except KeyError as e:
            logger.warning(f"KeyError in session data: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting user from session: {e}")

        return None


def TokenAuthMiddlewareStack(inner: Any) -> TokenOrSessionAuthMiddleware:
    """Helper to wrap an ASGI app with TokenOrSessionAuthMiddleware."""
    return TokenOrSessionAuthMiddleware(inner)
