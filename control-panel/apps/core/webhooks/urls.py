"""
URL configuration for webhooks domain.
"""

from django.urls import path
from apps.core.webhooks import views

app_name = 'webhooks'

urlpatterns = [
    # Webhook management
    path('', views.webhook_list, name='webhook_list'),
    path('create/', views.webhook_create, name='webhook_create'),
    path('<int:webhook_id>/', views.webhook_detail, name='webhook_detail'),
    path('<int:webhook_id>/toggle/', views.webhook_toggle, name='webhook_toggle'),
    path('<int:webhook_id>/delete/', views.webhook_delete, name='webhook_delete'),
    
    # Webhook endpoints (external)
    path('handler/<str:secret>/', views.webhook_handler, name='webhook_handler'),
    path('test/<str:secret>/', views.webhook_test, name='webhook_test'),
]