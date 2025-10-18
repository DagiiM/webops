"""
WebSocket Routing for KVM Addon

Configures WebSocket URLs for VNC console access.
"""

from django.urls import re_path
from . import vnc_proxy

websocket_urlpatterns = [
    re_path(
        r'ws/vnc/(?P<deployment_id>\d+)/$',
        vnc_proxy.VNCProxyConsumer.as_asgi()
    ),
]
