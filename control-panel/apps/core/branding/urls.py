"""
URL configuration for branding domain.
"""

from django.urls import path
from apps.core.branding import views

app_name = 'branding'

urlpatterns = [
    path('settings/', views.branding_settings, name='branding_settings'),
    path('reset/', views.reset_branding, name='reset_branding'),
]