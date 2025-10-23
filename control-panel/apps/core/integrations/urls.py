"""
URL configuration for integrations domain.
"""

from django.urls import path
from apps.core.integrations import views

app_name = 'integrations'

urlpatterns = [
    # Dashboard
    path('', views.integrations_dashboard, name='dashboard'),
    
    # GitHub integration
    path('github/connect/', views.github_connect, name='github_connect'),
    path('github/oauth/', views.github_connect_oauth, name='github_connect_oauth'),
    path('github/callback/', views.github_callback, name='github_callback'),
    path('github/disconnect/', views.github_disconnect, name='github_disconnect'),
    path('github/test/', views.github_test, name='github_test'),
    
    # Hugging Face integration
    path('huggingface/connect/', views.huggingface_connect, name='huggingface_connect'),
    path('huggingface/disconnect/', views.huggingface_disconnect, name='huggingface_disconnect'),
    path('huggingface/test/', views.huggingface_test, name='huggingface_test'),
    path('huggingface/models/', views.huggingface_models, name='huggingface_models'),
    
    # Google integration
    path('google/connect/', views.google_connect, name='google_connect'),
    path('google/oauth/', views.google_connect_oauth, name='google_connect_oauth'),
    path('google/callback/', views.google_callback, name='google_callback'),
    path('google/disconnect/', views.google_disconnect, name='google_disconnect'),
    path('google/test/', views.google_test, name='google_test'),
]