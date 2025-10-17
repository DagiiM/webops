from django.urls import path
from . import views

app_name = 'addons'

urlpatterns = [
    path('', views.addons_list, name='list'),
]