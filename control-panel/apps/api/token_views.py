"""
Views for API Token management UI.

Reference: CLAUDE.md "Django App Structure" section
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import APIToken


@login_required
def token_list(request):
    """List all API tokens for the current user."""
    tokens = APIToken.objects.filter(user=request.user)

    # Get statistics
    stats = {
        'total': tokens.count(),
        'active': tokens.filter(is_active=True).count(),
        'inactive': tokens.filter(is_active=False).count(),
        'expired': tokens.filter(expires_at__lt=timezone.now()).count(),
    }

    return render(request, 'api/token_list.html', {
        'tokens': tokens,
        'stats': stats
    })


@login_required
def token_create(request):
    """Create new API token."""
    if request.method == 'POST':
        name = request.POST.get('name')
        expires_days = request.POST.get('expires_days')

        if name:
            # Create token
            token = APIToken.objects.create(
                user=request.user,
                name=name
            )

            # Set expiration if provided
            if expires_days:
                try:
                    days = int(expires_days)
                    token.expires_at = timezone.now() + timezone.timedelta(days=days)
                    token.save()
                except ValueError:
                    pass

            messages.success(request, f'API token "{name}" created successfully!')
            return redirect('token_detail', pk=token.pk)
        else:
            messages.error(request, 'Token name is required')

    return render(request, 'api/token_create.html')


@login_required
def token_detail(request, pk):
    """Show API token details."""
    token = get_object_or_404(APIToken, pk=pk, user=request.user)

    # Check if token is expired
    is_expired = False
    if token.expires_at:
        is_expired = token.expires_at < timezone.now()

    return render(request, 'api/token_detail.html', {
        'token': token,
        'is_expired': is_expired
    })


@login_required
def token_toggle(request, pk):
    """Toggle token active status."""
    token = get_object_or_404(APIToken, pk=pk, user=request.user)

    if request.method == 'POST':
        token.is_active = not token.is_active
        token.save()

        status = 'activated' if token.is_active else 'deactivated'
        messages.success(request, f'Token "{token.name}" {status} successfully')

    return redirect('token_detail', pk=pk)


@login_required
def token_delete(request, pk):
    """Delete API token."""
    token = get_object_or_404(APIToken, pk=pk, user=request.user)

    if request.method == 'POST':
        token_name = token.name
        token.delete()

        messages.success(request, f'Token "{token_name}" deleted successfully')
        return redirect('token_list')

    return render(request, 'api/token_delete_confirm.html', {
        'token': token
    })