"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from django.conf import settings
from django.urls import re_path
from django.http import HttpResponse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django first
django.setup()

# Now import Django components after setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from apps.api.channels_auth import TokenAuthMiddlewareStack
import apps.deployments.routing
import apps.core.notifications.routing

# Create Django ASGI application
django_asgi_app = get_asgi_application()

# Static file serving for development
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    
    # Wrap the Django ASGI app with ASGIStaticFilesHandler
    django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddlewareStack(
            URLRouter(
                apps.deployments.routing.websocket_urlpatterns +
                apps.core.notifications.routing.websocket_urlpatterns
            )
        )
    ),
})
