"""
URL Configuration for KVM Addon
"""

from django.urls import path
from . import views

app_name = 'kvm'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.vm_dashboard, name='dashboard'),

    # Console
    path('console/<int:deployment_id>/', views.vm_console, name='console'),

    # VM Control API
    path('api/vm/<int:deployment_id>/start/', views.vm_start, name='vm_start'),
    path('api/vm/<int:deployment_id>/stop/', views.vm_stop, name='vm_stop'),
    path('api/vm/<int:deployment_id>/restart/', views.vm_restart, name='vm_restart'),
    path('api/vm/<int:deployment_id>/state/', views.vm_state, name='vm_state'),

    # Snapshot API
    path('api/vm/<int:deployment_id>/snapshots/', views.vm_snapshots_list, name='snapshots_list'),
    path('api/vm/<int:deployment_id>/snapshots/create/', views.vm_snapshot_create, name='snapshot_create'),
    path('api/vm/<int:deployment_id>/snapshots/<int:snapshot_id>/restore/', views.vm_snapshot_restore, name='snapshot_restore'),
    path('api/vm/<int:deployment_id>/snapshots/<int:snapshot_id>/delete/', views.vm_snapshot_delete, name='snapshot_delete'),
]
