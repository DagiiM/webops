"""
URL configuration for WebOps Control Panel.

"URL Routing" section
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from apps.deployments import views as deployment_views
from apps.core.webhooks import views as webhook_views



urlpatterns = [
    path('admin/', admin.site.urls),

    

    # Authentication (modern with 2FA)
    path('auth/', include('apps.core.urls')),

    # Dashboard
    path('', deployment_views.dashboard, name='dashboard'),
    path('dashboard/', deployment_views.dashboard, name='dashboard_alt'),

    # Deployments
    path('deployments/', include(('apps.deployments.urls', 'deployments'))),

    # Databases
    path('databases/', include('apps.databases.urls')),

    # Trash / Recycle Bin
    path('trash/', include('apps.trash.urls')),

    # Monitoring
    path('monitoring/', include(('apps.services.urls', 'monitoring'), namespace='monitoring')),

    # Automation
    path('automation/', include(('apps.automation.urls', 'automation'))),

    # Compliance & Security
    path('compliance/', include(('apps.compliance.urls', 'compliance'))),

    # Addons
    path('addons/', include(('apps.addons.urls', 'addons'))),

    # API
    path('api/', include('apps.api.urls')),

    # Webhook Endpoints (public, no auth required)
    path('webhooks/<str:secret>/', webhook_views.webhook_handler, name='webhook_handler'),
    path('webhooks/<str:secret>/test/', webhook_views.webhook_test, name='webhook_test'),
]

# Error handlers
handler400 = 'apps.core.error_handlers.handler400'
handler403 = 'apps.core.error_handlers.handler403'
handler404 = 'apps.core.error_handlers.handler404'
handler500 = 'apps.core.error_handlers.handler500'

# Serve media files in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
