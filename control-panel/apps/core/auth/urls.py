"""
URL configuration for authentication module.

Includes login, registration, password reset, and 2FA endpoints.
"""

from django.urls import path
from . import views

app_name = 'auth'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Password reset
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),

    # Two-Factor Authentication
    path('2fa/setup/', views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
    path('2fa/disable/', views.two_factor_disable, name='two_factor_disable'),
]
