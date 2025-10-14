"""
WebSocket routing for deployment-related real-time updates.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/deployments/$', consumers.DeploymentConsumer.as_asgi()),
    re_path(r'ws/deployments/(?P<deployment_id>\w+)/$', consumers.DeploymentStatusConsumer.as_asgi()),
]