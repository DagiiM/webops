"""
Django management command to create an advanced workflow with conditional logic and error handling.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from apps.automation.models import Workflow, WorkflowNode, WorkflowConnection
from apps.automation.validators import WorkflowValidator


class Command(BaseCommand):
    help = 'Create an advanced workflow with conditional logic, error handling, and multiple output paths'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            default=1,
            help='ID of the user to own the workflow (default: 1)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@example.com',
            help='Email address for notifications (default: admin@example.com)'
        )
        parser.add_argument(
            '--webhook-url',
            type=str,
            default='/webhook/order-data',
            help='Webhook URL endpoint (default: /webhook/order-data)'
        )

    def handle(self, *args, **options):
        """Create an advanced workflow with proper validation."""
        
        # Get or create the user
        user_id = options.get('user_id', 1)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            # Create a default admin user if not found
            import secrets
            import string

            # SECURITY FIX: Generate random password instead of hardcoded admin123
            alphabet = string.ascii_letters + string.digits + string.punctuation
            random_password = ''.join(secrets.choice(alphabet) for _ in range(20))

            user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@webops.local',
                    'first_name': 'Admin',
                    'last_name': 'User',
                    'is_staff': True,
                    'is_superuser': True,
                }
            )
            if created:
                user.set_password(random_password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Created default admin user:')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'  Username: admin')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'  Password: {random_password}')
                )
                self.stdout.write(
                    self.style.WARNING('⚠  Save this password! It will not be shown again.')
                )
        
        # Create the workflow
        workflow_name = 'Advanced Order Processing Workflow'
        workflow, created = Workflow.objects.get_or_create(
            name=workflow_name,
            owner=user,
            defaults={
                'description': 'An advanced workflow that processes order data, applies conditional logic, and handles errors gracefully.',
                'status': Workflow.Status.DRAFT,
                'trigger_type': Workflow.TriggerType.WEBHOOK,
                'retry_on_failure': True,
                'max_retries': 3,
                'timeout_seconds': 600,
            }
        )
        
        if not created:
            self.stdout.write(
                self.style.WARNING(f'Workflow "{workflow_name}" already exists. Deleting existing nodes and connections...')
            )
            # Delete existing nodes and connections
            workflow.nodes.all().delete()
            workflow.connections.all().delete()
        
        try:
            # 1. Input Node - Webhook for order data
            webhook_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='order_webhook',
                node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
                label='Order Webhook',
                position_x=100,
                position_y=150,
                config={
                    'endpoint': options['webhook_url'],
                    'method': 'POST',
                    'allowed_methods': ['POST'],
                    'response_type': 'json',
                    'required_fields': ['order_id', 'customer', 'amount', 'items'],
                    'description': 'Receives order data from external system'
                }
            )
            
            # 2. Processor Node - Validate order data
            validate_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='validate_order',
                node_type=WorkflowNode.NodeType.PROCESSOR_FILTER,
                label='Validate Order',
                position_x=300,
                position_y=150,
                config={
                    'filter_type': 'expression',
                    'expression': 'item.order_id and item.customer and item.amount > 0 and item.items',
                    'description': 'Validates that order has required fields and valid amount'
                }
            )
            
            # 3. Control Node - Check order amount
            condition_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='check_amount',
                node_type=WorkflowNode.NodeType.CONTROL_CONDITION,
                label='Check Order Amount',
                position_x=500,
                position_y=150,
                config={
                    'condition': 'amount >= 1000',
                    'description': 'Route orders based on amount threshold'
                }
            )
            
            # 4. Processor Node - Transform high-value order
            transform_high_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='transform_high_value',
                node_type=WorkflowNode.NodeType.PROCESSOR_TRANSFORM,
                label='Transform High Value Order',
                position_x=700,
                position_y=50,
                config={
                    'transform_type': 'jmespath',
                    'query': '{order_id, customer_name: customer.name, customer_email: customer.email, amount, priority: "HIGH", items_count: length(items), processed_at: now()}',
                    'description': 'Transforms high-value orders with priority marking'
                }
            )
            
            # 5. Processor Node - Transform regular order
            transform_regular_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='transform_regular',
                node_type=WorkflowNode.NodeType.PROCESSOR_TRANSFORM,
                label='Transform Regular Order',
                position_x=700,
                position_y=250,
                config={
                    'transform_type': 'jmespath',
                    'query': '{order_id, customer_name: customer.name, customer_email: customer.email, amount, priority: "NORMAL", items_count: length(items), processed_at: now()}',
                    'description': 'Transforms regular orders with standard priority'
                }
            )
            
            # 6. Output Node - Email for high-value orders
            email_high_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='email_high_value',
                node_type=WorkflowNode.NodeType.OUTPUT_EMAIL,
                label='Notify High Value Order',
                position_x=900,
                position_y=50,
                config={
                    'to_emails': [options['email'], 'manager@company.com'],
                    'subject': 'HIGH VALUE ORDER: {{order_id}} - ${{amount}}',
                    'body_template': 'A high-value order requires attention:\n\nOrder ID: {{order_id}}\nCustomer: {{customer_name}} ({{customer_email}})\nAmount: ${{amount}}\nItems: {{items_count}}\nPriority: {{priority}}\nProcessed: {{processed_at}}',
                    'content_type': 'text/html',
                    'description': 'Sends email notification for high-value orders'
                }
            )
            
            # 7. Output Node - Webhook for regular orders
            webhook_regular_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='webhook_regular',
                node_type=WorkflowNode.NodeType.OUTPUT_WEBHOOK,
                label='Process Regular Order',
                position_x=900,
                position_y=250,
                config={
                    'url': 'https://api.external-system.com/orders',
                    'method': 'POST',
                    'headers': {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ${API_TOKEN}'
                    },
                    'description': 'Sends regular order to external processing system'
                }
            )
            
            # 8. Control Node - Error Handler
            error_handler_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='error_handler',
                node_type=WorkflowNode.NodeType.CONTROL_ERROR_HANDLER,
                label='Handle Errors',
                position_x=300,
                position_y=350,
                config={
                    'error_types': ['validation_error', 'timeout', 'api_error'],
                    'retry_logic': {
                        'max_retries': 2,
                        'retry_delay': 30
                    },
                    'description': 'Handles errors from validation and processing'
                }
            )
            
            # 9. Output Node - Error notification
            error_email_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='error_email',
                node_type=WorkflowNode.NodeType.OUTPUT_EMAIL,
                label='Error Notification',
                position_x=500,
                position_y=350,
                config={
                    'to_emails': ['devops@company.com'],
                    'subject': 'Order Processing Error',
                    'body_template': 'An error occurred while processing order:\n\nError: {{error_message}}\nNode: {{failed_node}}\nTimestamp: {{error_time}}\nData: {{order_data}}',
                    'content_type': 'text/plain',
                    'description': 'Sends error notifications to technical team'
                }
            )
            
            self.stdout.write(
                self.style.SUCCESS('Created 9 nodes with conditional logic and error handling')
            )
            
            # Create connections between nodes
            connections = [
                # Main flow
                {
                    'source': webhook_node,
                    'target': validate_node,
                    'id': 'webhook-to-validate'
                },
                {
                    'source': validate_node,
                    'target': condition_node,
                    'id': 'validate-to-condition'
                },
                # High-value order path
                {
                    'source': condition_node,
                    'target': transform_high_node,
                    'id': 'condition-to-high',
                    'condition': {'expression': 'amount >= 1000'}
                },
                {
                    'source': transform_high_node,
                    'target': email_high_node,
                    'id': 'high-transform-to-email'
                },
                # Regular order path
                {
                    'source': condition_node,
                    'target': transform_regular_node,
                    'id': 'condition-to-regular',
                    'condition': {'expression': 'amount < 1000'}
                },
                {
                    'source': transform_regular_node,
                    'target': webhook_regular_node,
                    'id': 'regular-transform-to-webhook'
                },
                # Error handling
                {
                    'source': validate_node,
                    'target': error_handler_node,
                    'id': 'validate-to-error',
                    'condition': {'expression': 'validation_failed == true'}
                },
                {
                    'source': error_handler_node,
                    'target': error_email_node,
                    'id': 'error-handler-to-email'
                }
            ]
            
            for conn_data in connections:
                connection = WorkflowConnection.objects.create(
                    workflow=workflow,
                    source_node=conn_data['source'],
                    target_node=conn_data['target'],
                    source_handle='output',
                    target_handle='input',
                    condition=conn_data.get('condition', {})
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'Created {len(connections)} connections between nodes')
            )
            
            # Update canvas data for visual representation
            workflow.canvas_data = {
                'nodes': [
                    {
                        'id': 'order_webhook',
                        'type': 'webhook',
                        'position': {'x': 100, 'y': 150},
                        'data': {
                            'label': 'Order Webhook',
                            'endpoint': options['webhook_url']
                        }
                    },
                    {
                        'id': 'validate_order',
                        'type': 'filter',
                        'position': {'x': 300, 'y': 150},
                        'data': {
                            'label': 'Validate Order'
                        }
                    },
                    {
                        'id': 'check_amount',
                        'type': 'condition',
                        'position': {'x': 500, 'y': 150},
                        'data': {
                            'label': 'Check Order Amount'
                        }
                    },
                    {
                        'id': 'transform_high_value',
                        'type': 'transform',
                        'position': {'x': 700, 'y': 50},
                        'data': {
                            'label': 'Transform High Value Order'
                        }
                    },
                    {
                        'id': 'transform_regular',
                        'type': 'transform',
                        'position': {'x': 700, 'y': 250},
                        'data': {
                            'label': 'Transform Regular Order'
                        }
                    },
                    {
                        'id': 'email_high_value',
                        'type': 'email',
                        'position': {'x': 900, 'y': 50},
                        'data': {
                            'label': 'Notify High Value Order'
                        }
                    },
                    {
                        'id': 'webhook_regular',
                        'type': 'webhook_output',
                        'position': {'x': 900, 'y': 250},
                        'data': {
                            'label': 'Process Regular Order'
                        }
                    },
                    {
                        'id': 'error_handler',
                        'type': 'error_handler',
                        'position': {'x': 300, 'y': 350},
                        'data': {
                            'label': 'Handle Errors'
                        }
                    },
                    {
                        'id': 'error_email',
                        'type': 'email',
                        'position': {'x': 500, 'y': 350},
                        'data': {
                            'label': 'Error Notification'
                        }
                    }
                ],
                'connections': [
                    {
                        'id': 'webhook-to-validate',
                        'source': 'order_webhook',
                        'target': 'validate_order'
                    },
                    {
                        'id': 'validate-to-condition',
                        'source': 'validate_order',
                        'target': 'check_amount'
                    },
                    {
                        'id': 'condition-to-high',
                        'source': 'check_amount',
                        'target': 'transform_high_value',
                        'animated': True,
                        'style': {'stroke': '#22c55e'}
                    },
                    {
                        'id': 'high-transform-to-email',
                        'source': 'transform_high_value',
                        'target': 'email_high_value'
                    },
                    {
                        'id': 'condition-to-regular',
                        'source': 'check_amount',
                        'target': 'transform_regular',
                        'animated': True,
                        'style': {'stroke': '#3b82f6'}
                    },
                    {
                        'id': 'regular-transform-to-webhook',
                        'source': 'transform_regular',
                        'target': 'webhook_regular'
                    },
                    {
                        'id': 'validate-to-error',
                        'source': 'validate_order',
                        'target': 'error_handler',
                        'style': {'stroke': '#ef4444', 'strokeDasharray': '5 5'}
                    },
                    {
                        'id': 'error-handler-to-email',
                        'source': 'error_handler',
                        'target': 'error_email',
                        'style': {'stroke': '#ef4444', 'strokeDasharray': '5 5'}
                    }
                ]
            }
            workflow.save()
            
            # Validate the workflow
            is_valid, errors = WorkflowValidator.validate_workflow(workflow)
            
            if not is_valid:
                self.stdout.write(
                    self.style.ERROR('Workflow validation failed:')
                )
                for error in errors:
                    self.stdout.write(
                        self.style.ERROR(f'  - {error}')
                    )
                raise CommandError('Workflow validation failed')
            
            self.stdout.write(
                self.style.SUCCESS('✓ Workflow validation passed')
            )
            
            # Display workflow information
            self.stdout.write(
                self.style.SUCCESS('\n=== Advanced Workflow Created Successfully ===')
            )
            self.stdout.write(f'Workflow Name: {workflow.name}')
            self.stdout.write(f'Workflow ID: {workflow.id}')
            self.stdout.write(f'Owner: {workflow.owner.username}')
            self.stdout.write(f'Status: {workflow.get_status_display()}')
            self.stdout.write(f'Trigger Type: {workflow.get_trigger_type_display()}')
            self.stdout.write(f'Max Retries: {workflow.max_retries}')
            self.stdout.write(f'Timeout: {workflow.timeout_seconds} seconds')
            
            self.stdout.write('\nNodes:')
            for node in workflow.nodes.all():
                self.stdout.write(f'  - {node.label} ({node.get_node_type_display()}) - ID: {node.node_id}')
            
            self.stdout.write('\nConnections:')
            for conn in workflow.connections.all():
                condition_text = f" [Condition: {conn.condition}]" if conn.condition else ""
                self.stdout.write(f'  - {conn.source_node.label} → {conn.target_node.label}{condition_text}')
            
            self.stdout.write('\nWebhook Endpoint:')
            self.stdout.write(f'  POST {options["webhook_url"]}')
            
            self.stdout.write('\nSample JSON payload for webhook:')
            self.stdout.write('  {')
            self.stdout.write('    "order_id": "ORD-12345",')
            self.stdout.write('    "customer": {')
            self.stdout.write('      "name": "Jane Smith",')
            self.stdout.write('      "email": "jane@example.com"')
            self.stdout.write('    },')
            self.stdout.write('    "amount": 1500.00,')
            self.stdout.write('    "items": [')
            self.stdout.write('      {"sku": "PROD-001", "quantity": 2, "price": 750.00}')
            self.stdout.write('    ]')
            self.stdout.write('  }')
            
            self.stdout.write('\nWorkflow Logic:')
            self.stdout.write('  1. Receives order data via webhook')
            self.stdout.write('  2. Validates required fields')
            self.stdout.write('  3. Checks if order amount >= $1000')
            self.stdout.write('  4. High-value orders (>= $1000):')
            self.stdout.write('     - Transforms with HIGH priority')
            self.stdout.write('     - Sends email notification')
            self.stdout.write('  5. Regular orders (< $1000):')
            self.stdout.write('     - Transforms with NORMAL priority')
            self.stdout.write('     - Sends to external API')
            self.stdout.write('  6. Error handling:')
            self.stdout.write('     - Catches validation errors')
            self.stdout.write('     - Notifies technical team')
            
            self.stdout.write('\nTo activate this workflow:')
            self.stdout.write(f'  1. Go to the Django admin panel')
            self.stdout.write(f'  2. Find the workflow "{workflow.name}"')
            self.stdout.write(f'  3. Change status to "Active"')
            self.stdout.write(f'  4. Set up the API_TOKEN environment variable for external webhook')
            self.stdout.write(f'  5. Test by sending a POST request to {options["webhook_url"]}')
            
        except Exception as e:
            # Clean up on error
            workflow.delete()
            raise CommandError(f'Failed to create workflow: {str(e)}')