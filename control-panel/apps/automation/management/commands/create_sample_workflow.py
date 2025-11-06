"""
Django management command to create a sample workflow with input, processor, and output nodes.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from apps.automation.models import Workflow, WorkflowNode, WorkflowConnection
from apps.automation.validators import WorkflowValidator


class Command(BaseCommand):
    help = 'Create a sample workflow with webhook input, transform processor, and email output nodes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID of the user to own the workflow (default: 1)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@example.com',
            help='Email address for the output node (default: admin@example.com)'
        )
        parser.add_argument(
            '--webhook-url',
            type=str,
            default='/webhook/sample-data',
            help='Webhook URL endpoint (default: /webhook/sample-data)'
        )

    def handle(self, *args, **options):
        """Create a sample workflow with proper validation."""
        
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
        workflow_name = 'Sample Data Processing Workflow'
        workflow, created = Workflow.objects.get_or_create(
            name=workflow_name,
            owner=user,
            defaults={
                'description': 'A sample workflow that receives data via webhook, transforms it using JMESPath, and sends it via email.',
                'status': Workflow.Status.DRAFT,
                'trigger_type': Workflow.TriggerType.WEBHOOK,
            }
        )
        
        if not created:
            self.stdout.write(
                self.style.WARNING(f'Workflow "{workflow_name}" already exists. Deleting existing nodes and connections...')
            )
            # Delete existing nodes and connections
            workflow.nodes.all().delete()
            workflow.connections.all().delete()
        
        # Create nodes
        try:
            # 1. Input Node - Webhook
            webhook_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='webhook_input',
                node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
                label='Webhook Input',
                position_x=100,
                position_y=100,
                config={
                    'endpoint': options['webhook_url'],
                    'method': 'POST',
                    'allowed_methods': ['POST'],
                    'response_type': 'json',
                    'description': 'Receives JSON data via webhook'
                }
            )
            
            # 2. Processor Node - Transform with JMESPath
            transform_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='transform_processor',
                node_type=WorkflowNode.NodeType.PROCESSOR_TRANSFORM,
                label='Transform Data',
                position_x=300,
                position_y=100,
                config={
                    'transform_type': 'jmespath',
                    'query': '{name: user.name, email: user.email, timestamp: created_at, processed: true}',
                    'description': 'Extracts and transforms user data using JMESPath'
                }
            )
            
            # 3. Output Node - Email
            email_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_id='email_output',
                node_type=WorkflowNode.NodeType.OUTPUT_EMAIL,
                label='Send Email',
                position_x=500,
                position_y=100,
                config={
                    'to_emails': [options['email']],
                    'subject': 'Processed Data from Webhook',
                    'body_template': 'The following data was processed:\n\nName: {{name}}\nEmail: {{email}}\nTimestamp: {{timestamp}}\nProcessed: {{processed}}',
                    'content_type': 'text/plain',
                    'description': 'Sends the transformed data via email'
                }
            )
            
            self.stdout.write(
                self.style.SUCCESS('Created 3 nodes: webhook_input, transform_processor, email_output')
            )
            
            # Create connections between nodes
            # Connection 1: Webhook -> Transform
            connection1 = WorkflowConnection.objects.create(
                workflow=workflow,
                source_node=webhook_node,
                target_node=transform_node,
                source_handle='output',
                target_handle='input'
            )
            
            # Connection 2: Transform -> Email
            connection2 = WorkflowConnection.objects.create(
                workflow=workflow,
                source_node=transform_node,
                target_node=email_node,
                source_handle='output',
                target_handle='input'
            )
            
            self.stdout.write(
                self.style.SUCCESS('Created 2 connections between nodes')
            )
            
            # Update canvas data for visual representation
            workflow.canvas_data = {
                'nodes': [
                    {
                        'id': 'webhook_input',
                        'type': 'webhook',
                        'position': {'x': 100, 'y': 100},
                        'data': {
                            'label': 'Webhook Input',
                            'endpoint': options['webhook_url']
                        }
                    },
                    {
                        'id': 'transform_processor',
                        'type': 'transform',
                        'position': {'x': 300, 'y': 100},
                        'data': {
                            'label': 'Transform Data',
                            'query': '{name: user.name, email: user.email, timestamp: created_at, processed: true}'
                        }
                    },
                    {
                        'id': 'email_output',
                        'type': 'email',
                        'position': {'x': 500, 'y': 100},
                        'data': {
                            'label': 'Send Email',
                            'to': options['email']
                        }
                    }
                ],
                'connections': [
                    {
                        'id': 'webhook-to-transform',
                        'source': 'webhook_input',
                        'target': 'transform_processor',
                        'sourceHandle': 'output',
                        'targetHandle': 'input'
                    },
                    {
                        'id': 'transform-to-email',
                        'source': 'transform_processor',
                        'target': 'email_output',
                        'sourceHandle': 'output',
                        'targetHandle': 'input'
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
                self.style.SUCCESS('\n=== Sample Workflow Created Successfully ===')
            )
            self.stdout.write(f'Workflow Name: {workflow.name}')
            self.stdout.write(f'Workflow ID: {workflow.id}')
            self.stdout.write(f'Owner: {workflow.owner.username}')
            self.stdout.write(f'Status: {workflow.get_status_display()}')
            self.stdout.write(f'Trigger Type: {workflow.get_trigger_type_display()}')
            
            self.stdout.write('\nNodes:')
            for node in workflow.nodes.all():
                self.stdout.write(f'  - {node.label} ({node.get_node_type_display()}) - ID: {node.node_id}')
            
            self.stdout.write('\nConnections:')
            for conn in workflow.connections.all():
                self.stdout.write(f'  - {conn.source_node.label} → {conn.target_node.label}')
            
            self.stdout.write('\nWebhook Endpoint:')
            self.stdout.write(f'  POST {options["webhook_url"]}')
            
            self.stdout.write('\nSample JSON payload for webhook:')
            self.stdout.write('  {')
            self.stdout.write('    "user": {')
            self.stdout.write('      "name": "John Doe",')
            self.stdout.write('      "email": "john@example.com"')
            self.stdout.write('    },')
            self.stdout.write('    "created_at": "2023-10-20T10:30:00Z"')
            self.stdout.write('  }')
            
            self.stdout.write('\nTransformed Output (JMESPath):')
            self.stdout.write('  {')
            self.stdout.write('    "name": "John Doe",')
            self.stdout.write('    "email": "john@example.com",')
            self.stdout.write('    "timestamp": "2023-10-20T10:30:00Z",')
            self.stdout.write('    "processed": true')
            self.stdout.write('  }')
            
            self.stdout.write('\nTo activate this workflow:')
            self.stdout.write(f'  1. Go to the Django admin panel')
            self.stdout.write(f'  2. Find the workflow "{workflow.name}"')
            self.stdout.write(f'  3. Change status to "Active"')
            self.stdout.write(f'  4. Test by sending a POST request to {options["webhook_url"]}')
            
        except Exception as e:
            # Clean up on error
            workflow.delete()
            raise CommandError(f'Failed to create workflow: {str(e)}')