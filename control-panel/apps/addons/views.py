from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Addon

@login_required
def addons_list(request):
    addons = Addon.objects.all().order_by('name')
    return render(request, 'addons/list.html', {'addons': addons})