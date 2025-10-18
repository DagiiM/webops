"""
KVM Addon Views

API endpoints and views for VM console access and management.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import VMDeployment, VMSnapshot
from .deployment_service import KVMDeploymentService
from .vnc_proxy import VNCTokenAuth
import logging

logger = logging.getLogger(__name__)


@login_required
def vm_console(request, deployment_id):
    """
    Render VM console page with noVNC viewer.

    Args:
        deployment_id: Deployment ID

    Returns:
        HTML page with embedded noVNC client
    """
    vm_deployment = get_object_or_404(
        VMDeployment.objects.select_related('deployment', 'compute_node'),
        deployment_id=deployment_id
    )

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden("You don't have access to this VM console")

    # Generate VNC access token
    vnc_token = VNCTokenAuth.generate_token(vm_deployment, request.user)

    # Get WebSocket URL
    ws_scheme = 'wss' if request.is_secure() else 'ws'
    ws_url = f"{ws_scheme}://{request.get_host()}/ws/vnc/{deployment_id}/"

    context = {
        'vm_deployment': vm_deployment,
        'deployment': vm_deployment.deployment,
        'ws_url': ws_url,
        'vnc_token': vnc_token,
        'vm_name': vm_deployment.vm_name,
        'vm_state': vm_deployment.libvirt_state,
    }

    return render(request, 'kvm/console.html', context)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vm_start(request, deployment_id):
    """Start a stopped VM."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    service = KVMDeploymentService()
    success = service.start_vm(vm_deployment)

    if success:
        return Response({
            'success': True,
            'state': vm_deployment.libvirt_state,
            'message': 'VM started successfully'
        })
    else:
        return Response({
            'success': False,
            'error': 'Failed to start VM'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vm_stop(request, deployment_id):
    """Stop a running VM."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    force = request.data.get('force', False)

    service = KVMDeploymentService()
    success = service.stop_vm(vm_deployment, force=force)

    if success:
        return Response({
            'success': True,
            'state': vm_deployment.libvirt_state,
            'message': 'VM stopped successfully'
        })
    else:
        return Response({
            'success': False,
            'error': 'Failed to stop VM'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vm_restart(request, deployment_id):
    """Restart a VM."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    service = KVMDeploymentService()
    success = service.restart_vm(vm_deployment)

    if success:
        return Response({
            'success': True,
            'message': 'VM restarted successfully'
        })
    else:
        return Response({
            'success': False,
            'error': 'Failed to restart VM'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vm_state(request, deployment_id):
    """Get current VM state."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    service = KVMDeploymentService()
    state = service.update_vm_state(vm_deployment)

    return Response({
        'state': state,
        'ip_address': vm_deployment.ip_address,
        'ssh_port': vm_deployment.ssh_port,
        'ssh_command': vm_deployment.get_ssh_command(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vm_snapshots_list(request, deployment_id):
    """List all snapshots for a VM."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    snapshots = VMSnapshot.objects.filter(
        vm_deployment=vm_deployment,
        is_active=True
    ).order_by('-created_at')

    data = [
        {
            'id': snap.id,
            'name': snap.name,
            'description': snap.description,
            'disk_size_mb': snap.disk_size_mb,
            'created_at': snap.created_at.isoformat(),
        }
        for snap in snapshots
    ]

    return Response({'snapshots': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vm_snapshot_create(request, deployment_id):
    """Create a new VM snapshot."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    snapshot_name = request.data.get('name')
    description = request.data.get('description', '')

    if not snapshot_name:
        return Response({'error': 'Snapshot name is required'}, status=status.HTTP_400_BAD_REQUEST)

    service = KVMDeploymentService()
    success = service.create_snapshot(vm_deployment, snapshot_name, description)

    if success:
        return Response({
            'success': True,
            'message': 'Snapshot created successfully'
        })
    else:
        return Response({
            'success': False,
            'error': 'Failed to create snapshot'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vm_snapshot_restore(request, deployment_id, snapshot_id):
    """Restore VM to a snapshot."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)
    snapshot = get_object_or_404(VMSnapshot, id=snapshot_id, vm_deployment=vm_deployment)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    from .libvirt_manager import LibvirtManager

    try:
        with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
            success = mgr.restore_snapshot(vm_deployment.vm_name, snapshot.name)

        if success:
            return Response({
                'success': True,
                'message': f'Restored to snapshot: {snapshot.name}'
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to restore snapshot'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Snapshot restore error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def vm_snapshot_delete(request, deployment_id, snapshot_id):
    """Delete a snapshot."""
    vm_deployment = get_object_or_404(VMDeployment, deployment_id=deployment_id)
    snapshot = get_object_or_404(VMSnapshot, id=snapshot_id, vm_deployment=vm_deployment)

    # Check authorization
    if vm_deployment.deployment.user != request.user and not request.user.is_staff:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    from .libvirt_manager import LibvirtManager

    try:
        with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
            success = mgr.delete_snapshot(vm_deployment.vm_name, snapshot.name)

        if success:
            snapshot.delete()
            return Response({
                'success': True,
                'message': 'Snapshot deleted successfully'
            })
        else:
            return Response({
                'success': False,
                'error': 'Failed to delete snapshot'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Snapshot delete error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@login_required
def vm_dashboard(request):
    """
    User-facing VM dashboard showing all VMs.
    """
    vms = VMDeployment.objects.filter(
        deployment__user=request.user
    ).select_related(
        'deployment',
        'compute_node',
        'vm_plan',
        'os_template'
    ).order_by('-created_at')

    context = {
        'vms': vms,
    }

    return render(request, 'kvm/dashboard.html', context)
