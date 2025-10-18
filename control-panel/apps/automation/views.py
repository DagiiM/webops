"""
Automation Workflow Views.

Provides web interface and API endpoints for:
- Workflow management (CRUD)
- Visual workflow builder
- Workflow execution
- Execution history and monitoring
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
import json

from .models import (
    Workflow,
    WorkflowNode,
    WorkflowConnection,
    WorkflowExecution,
    WorkflowTemplate,
    DataSourceCredential
)
from .engine import workflow_engine


# =============================================================================
# WORKFLOW MANAGEMENT VIEWS
# =============================================================================

@login_required
def workflow_list(request):
    """List all workflows."""
    workflows = Workflow.objects.filter(
        owner=request.user
    ).order_by('-updated_at')

    # Get execution statistics
    workflow_stats = []
    for workflow in workflows:
        recent_executions = workflow.executions.all()[:5]
        workflow_stats.append({
            'workflow': workflow,
            'recent_executions': recent_executions,
            'node_count': workflow.nodes.count(),
            'connection_count': workflow.connections.count()
        })

    context = {
        'workflow_stats': workflow_stats,
        'total_workflows': workflows.count(),
        'active_workflows': workflows.filter(status=Workflow.Status.ACTIVE).count(),
    }

    return render(request, 'automation/workflow_list.html', context)


@login_required
def workflow_create(request):
    """Create new workflow."""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        trigger_type = request.POST.get('trigger_type', Workflow.TriggerType.MANUAL)

        workflow = Workflow.objects.create(
            name=name,
            description=description,
            owner=request.user,
            trigger_type=trigger_type,
            status=Workflow.Status.DRAFT
        )

        messages.success(request, f'Workflow "{name}" created successfully')
        return redirect('automation:workflow_builder', workflow_id=workflow.id)

    # Load templates for quick start
    templates = WorkflowTemplate.objects.filter(
        Q(is_public=True) | Q(author=request.user)
    ).order_by('-usage_count')[:10]

    context = {
        'templates': templates,
    }

    return render(request, 'automation/workflow_create.html', context)


@login_required
def workflow_builder(request, workflow_id):
    """Visual workflow builder interface."""
    workflow = get_object_or_404(Workflow, pk=workflow_id, owner=request.user)

    # Get all nodes and connections
    nodes = list(workflow.nodes.all())
    connections = list(workflow.connections.all())

    # Serialize for frontend
    nodes_data = [
        {
            'id': node.node_id,
            'type': node.node_type,
            'label': node.label,
            'position': {'x': node.position_x, 'y': node.position_y},
            'config': node.config,
            'enabled': node.enabled,
        }
        for node in nodes
    ]

    connections_data = [
        {
            'id': f"{conn.source_node.node_id}-{conn.target_node.node_id}",
            'source': conn.source_node.node_id,
            'target': conn.target_node.node_id,
            'sourceHandle': conn.source_handle,
            'targetHandle': conn.target_handle,
        }
        for conn in connections
    ]

    context = {
        'workflow': workflow,
        'nodes': json.dumps(nodes_data),
        'connections': json.dumps(connections_data),
        'node_types': WorkflowNode.NodeType.choices,
    }

    return render(request, 'automation/workflow_builder.html', context)


@login_required
@require_POST
def workflow_save(request, workflow_id):
    """Save workflow changes."""
    workflow = get_object_or_404(Workflow, pk=workflow_id, owner=request.user)

    try:
        data = json.loads(request.body)

        # Update workflow metadata
        if 'name' in data:
            workflow.name = data['name']
        if 'description' in data:
            workflow.description = data['description']
        if 'status' in data:
            workflow.status = data['status']

        # Save canvas data
        workflow.canvas_data = data.get('canvas_data', {})
        workflow.save()

        # Update nodes
        if 'nodes' in data:
            # Delete removed nodes
            existing_node_ids = set(workflow.nodes.values_list('node_id', flat=True))
            new_node_ids = set(node['id'] for node in data['nodes'])
            removed_ids = existing_node_ids - new_node_ids

            workflow.nodes.filter(node_id__in=removed_ids).delete()

            # Create or update nodes
            for node_data in data['nodes']:
                node, created = WorkflowNode.objects.update_or_create(
                    workflow=workflow,
                    node_id=node_data['id'],
                    defaults={
                        'node_type': node_data['type'],
                        'label': node_data.get('label', node_data['type']),
                        'position_x': node_data.get('position', {}).get('x', 0),
                        'position_y': node_data.get('position', {}).get('y', 0),
                        'config': node_data.get('config', {}),
                        'enabled': node_data.get('enabled', True),
                    }
                )

        # Update connections
        if 'connections' in data:
            # Delete all existing connections and recreate
            workflow.connections.all().delete()

            for conn_data in data['connections']:
                source_node = workflow.nodes.get(node_id=conn_data['source'])
                target_node = workflow.nodes.get(node_id=conn_data['target'])

                WorkflowConnection.objects.create(
                    workflow=workflow,
                    source_node=source_node,
                    target_node=target_node,
                    source_handle=conn_data.get('sourceHandle', 'output'),
                    target_handle=conn_data.get('targetHandle', 'input'),
                )

        return JsonResponse({
            'success': True,
            'message': 'Workflow saved successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_POST
def workflow_execute(request, workflow_id):
    """Execute a workflow."""
    workflow = get_object_or_404(Workflow, pk=workflow_id, owner=request.user)

    if workflow.status == Workflow.Status.DISABLED:
        return JsonResponse({
            'success': False,
            'error': 'Workflow is disabled'
        }, status=400)

    try:
        # Get input data from request
        if request.content_type == 'application/json':
            input_data = json.loads(request.body)
        else:
            input_data = dict(request.POST)

        # Execute workflow
        execution = workflow_engine.execute_workflow(
            workflow=workflow,
            input_data=input_data,
            triggered_by=request.user,
            trigger_type='manual'
        )

        return JsonResponse({
            'success': True,
            'execution_id': execution.id,
            'status': execution.status,
            'message': 'Workflow execution started'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def workflow_delete(request, workflow_id):
    """Delete a workflow."""
    workflow = get_object_or_404(Workflow, pk=workflow_id, owner=request.user)

    workflow_name = workflow.name
    workflow.delete()

    messages.success(request, f'Workflow "{workflow_name}" deleted successfully')
    return redirect('automation:workflow_list')


# =============================================================================
# EXECUTION MONITORING VIEWS
# =============================================================================

@login_required
def execution_list(request, workflow_id):
    """List workflow executions."""
    workflow = get_object_or_404(Workflow, pk=workflow_id, owner=request.user)

    executions = workflow.executions.order_by('-started_at')[:50]

    context = {
        'workflow': workflow,
        'executions': executions,
    }

    return render(request, 'automation/execution_list.html', context)


@login_required
def execution_detail(request, execution_id):
    """View execution details."""
    execution = get_object_or_404(WorkflowExecution, pk=execution_id)

    # Check permission
    if execution.workflow.owner != request.user:
        messages.error(request, 'Permission denied')
        return redirect('automation:workflow_list')

    context = {
        'execution': execution,
        'workflow': execution.workflow,
    }

    return render(request, 'automation/execution_detail.html', context)


# =============================================================================
# TEMPLATE VIEWS
# =============================================================================

@login_required
def template_list(request):
    """List workflow templates."""
    templates = WorkflowTemplate.objects.filter(
        Q(is_public=True) | Q(author=request.user)
    ).order_by('category', '-usage_count')

    context = {
        'templates': templates,
    }

    return render(request, 'automation/template_list.html', context)


@login_required
def template_preview(request, template_id):
    """Get template preview data for modal."""
    template = get_object_or_404(WorkflowTemplate, pk=template_id)
    
    # Check if template is public or owned by user
    if not template.is_public and template.author != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Template not accessible'
        }, status=403)
    
    # Generate preview HTML
    workflow_data = template.workflow_data
    nodes = workflow_data.get('nodes', [])
    connections = workflow_data.get('connections', [])
    
    # Create a visual representation of the workflow
    preview_html = f"""
    <div class="template-preview-content">
        <div class="template-description">
            <p>{template.description}</p>
        </div>
        
        <div class="workflow-summary">
            <div class="summary-stats">
                <div class="stat-item">
                    <span class="stat-number">{len(nodes)}</span>
                    <span class="stat-label">Nodes</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{len(connections)}</span>
                    <span class="stat-label">Connections</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{template.usage_count}</span>
                    <span class="stat-label">Uses</span>
                </div>
            </div>
        </div>
        
        <div class="workflow-nodes">
            <h4>Workflow Components:</h4>
            <div class="node-list">
    """
    
    # Add node information
    for node in nodes:
        node_type = node.get('type', 'unknown')
        node_label = node.get('label', 'Unnamed Node')
        preview_html += f"""
                <div class="node-preview">
                    <span class="node-type-badge node-type-{node_type}">{node_type.title()}</span>
                    <span class="node-label">{node_label}</span>
                </div>
        """
    
    preview_html += """
            </div>
        </div>
    </div>
    """
    
    return JsonResponse({
        'success': True,
        'name': template.name,
        'category': template.get_category_display(),
        'description': template.description,
        'html': preview_html,
        'usage_count': template.usage_count,
        'author': template.author.username if template.author else 'System'
    })


@login_required
@require_POST
def workflow_create_from_template(request, template_id):
    """Create workflow from template."""
    template = get_object_or_404(WorkflowTemplate, pk=template_id)

    # Check if template is public or owned by user
    if not template.is_public and template.author != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Template not accessible'
        }, status=403)

    try:
        # Create workflow from template
        workflow_data = template.workflow_data

        workflow = Workflow.objects.create(
            name=f"{template.name} (Copy)",
            description=template.description,
            owner=request.user,
            trigger_type=workflow_data.get('trigger_type', Workflow.TriggerType.MANUAL),
            status=Workflow.Status.DRAFT,
            canvas_data=workflow_data.get('canvas_data', {})
        )

        # Create nodes
        node_map = {}  # Map template node IDs to new node IDs
        for node_data in workflow_data.get('nodes', []):
            node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id=node_data['id'],
                node_type=node_data['type'],
                label=node_data['label'],
                position_x=node_data.get('position', {}).get('x', 0),
                position_y=node_data.get('position', {}).get('y', 0),
                config=node_data.get('config', {}),
                enabled=node_data.get('enabled', True)
            )
            node_map[node_data['id']] = node

        # Create connections
        for conn_data in workflow_data.get('connections', []):
            WorkflowConnection.objects.create(
                workflow=workflow,
                source_node=node_map[conn_data['source']],
                target_node=node_map[conn_data['target']],
                source_handle=conn_data.get('sourceHandle', 'output'),
                target_handle=conn_data.get('targetHandle', 'input')
            )

        # Update template usage count
        template.usage_count += 1
        template.save()

        return JsonResponse({
            'success': True,
            'workflow_id': workflow.id,
            'message': 'Workflow created from template'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def api_workflow_status(request, workflow_id):
    """API: Get workflow status and statistics."""
    workflow = get_object_or_404(Workflow, pk=workflow_id, owner=request.user)

    data = {
        'id': workflow.id,
        'name': workflow.name,
        'status': workflow.status,
        'trigger_type': workflow.trigger_type,
        'total_executions': workflow.total_executions,
        'successful_executions': workflow.successful_executions,
        'failed_executions': workflow.failed_executions,
        'success_rate': (
            (workflow.successful_executions / workflow.total_executions * 100)
            if workflow.total_executions > 0 else 0
        ),
        'average_duration_ms': workflow.average_duration_ms,
        'last_executed_at': workflow.last_executed_at.isoformat() if workflow.last_executed_at else None,
        'node_count': workflow.nodes.count(),
        'connection_count': workflow.connections.count(),
    }

    return JsonResponse(data)


@login_required
@require_http_methods(["GET"])
def api_execution_status(request, execution_id):
    """API: Get execution status."""
    execution = get_object_or_404(WorkflowExecution, pk=execution_id)

    # Check permission
    if execution.workflow.owner != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    data = {
        'id': execution.id,
        'workflow_id': execution.workflow.id,
        'status': execution.status,
        'started_at': execution.started_at.isoformat(),
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration_ms': execution.duration_ms,
        'trigger_type': execution.trigger_type,
        'error_message': execution.error_message,
        'node_logs': execution.node_logs,
    }

    return JsonResponse(data)


@login_required
@require_http_methods(["GET"])
def api_node_types(request):
    """API: Get available node types."""
    node_types = {
        'data_sources': [
            {'value': choice[0], 'label': choice[1]}
            for choice in WorkflowNode.NodeType.choices
            if choice[0].startswith('DATA_SOURCE_')
        ],
        'processors': [
            {'value': choice[0], 'label': choice[1]}
            for choice in WorkflowNode.NodeType.choices
            if choice[0].startswith('PROCESSOR_')
        ],
        'outputs': [
            {'value': choice[0], 'label': choice[1]}
            for choice in WorkflowNode.NodeType.choices
            if choice[0].startswith('OUTPUT_')
        ],
        'control': [
            {'value': choice[0], 'label': choice[1]}
            for choice in WorkflowNode.NodeType.choices
            if choice[0].startswith('CONTROL_')
        ],
    }

    return JsonResponse(node_types)
