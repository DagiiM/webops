from django.urls import path
from . import views

app_name = 'trash'

urlpatterns = [
    # Main trash views
    path('', views.TrashListView.as_view(), name='list'),
    path('<int:pk>/', views.TrashDetailView.as_view(), name='detail'),

    # Item actions
    path('<int:pk>/restore/', views.restore_item, name='restore_item'),
    path('<int:pk>/delete/', views.permanent_delete_item, name='permanent_delete_item'),

    # Bulk operations
    path('bulk/restore/', views.bulk_restore_items, name='bulk_restore'),
    path('bulk/delete/', views.bulk_permanent_delete_items, name='bulk_permanent_delete'),

    # Trash management
    path('empty/', views.empty_trash, name='empty_trash'),

    # API endpoints
    path('api/stats/', views.get_trash_stats_api, name='api_stats'),
    path('api/search/', views.search_trash_api, name='api_search'),

    # Settings (admin only)
    path('settings/', views.TrashSettingsView.as_view(), name='settings'),
]
