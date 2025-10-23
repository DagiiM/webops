from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, Http404, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.urls import reverse
from django.views.generic import ListView, DetailView, View
from django.contrib.auth import get_user_model

from .models import TrashItem, TrashSettings, TrashOperation
from .utils import get_client_ip

User = get_user_model()


class TrashListView(LoginRequiredMixin, ListView):
    """
    Main trash interface showing all deleted items
    """
    model = TrashItem
    template_name = 'trash/list.html'
    context_object_name = 'trash_items'
    paginate_by = 20

    def get_queryset(self):
        queryset = TrashItem.objects.filter(
            deleted_by=self.request.user,
            is_restored=False,
            is_permanently_deleted=False
        )

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(item_name__icontains=search) |
                Q(item_type__icontains=search) |
                Q(original_path__icontains=search)
            )

        # Filter by type
        item_type = self.request.GET.get('type')
        if item_type:
            queryset = queryset.filter(item_type=item_type)

        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        if date_from:
            queryset = queryset.filter(deleted_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(deleted_at__lte=date_to)

        return queryset.order_by('-deleted_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get unique item types for filter dropdown
        context['item_types'] = TrashItem.objects.filter(
            deleted_by=self.request.user,
            is_restored=False,
            is_permanently_deleted=False
        ).values_list('item_type', flat=True).distinct()

        # Get statistics
        context['stats'] = self.get_trash_stats()

        # Preserve search/filter parameters
        context['current_search'] = self.request.GET.get('search', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['current_date_from'] = self.request.GET.get('date_from', '')
        context['current_date_to'] = self.request.GET.get('date_to', '')

        return context

    def get_trash_stats(self):
        """Get trash statistics for the current user"""
        queryset = TrashItem.objects.filter(
            deleted_by=self.request.user,
            is_restored=False,
            is_permanently_deleted=False
        )

        return {
            'total_items': queryset.count(),
            'total_size': queryset.aggregate(Sum('size'))['size__sum'] or 0,
            'expiring_soon': queryset.filter(
                auto_delete_at__lte=timezone.now() + timezone.timedelta(days=3)
            ).count(),
        }


class TrashDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a specific trash item
    """
    model = TrashItem
    template_name = 'trash/detail.html'
    context_object_name = 'trash_item'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.deleted_by != self.request.user:
            raise Http404("Item not found")
        return obj


@login_required
@require_POST
@csrf_protect
def restore_item(request, pk):
    """Restore a single item from trash"""
    item = get_object_or_404(
        TrashItem,
        pk=pk,
        deleted_by=request.user,
        is_restored=False,
        is_permanently_deleted=False
    )

    try:
        item.restore(user=request.user)

        # Log the operation
        operation = TrashOperation.objects.create(
            operation='restore',
            performed_by=request.user,
            items_count=1,
            ip_address=get_client_ip(request)
        )
        operation.items_affected.add(item)

        if request.headers.get('HX-Request'):
            return render(request, 'trash/components/item_restored.html', {'item': item})

        messages.success(request, f'"{item.item_name}" has been restored successfully.')
        return redirect('trash:list')

    except Exception as e:
        if request.headers.get('HX-Request'):
            return HttpResponseBadRequest(f'Error: {str(e)}')

        messages.error(request, f'Failed to restore item: {str(e)}')
        return redirect('trash:list')


@login_required
@require_POST
@csrf_protect
def permanent_delete_item(request, pk):
    """Permanently delete a single item from trash"""
    item = get_object_or_404(
        TrashItem,
        pk=pk,
        deleted_by=request.user,
        is_restored=False,
        is_permanently_deleted=False
    )

    try:
        item.permanent_delete(user=request.user)

        # Log the operation
        operation = TrashOperation.objects.create(
            operation='permanent_delete',
            performed_by=request.user,
            items_count=1,
            ip_address=get_client_ip(request)
        )
        operation.items_affected.add(item)

        if request.headers.get('HX-Request'):
            return render(request, 'trash/components/item_deleted.html', {'item': item})

        messages.success(request, f'"{item.item_name}" has been permanently deleted.')
        return redirect('trash:list')

    except Exception as e:
        if request.headers.get('HX-Request'):
            return HttpResponseBadRequest(f'Error: {str(e)}')

        messages.error(request, f'Failed to delete item: {str(e)}')
        return redirect('trash:list')


@login_required
@require_POST
@csrf_protect
def bulk_restore_items(request):
    """Restore multiple items from trash"""
    item_ids = request.POST.getlist('item_ids')

    if not item_ids:
        messages.error(request, 'No items selected for restoration.')
        return redirect('trash:list')

    try:
        items = TrashItem.objects.filter(
            id__in=item_ids,
            deleted_by=request.user,
            is_restored=False,
            is_permanently_deleted=False
        )

        restored_count = 0
        for item in items:
            item.restore(user=request.user)
            restored_count += 1

        # Log the operation
        operation = TrashOperation.objects.create(
            operation='bulk_restore',
            performed_by=request.user,
            items_count=restored_count,
            details={'item_ids': item_ids},
            ip_address=get_client_ip(request)
        )
        operation.items_affected.set(items)

        messages.success(request, f'{restored_count} items restored successfully.')
        return redirect('trash:list')

    except Exception as e:
        messages.error(request, f'Failed to restore items: {str(e)}')
        return redirect('trash:list')


@login_required
@require_POST
@csrf_protect
def bulk_permanent_delete_items(request):
    """Permanently delete multiple items from trash"""
    item_ids = request.POST.getlist('item_ids')

    if not item_ids:
        messages.error(request, 'No items selected for deletion.')
        return redirect('trash:list')

    try:
        items = TrashItem.objects.filter(
            id__in=item_ids,
            deleted_by=request.user,
            is_restored=False,
            is_permanently_deleted=False
        )

        deleted_count = 0
        for item in items:
            item.permanent_delete(user=request.user)
            deleted_count += 1

        # Log the operation
        operation = TrashOperation.objects.create(
            operation='bulk_permanent_delete',
            performed_by=request.user,
            items_count=deleted_count,
            details={'item_ids': item_ids},
            ip_address=get_client_ip(request)
        )
        operation.items_affected.set(items)

        messages.success(request, f'{deleted_count} items permanently deleted.')
        return redirect('trash:list')

    except Exception as e:
        messages.error(request, f'Failed to delete items: {str(e)}')
        return redirect('trash:list')


@login_required
@require_POST
@csrf_protect
def empty_trash(request):
    """Empty entire trash (permanent delete all items)"""
    try:
        items = TrashItem.objects.filter(
            deleted_by=request.user,
            is_restored=False,
            is_permanently_deleted=False
        )

        count = items.count()
        if count == 0:
            messages.info(request, 'Trash is already empty.')
            return redirect('trash:list')

        # Permanently delete all items
        for item in items:
            item.permanent_delete(user=request.user)

        # Log the operation
        operation = TrashOperation.objects.create(
            operation='empty_trash',
            performed_by=request.user,
            items_count=count,
            ip_address=get_client_ip(request)
        )
        operation.items_affected.set(items)

        messages.success(request, f'All {count} items permanently deleted from trash.')
        return redirect('trash:list')

    except Exception as e:
        messages.error(request, f'Failed to empty trash: {str(e)}')
        return redirect('trash:list')


@login_required
def get_trash_stats_api(request):
    """API endpoint for trash statistics"""
    try:
        stats = TrashListView().get_trash_stats()
        return JsonResponse({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def search_trash_api(request):
    """API endpoint for trash search with HTMX"""
    query = request.GET.get('q', '')
    page = int(request.GET.get('page', 1))

    if not query:
        return JsonResponse({'error': 'No search query provided'})

    # Simple search implementation
    items = TrashItem.objects.filter(
        deleted_by=request.user,
        is_restored=False,
        is_permanently_deleted=False,
        item_name__icontains=query
    ).order_by('-deleted_at')

    paginator = Paginator(items, 10)
    page_obj = paginator.get_page(page)

    context = {
        'trash_items': page_obj,
        'query': query,
        'is_search': True
    }

    html = render(request, 'trash/components/search_results.html', context).content.decode()

    return JsonResponse({
        'success': True,
        'html': html,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'current_page': page,
        'total_pages': paginator.num_pages
    })


class TrashSettingsView(LoginRequiredMixin, View):
    """
    View for managing trash settings (admin only)
    """

    def get(self, request):
        if not request.user.is_staff:
            raise Http404("Settings not found")

        settings, created = TrashSettings.objects.get_or_create(pk=1)

        context = {
            'settings': settings,
            'title': 'Trash Settings'
        }

        return render(request, 'trash/settings.html', context)

    def post(self, request):
        if not request.user.is_staff:
            raise Http404("Settings not found")

        settings, created = TrashSettings.objects.get_or_create(pk=1)

        try:
            settings.default_retention_days = int(request.POST.get('default_retention_days', 30))
            settings.max_retention_days = int(request.POST.get('max_retention_days', 90))
            settings.max_trash_size_gb = int(request.POST.get('max_trash_size_gb', 10))
            settings.enable_auto_cleanup = request.POST.get('enable_auto_cleanup') == 'on'
            settings.cleanup_schedule_hours = int(request.POST.get('cleanup_schedule_hours', 24))
            settings.notify_before_deletion_days = int(request.POST.get('notify_before_deletion_days', 7))

            settings.save()

            messages.success(request, 'Trash settings updated successfully.')
            return redirect('trash:settings')

        except Exception as e:
            messages.error(request, f'Failed to update settings: {str(e)}')
            return redirect('trash:settings')
