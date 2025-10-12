"""URL configuration for Databases app."""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.database_list, name='database_list'),
    path('create/', views.database_create, name='database_create'),
    path('<int:pk>/', views.database_detail, name='database_detail'),
    path('<int:pk>/delete/', views.database_delete, name='database_delete'),
    path('<int:pk>/credentials/', views.database_credentials_json, name='database_credentials_json'),
]