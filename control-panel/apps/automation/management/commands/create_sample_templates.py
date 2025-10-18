"""
Django management command to create sample workflow templates.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.automation.models import WorkflowTemplate


class Command(BaseCommand):
    help = 'Create sample workflow templates for the automation system'

    def handle(self, *args, **options):
        """Create sample workflow templates."""
        
        # Get or create a system user for templates
        system_user, created = User.objects.get_or_create(
            username='system',
            defaults={
                'email': 'system@webops.local',
                'first_name': 'System',
                'last_name': 'Templates',
                'is_active': True,
            }
        )
        
        templates = [
            {
                'name': 'Database Backup Automation',
                'description': 'Automatically backup databases on a schedule and notify administrators of the status.',
                'category': WorkflowTemplate.Category.MONITORING,
                'workflow_data': {
                    'nodes': [
                        {
                            'id': 'trigger',
                            'type': 'trigger',
                            'label': 'Schedule Trigger',
                            'position': {'x': 100, 'y': 100},
                            'config': {
                                'schedule': '0 2 * * *',  # Daily at 2 AM
                                'description': 'Trigger backup daily at 2 AM'
                            }
                        },
                        {
                            'id': 'backup_db',
                            'type': 'database',
                            'label': 'Create Database Backup',
                            'position': {'x': 300, 'y': 100},
                            'config': {
                                'action': 'backup',
                                'database_name': '${DATABASE_NAME}',
                                'backup_location': '/backups/',
                                'compression': True
                            }
                        },
                        {
                            'id': 'check_backup',
                            'type': 'condition',
                            'label': 'Check Backup Success',
                            'position': {'x': 500, 'y': 100},
                            'config': {
                                'condition': 'backup_status == "success"'
                            }
                        },
                        {
                            'id': 'success_notification',
                            'type': 'email',
                            'label': 'Success Notification',
                            'position': {'x': 700, 'y': 50},
                            'config': {
                                'to': '${ADMIN_EMAIL}',
                                'subject': 'Database Backup Successful',
                                'body': 'Database backup completed successfully at ${timestamp}'
                            }
                        },
                        {
                            'id': 'failure_notification',
                            'type': 'email',
                            'label': 'Failure Notification',
                            'position': {'x': 700, 'y': 150},
                            'config': {
                                'to': '${ADMIN_EMAIL}',
                                'subject': 'Database Backup Failed',
                                'body': 'Database backup failed. Please check the logs.'
                            }
                        }
                    ],
                    'connections': [
                        {'source': 'trigger', 'target': 'backup_db'},
                        {'source': 'backup_db', 'target': 'check_backup'},
                        {'source': 'check_backup', 'target': 'success_notification', 'condition': 'true'},
                        {'source': 'check_backup', 'target': 'failure_notification', 'condition': 'false'}
                    ]
                }
            },
            {
                'name': 'System Health Monitoring',
                'description': 'Monitor system resources and send alerts when thresholds are exceeded.',
                'category': WorkflowTemplate.Category.MONITORING,
                'workflow_data': {
                    'nodes': [
                        {
                            'id': 'trigger',
                            'type': 'trigger',
                            'label': 'Schedule Trigger',
                            'position': {'x': 100, 'y': 100},
                            'config': {
                                'schedule': '*/5 * * * *',  # Every 5 minutes
                                'description': 'Check system health every 5 minutes'
                            }
                        },
                        {
                            'id': 'check_cpu',
                            'type': 'api',
                            'label': 'Check CPU Usage',
                            'position': {'x': 300, 'y': 50},
                            'config': {
                                'url': '/api/system/cpu',
                                'method': 'GET'
                            }
                        },
                        {
                            'id': 'check_memory',
                            'type': 'api',
                            'label': 'Check Memory Usage',
                            'position': {'x': 300, 'y': 150},
                            'config': {
                                'url': '/api/system/memory',
                                'method': 'GET'
                            }
                        },
                        {
                            'id': 'check_disk',
                            'type': 'api',
                            'label': 'Check Disk Usage',
                            'position': {'x': 300, 'y': 250},
                            'config': {
                                'url': '/api/system/disk',
                                'method': 'GET'
                            }
                        },
                        {
                            'id': 'aggregate_metrics',
                            'type': 'aggregate',
                            'label': 'Aggregate Metrics',
                            'position': {'x': 500, 'y': 150},
                            'config': {
                                'operation': 'merge',
                                'fields': ['cpu_usage', 'memory_usage', 'disk_usage']
                            }
                        },
                        {
                            'id': 'check_thresholds',
                            'type': 'condition',
                            'label': 'Check Alert Thresholds',
                            'position': {'x': 700, 'y': 150},
                            'config': {
                                'condition': 'cpu_usage > 80 OR memory_usage > 85 OR disk_usage > 90'
                            }
                        },
                        {
                            'id': 'send_alert',
                            'type': 'notification',
                            'label': 'Send Alert',
                            'position': {'x': 900, 'y': 150},
                            'config': {
                                'type': 'warning',
                                'title': 'System Resource Alert',
                                'message': 'System resources are running high: CPU: ${cpu_usage}%, Memory: ${memory_usage}%, Disk: ${disk_usage}%'
                            }
                        }
                    ],
                    'connections': [
                        {'source': 'trigger', 'target': 'check_cpu'},
                        {'source': 'trigger', 'target': 'check_memory'},
                        {'source': 'trigger', 'target': 'check_disk'},
                        {'source': 'check_cpu', 'target': 'aggregate_metrics'},
                        {'source': 'check_memory', 'target': 'aggregate_metrics'},
                        {'source': 'check_disk', 'target': 'aggregate_metrics'},
                        {'source': 'aggregate_metrics', 'target': 'check_thresholds'},
                        {'source': 'check_thresholds', 'target': 'send_alert', 'condition': 'true'}
                    ]
                }
            },
            {
                'name': 'Deployment Notification',
                'description': 'Send notifications to team members when deployments are completed.',
                'category': WorkflowTemplate.Category.INTEGRATION,
                'workflow_data': {
                    'nodes': [
                        {
                            'id': 'webhook_trigger',
                            'type': 'webhook',
                            'label': 'Deployment Webhook',
                            'position': {'x': 100, 'y': 100},
                            'config': {
                                'endpoint': '/webhook/deployment',
                                'method': 'POST',
                                'description': 'Receives deployment completion events'
                            }
                        },
                        {
                            'id': 'parse_deployment',
                            'type': 'transform',
                            'label': 'Parse Deployment Data',
                            'position': {'x': 300, 'y': 100},
                            'config': {
                                'extract_fields': ['app_name', 'version', 'environment', 'status', 'deployed_by']
                            }
                        },
                        {
                            'id': 'check_status',
                            'type': 'condition',
                            'label': 'Check Deployment Status',
                            'position': {'x': 500, 'y': 100},
                            'config': {
                                'condition': 'status == "success"'
                            }
                        },
                        {
                            'id': 'success_slack',
                            'type': 'slack',
                            'label': 'Success Notification',
                            'position': {'x': 700, 'y': 50},
                            'config': {
                                'channel': '#deployments',
                                'message': '✅ Deployment successful: ${app_name} v${version} deployed to ${environment} by ${deployed_by}'
                            }
                        },
                        {
                            'id': 'failure_slack',
                            'type': 'slack',
                            'label': 'Failure Notification',
                            'position': {'x': 700, 'y': 150},
                            'config': {
                                'channel': '#deployments',
                                'message': '❌ Deployment failed: ${app_name} v${version} failed to deploy to ${environment}. Deployed by ${deployed_by}'
                            }
                        }
                    ],
                    'connections': [
                        {'source': 'webhook_trigger', 'target': 'parse_deployment'},
                        {'source': 'parse_deployment', 'target': 'check_status'},
                        {'source': 'check_status', 'target': 'success_slack', 'condition': 'true'},
                        {'source': 'check_status', 'target': 'failure_slack', 'condition': 'false'}
                    ]
                }
            },
            {
                'name': 'Log Cleanup Automation',
                'description': 'Automatically clean up old log files to free up disk space.',
                'category': WorkflowTemplate.Category.DATA_PROCESSING,
                'workflow_data': {
                    'nodes': [
                        {
                            'id': 'trigger',
                            'type': 'trigger',
                            'label': 'Weekly Cleanup',
                            'position': {'x': 100, 'y': 100},
                            'config': {
                                'schedule': '0 3 * * 0',  # Weekly on Sunday at 3 AM
                                'description': 'Run log cleanup weekly'
                            }
                        },
                        {
                            'id': 'find_old_logs',
                            'type': 'file',
                            'label': 'Find Old Log Files',
                            'position': {'x': 300, 'y': 100},
                            'config': {
                                'action': 'find',
                                'path': '/var/log/',
                                'pattern': '*.log',
                                'older_than_days': 30
                            }
                        },
                        {
                            'id': 'compress_logs',
                            'type': 'code',
                            'label': 'Compress Old Logs',
                            'position': {'x': 500, 'y': 100},
                            'config': {
                                'language': 'bash',
                                'script': 'gzip ${file_path}'
                            }
                        },
                        {
                            'id': 'delete_very_old',
                            'type': 'file',
                            'label': 'Delete Very Old Logs',
                            'position': {'x': 700, 'y': 100},
                            'config': {
                                'action': 'delete',
                                'path': '/var/log/',
                                'pattern': '*.log.gz',
                                'older_than_days': 90
                            }
                        },
                        {
                            'id': 'report_cleanup',
                            'type': 'notification',
                            'label': 'Cleanup Report',
                            'position': {'x': 900, 'y': 100},
                            'config': {
                                'type': 'info',
                                'title': 'Log Cleanup Complete',
                                'message': 'Log cleanup completed. Compressed ${compressed_count} files, deleted ${deleted_count} old files.'
                            }
                        }
                    ],
                    'connections': [
                        {'source': 'trigger', 'target': 'find_old_logs'},
                        {'source': 'find_old_logs', 'target': 'compress_logs'},
                        {'source': 'compress_logs', 'target': 'delete_very_old'},
                        {'source': 'delete_very_old', 'target': 'report_cleanup'}
                    ]
                }
            },
            {
                'name': 'Service Restart Template',
                'description': 'Automatically restart services when they become unresponsive.',
                'category': WorkflowTemplate.Category.MONITORING,
                'workflow_data': {
                    'nodes': [
                        {
                            'id': 'trigger',
                            'type': 'trigger',
                            'label': 'Health Check',
                            'position': {'x': 100, 'y': 100},
                            'config': {
                                'schedule': '*/2 * * * *',  # Every 2 minutes
                                'description': 'Check service health every 2 minutes'
                            }
                        },
                        {
                            'id': 'check_service',
                            'type': 'api',
                            'label': 'Check Service Health',
                            'position': {'x': 300, 'y': 100},
                            'config': {
                                'url': '${SERVICE_HEALTH_URL}',
                                'method': 'GET',
                                'timeout': 10
                            }
                        },
                        {
                            'id': 'check_response',
                            'type': 'condition',
                            'label': 'Check Response',
                            'position': {'x': 500, 'y': 100},
                            'config': {
                                'condition': 'status_code != 200 OR response_time > 5000'
                            }
                        },
                        {
                            'id': 'restart_service',
                            'type': 'code',
                            'label': 'Restart Service',
                            'position': {'x': 700, 'y': 100},
                            'config': {
                                'language': 'bash',
                                'script': 'systemctl restart ${SERVICE_NAME}'
                            }
                        },
                        {
                            'id': 'wait_for_restart',
                            'type': 'delay',
                            'label': 'Wait for Restart',
                            'position': {'x': 900, 'y': 100},
                            'config': {
                                'delay_seconds': 30
                            }
                        },
                        {
                            'id': 'verify_restart',
                            'type': 'api',
                            'label': 'Verify Service',
                            'position': {'x': 1100, 'y': 100},
                            'config': {
                                'url': '${SERVICE_HEALTH_URL}',
                                'method': 'GET',
                                'timeout': 10
                            }
                        },
                        {
                            'id': 'notify_admin',
                            'type': 'email',
                            'label': 'Notify Administrator',
                            'position': {'x': 1300, 'y': 100},
                            'config': {
                                'to': '${ADMIN_EMAIL}',
                                'subject': 'Service Restart: ${SERVICE_NAME}',
                                'body': 'Service ${SERVICE_NAME} was automatically restarted due to health check failure.'
                            }
                        }
                    ],
                    'connections': [
                        {'source': 'trigger', 'target': 'check_service'},
                        {'source': 'check_service', 'target': 'check_response'},
                        {'source': 'check_response', 'target': 'restart_service', 'condition': 'true'},
                        {'source': 'restart_service', 'target': 'wait_for_restart'},
                        {'source': 'wait_for_restart', 'target': 'verify_restart'},
                        {'source': 'verify_restart', 'target': 'notify_admin'}
                    ]
                }
            }
        ]
        
        created_count = 0
        for template_data in templates:
            template, created = WorkflowTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    'description': template_data['description'],
                    'category': template_data['category'],
                    'workflow_data': template_data['workflow_data'],
                    'author': system_user,
                    'is_official': True,
                    'is_public': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created template: {template.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Template already exists: {template.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} new templates')
        )