"""URL configuration for Databases app."""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.database_list, name='database_list'),
    path('create/', views.DatabaseCreateView.as_view(), name='database_create'),
    path('create-legacy/', views.database_create_legacy, name='database_create_legacy'),
    path('<int:pk>/', views.database_detail, name='database_detail'),
    path('<int:pk>/delete/', views.database_delete, name='database_delete'),
    path('<int:pk>/credentials/', views.database_credentials_json, name='database_credentials_json'),
    path('check-dependencies/', views.check_dependencies, name='check_dependencies'),
    path('<int:pk>/check-dependencies/', views.check_dependencies, name='database_check_dependencies'),
    path('install-dependencies/', views.install_dependencies_ajax, name='install_dependencies_ajax'),
]