from django.urls import path
from . import views
from . import api

app_name = 'addons'

# Web UI URLs
urlpatterns = [
    path('', views.addons_list, name='addons_list'),
    path('<str:addon_name>/', views.addon_detail, name='addon_detail'),
    path('<str:addon_name>/toggle/', views.addon_toggle, name='addon_toggle'),
    path('<str:addon_name>/enable/', views.addon_enable, name='addon_enable'),
    path('<str:addon_name>/disable/', views.addon_disable, name='addon_disable'),
    path('<str:addon_name>/toggle-ajax/', views.addon_toggle_ajax, name='addon_toggle_ajax'),
]

# REST API URLs
api_urlpatterns = [
    # Discovery and listing
    path('api/addons/', api.list_addons, name='api_list_addons'),
    path('api/addons/discover/', api.discover_addons, name='api_discover_addons'),
    path('api/addons/stats/', api.get_addon_stats, name='api_addon_stats'),
    path('api/addons/<str:name>/', api.get_addon, name='api_get_addon'),

    # Operations
    path('api/addons/<str:name>/install/', api.install_addon, name='api_install_addon'),
    path('api/addons/<str:name>/uninstall/', api.uninstall_addon, name='api_uninstall_addon'),
    path('api/addons/<str:name>/configure/', api.configure_addon, name='api_configure_addon'),
    path('api/addons/<str:name>/toggle/', api.toggle_addon, name='api_toggle_addon'),

    # Status and health
    path('api/addons/<str:name>/status/', api.get_addon_status, name='api_addon_status'),
    path('api/addons/<str:name>/sync/', api.sync_addon_status, name='api_sync_addon_status'),
    path('api/addons/health-check/', api.health_check_addons, name='api_health_check_addons'),

    # Execution history
    path('api/addons/<str:name>/executions/', api.get_addon_executions, name='api_addon_executions'),
    path('api/executions/<int:execution_id>/', api.get_execution_detail, name='api_execution_detail'),
]

urlpatterns += api_urlpatterns