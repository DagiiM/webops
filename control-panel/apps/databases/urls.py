"""URL configuration for Databases app."""

from django.urls import path, re_path
from . import views, managed_views

urlpatterns = [
    path('', views.database_list, name='database_list'),
    path('deploy/', managed_views.database_deploy, name='database_deploy'),
    path('<int:pk>/status/', managed_views.database_status, name='database_status'),
    path('create/', views.DatabaseCreateView.as_view(), name='database_create'),
    path('<int:pk>/', views.database_detail, name='database_detail'),
    path('<int:pk>/edit/', views.database_update, name='database_update'),
    path('<int:pk>/delete/', views.database_delete, name='database_delete'),
    path('<int:pk>/credentials/', views.database_credentials_json, name='database_credentials_json'),
    path('check-dependencies/', views.check_dependencies, name='check_dependencies'),
    path('<int:pk>/check-dependencies/', views.check_dependencies, name='database_check_dependencies'),
    path('install-dependencies/', views.install_dependencies_ajax, name='install_dependencies_ajax'),
    re_path(r'^(?P<pk>\d+)/(?P<action>start|stop|restart|check)/$', managed_views.database_action, name='database_action'),
]