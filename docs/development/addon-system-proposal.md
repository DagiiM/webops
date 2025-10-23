# WebOps Addon System Proposal

> **Status:** Draft  
> **Version:** 2.0  
> **Last updated:** 2025-01-21  
> **Authors:** WebOps Development Team

## Executive Summary

The WebOps Addon System enables secure, extensible functionality through a plugin architecture that supports CLI commands, Control Panel UI components, API endpoints, deployment hooks, background tasks, and infrastructure templates. This proposal outlines a comprehensive framework for third-party and internal extensions while maintaining system security, stability, and upgrade compatibility.

## Overview

Addons are optional, installable extensions that integrate with WebOps through a stable, versioned contract. Each addon operates within a defined security sandbox with explicit capability declarations, ensuring system integrity while enabling powerful extensibility.

### Key Principles

- **Security First:** Capability-based permissions with sandboxed execution
- **Stable Contracts:** Semantic versioning with backward compatibility guarantees
- **Developer Experience:** Rich tooling, clear documentation, and comprehensive examples
- **Operational Excellence:** Monitoring, logging, and lifecycle management built-in

## Goals

- Enable third-party and internal teams to extend WebOps safely and efficiently
- Maintain smooth upgrades via compatibility checks and strict API contracts
- Provide consistent UX across CLI and Control Panel interfaces
- Ensure enterprise-grade security with capabilities, sandboxing, and audit trails
- Support rapid development cycles with hot-reloading and debugging tools

## Addon Types

### CLI Addons
- **Purpose:** Extend the `webops` command-line interface with new commands and interactive flows
- **Integration:** Dynamic command registration via Python entry points
- **Examples:** `webops slack notify`, `webops backup create`, `webops monitor dashboard`

### Control Panel Addons  
- **Purpose:** Add admin pages, templates, static assets, and API endpoints to the Django control panel
- **Integration:** Django app registration with automatic URL routing and template discovery
- **Examples:** Monitoring dashboards, integration settings pages, custom deployment workflows

### Provider Addons
- **Purpose:** Add support for new deployment targets, database providers, and infrastructure services
- **Integration:** Hook-based architecture with provisioning script contributions
- **Examples:** AWS ECS provider, MongoDB provider, Kubernetes deployment provider

### Integration Addons
- **Purpose:** Connect WebOps to external tools and services
- **Integration:** Webhook handlers, API clients, and notification channels
- **Examples:** Slack notifications, GitHub Actions integration, Datadog monitoring, PagerDuty alerting

### Essential Addons (Priority Implementation)

#### CI/CD Pipeline Integration Addon
- **Purpose:** Comprehensive integration with popular CI/CD platforms for advanced deployment workflows
- **Gap Addressed:** Current webhook system only triggers deployments but lacks CI/CD pipeline integration
- **Integration:** Pipeline status tracking, build artifact management, deployment gates
- **Key Features:**
  - GitHub Actions workflow integration and status tracking
  - GitLab CI/CD pipeline monitoring and artifact management
  - Jenkins job integration with build status reporting
  - Automated deployment gates based on CI/CD results
  - Build artifact storage and deployment coordination
  - Pipeline failure notifications and retry mechanisms
- **Examples:** `webops pipeline status`, `webops artifacts deploy`, `webops gates configure`

#### Log Aggregation and Analytics Addon
- **Purpose:** Centralized log management and analytics for all WebOps deployments
- **Gap Addressed:** Current logging is scattered across deployments with no centralized search or analytics
- **Integration:** Real-time log streaming, search interface, analytics dashboard
- **Key Features:**
  - Centralized log collection from all deployments and services
  - Real-time log streaming with WebSocket connections
  - Advanced search and filtering capabilities with regex support
  - Integration with ELK stack (Elasticsearch, Logstash, Kibana)
  - Log analytics with pattern detection and anomaly alerts
  - Custom log parsing rules and structured logging
  - Log retention policies with automated archiving
  - Performance metrics derived from log analysis
- **Examples:** `webops logs search`, `webops logs stream`, `webops logs analyze`

## Technical Architecture

### CLI Integration Points

The CLI addon system integrates with the existing Click-based command structure:

```python
# Current CLI structure in cli/webops_cli/cli.py
@click.group()
def main() -> None:
    """WebOps CLI - Manage your deployments from the command line."""
    pass

# Addon commands will be dynamically registered:
main.add_command(addon_command_group)
```

**Integration Mechanism:**
- Addons register commands via Python `entry_points` in `setup.py` or `pyproject.toml`
- CLI loader discovers and imports addon commands at runtime
- Commands inherit from base classes providing API client access and configuration
- Interactive flows integrate with existing `cli.py` and `terminal_ui.py` components

### Control Panel Integration Points

The Django control panel supports dynamic app registration:

```python
# Current structure in control-panel/config/settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    # ... core Django apps
    'apps.core',
    'apps.deployments', 
    'apps.databases',
    'apps.services',
    'apps.api',
    # Addon apps will be dynamically added here
]
```

**Integration Mechanism:**
- Addons provide Django `AppConfig` classes for Control Panel integration
- Dynamic `INSTALLED_APPS` modification during startup based on enabled addons
- URL routing automatically includes addon URL patterns
- Template and static file discovery works seamlessly with Django's app structure
- Admin interface automatically registers addon models and admin classes

### Provider and Integration Points

**System Templates Integration:**
```python
# Addons can contribute system configuration templates
# Located in system-templates/ directory structure
addon_templates = {
    'nginx': 'templates/nginx/addon-config.conf.j2',
    'systemd': 'templates/systemd/addon-service.service.j2',
    'ssl': 'scripts/ssl/addon-ssl-setup.sh'
}
```

**Background Task Integration:**
```python
# Integration with control-panel/config/celery_app.py
from celery import shared_task

@shared_task
def addon_background_task():
    """Addon-provided background task"""
    pass
```

**Hook Registry System:**
```python
# Central hook registry for addon integration
class AddonHookRegistry:
    def __init__(self):
        self.hooks = {
            'pre_deployment': [],
            'post_deployment': [],
            'pre_backup': [],
            'post_backup': [],
            'service_health_check': [],
            'notification_channels': []
        }
    
    def register_hook(self, event: str, callback: callable):
        """Register addon hook for specific events"""
        if event in self.hooks:
            self.hooks[event].append(callback)
```

## Implementation Examples

### Example 1: Slack Notifications Addon

**Directory Structure:**
```
addons/slack-notifications/
├── addon.yaml
├── setup.py
├── slack_addon/
│   ├── __init__.py
│   ├── cli.py          # CLI commands
│   ├── apps.py         # Django app config
│   ├── models.py       # Django models
│   ├── views.py        # API endpoints
│   ├── admin.py        # Admin interface
│   ├── tasks.py        # Celery tasks
│   └── templates/
│       └── slack/
│           └── settings.html
└── static/
    └── slack/
        ├── css/
        └── js/
```

**addon.yaml:**
```yaml
name: slack-notifications
version: 1.0.0
description: Send deployment notifications to Slack channels
author: WebOps Community
license: MIT

webops_version: ">=2.0.0"

capabilities:
  - notifications
  - webhooks

hooks:
  - post_deployment
  - service_health_check
  - backup_complete

django_app: slack_addon
cli_commands: slack_addon.cli:slack_group

dependencies:
  - slack-sdk>=3.0.0
  - requests>=2.28.0

settings_schema:
  webhook_url:
    type: string
    required: true
    description: Slack webhook URL for notifications
  default_channel:
    type: string
    default: "#deployments"
    description: Default Slack channel for notifications
```

**CLI Integration (slack_addon/cli.py):**
```python
import click
from webops_cli.base import WebOpsCommand

@click.group()
def slack_group():
    """Slack notification commands"""
    pass

@slack_group.command()
@click.option('--channel', default='#deployments')
@click.argument('message')
class SlackNotifyCommand(WebOpsCommand):
    """Send a message to Slack"""
    
    def execute(self, channel: str, message: str):
        # Implementation using addon configuration
        webhook_url = self.get_addon_setting('slack-notifications', 'webhook_url')
        # Send notification logic
        self.success(f"Message sent to {channel}")
```

**Django Integration (slack_addon/apps.py):**
```python
from django.apps import AppConfig

class SlackAddonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'slack_addon'
    verbose_name = 'Slack Notifications'
    
    def ready(self):
        # Register hooks when app is ready
        from webops.addons import hook_registry
        from .hooks import post_deployment_notification
        
        hook_registry.register_hook('post_deployment', post_deployment_notification)
```

### Example 2: CI/CD Pipeline Integration Addon

This addon provides comprehensive integration with popular CI/CD platforms, addressing the gap in WebOps' current webhook-only deployment system.

```
addons/
└── cicd-pipeline-integration/
    ├── addon.yaml
    ├── __init__.py
    ├── cli/
    │   ├── __init__.py
    │   ├── pipeline.py
    │   ├── artifacts.py
    │   └── gates.py
    ├── control_panel/
    │   ├── __init__.py
    │   ├── apps.py
    │   ├── models.py
    │   ├── views.py
    │   ├── urls.py
    │   ├── admin.py
    │   ├── templates/
    │   │   └── cicd/
    │   │       ├── dashboard.html
    │   │       ├── pipeline_status.html
    │   │       └── artifacts.html
    │   └── static/
    │       └── cicd/
    │           ├── css/
    │           └── js/
    ├── providers/
    │   ├── __init__.py
    │   ├── github_actions.py
    │   ├── gitlab_ci.py
    │   └── jenkins.py
    ├── webhooks/
    │   ├── __init__.py
    │   └── handlers.py
    ├── tasks/
    │   ├── __init__.py
    │   └── pipeline_sync.py
    └── tests/
        ├── __init__.py
        ├── test_cli.py
        ├── test_providers.py
        └── test_webhooks.py
```

**addon.yaml:**
```yaml
name: cicd-pipeline-integration
version: 1.0.0
description: Comprehensive CI/CD pipeline integration for GitHub Actions, GitLab CI, and Jenkins
author: WebOps Team
license: MIT
webops_version: ">=1.0.0"

capabilities:
  - network.http_client
  - storage.database
  - hooks.deployment
  - webhooks.receive

integration:
  hooks:
    - name: pre_deployment
      handler: cicd_pipeline_integration.hooks.validate_pipeline_status
    - name: post_deployment
      handler: cicd_pipeline_integration.hooks.update_deployment_status
  
  django_app:
    name: cicd_pipeline_integration.control_panel
    url_prefix: cicd
  
  cli_commands:
    - name: pipeline
      module: cicd_pipeline_integration.cli.pipeline
    - name: artifacts
      module: cicd_pipeline_integration.cli.artifacts
    - name: gates
      module: cicd_pipeline_integration.cli.gates
  
  webhooks:
    - path: /webhooks/github-actions
      handler: cicd_pipeline_integration.webhooks.handlers.github_actions
    - path: /webhooks/gitlab-ci
      handler: cicd_pipeline_integration.webhooks.handlers.gitlab_ci
    - path: /webhooks/jenkins
      handler: cicd_pipeline_integration.webhooks.handlers.jenkins

dependencies:
  python:
    - requests>=2.28.0
    - PyGithub>=1.58.0
    - python-gitlab>=3.12.0
    - python-jenkins>=1.8.0
    - celery>=5.2.0

configuration:
  schema:
    github:
      type: object
      properties:
        token:
          type: string
          secret: true
          description: GitHub personal access token
        webhook_secret:
          type: string
          secret: true
          description: GitHub webhook secret
    gitlab:
      type: object
      properties:
        url:
          type: string
          description: GitLab instance URL
        token:
          type: string
          secret: true
          description: GitLab access token
    jenkins:
      type: object
      properties:
        url:
          type: string
          description: Jenkins server URL
        username:
          type: string
          description: Jenkins username
        api_token:
          type: string
          secret: true
          description: Jenkins API token
    deployment_gates:
      type: object
      properties:
        require_successful_build:
          type: boolean
          default: true
        require_tests_passed:
          type: boolean
          default: true
        require_security_scan:
          type: boolean
          default: false

security:
  signature: "sha256:abc123..."
  
marketplace:
  category: integration
  tags: [cicd, github, gitlab, jenkins, automation]
  screenshots: [dashboard.png, pipeline-status.png]
```

**CLI Implementation (cli/pipeline.py):**
```python
import click
from webops.cli.decorators import webops_command
from .providers import get_provider

@webops_command()
@click.group()
def pipeline():
    """Manage CI/CD pipeline integrations."""
    pass

@pipeline.command()
@click.option('--provider', type=click.Choice(['github', 'gitlab', 'jenkins']), required=True)
@click.option('--repository', required=True, help='Repository name (owner/repo for GitHub)')
@click.option('--branch', default='main', help='Branch to check')
def status(provider, repository, branch):
    """Check pipeline status for a repository."""
    provider_instance = get_provider(provider)
    status_info = provider_instance.get_pipeline_status(repository, branch)
    
    click.echo(f"Pipeline Status for {repository}:{branch}")
    click.echo(f"Status: {status_info['status']}")
    click.echo(f"Last Run: {status_info['last_run']}")
    click.echo(f"Duration: {status_info['duration']}")
    
    if status_info['status'] == 'failed':
        click.echo(f"Failure Reason: {status_info['failure_reason']}")

@pipeline.command()
@click.option('--provider', type=click.Choice(['github', 'gitlab', 'jenkins']), required=True)
@click.option('--repository', required=True)
@click.option('--workflow', help='Workflow/pipeline name')
def trigger(provider, repository, workflow):
    """Trigger a pipeline run."""
    provider_instance = get_provider(provider)
    run_id = provider_instance.trigger_pipeline(repository, workflow)
    click.echo(f"Pipeline triggered successfully. Run ID: {run_id}")
```

**Django Models (control_panel/models.py):**
```python
from django.db import models
from django.contrib.auth.models import User

class PipelineProvider(models.Model):
    PROVIDER_CHOICES = [
        ('github', 'GitHub Actions'),
        ('gitlab', 'GitLab CI'),
        ('jenkins', 'Jenkins'),
    ]
    
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    configuration = models.JSONField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PipelineRun(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    provider = models.ForeignKey(PipelineProvider, on_delete=models.CASCADE)
    repository = models.CharField(max_length=200)
    branch = models.CharField(max_length=100)
    commit_sha = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    run_id = models.CharField(max_length=100)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    logs_url = models.URLField(blank=True)
    artifacts_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DeploymentGate(models.Model):
    name = models.CharField(max_length=100)
    repository = models.CharField(max_length=200)
    branch = models.CharField(max_length=100, default='main')
    require_successful_build = models.BooleanField(default=True)
    require_tests_passed = models.BooleanField(default=True)
    require_security_scan = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

**GitHub Actions Provider (providers/github_actions.py):**
```python
import requests
from github import Github
from django.conf import settings
from ..models import PipelineRun

class GitHubActionsProvider:
    def __init__(self, config):
        self.token = config['token']
        self.github = Github(self.token)
    
    def get_pipeline_status(self, repository, branch='main'):
        """Get the latest pipeline status for a repository branch."""
        repo = self.github.get_repo(repository)
        workflows = repo.get_workflows()
        
        latest_run = None
        for workflow in workflows:
            runs = workflow.get_runs(branch=branch)
            for run in runs:
                if latest_run is None or run.created_at > latest_run.created_at:
                    latest_run = run
                break
        
        if not latest_run:
            return {'status': 'no_runs', 'last_run': None}
        
        return {
            'status': latest_run.status,
            'conclusion': latest_run.conclusion,
            'last_run': latest_run.created_at,
            'duration': latest_run.updated_at - latest_run.created_at if latest_run.updated_at else None,
            'run_id': latest_run.id,
            'html_url': latest_run.html_url,
            'failure_reason': self._get_failure_reason(latest_run) if latest_run.conclusion == 'failure' else None
        }
    
    def trigger_pipeline(self, repository, workflow_name=None):
        """Trigger a workflow run."""
        repo = self.github.get_repo(repository)
        
        if workflow_name:
            workflow = repo.get_workflow(workflow_name)
        else:
            workflows = list(repo.get_workflows())
            if not workflows:
                raise ValueError("No workflows found in repository")
            workflow = workflows[0]
        
        success = workflow.create_dispatch('main')
        return workflow.id if success else None
    
    def _get_failure_reason(self, run):
        """Extract failure reason from workflow run."""
        jobs = run.get_jobs()
        for job in jobs:
            if job.conclusion == 'failure':
                return f"Job '{job.name}' failed"
        return "Unknown failure"
```

**Webhook Handler (webhooks/handlers.py):**
```python
import json
import hmac
import hashlib
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from ..models import PipelineRun, PipelineProvider
from ..tasks import sync_pipeline_status

@csrf_exempt
@require_http_methods(["POST"])
def github_actions(request):
    """Handle GitHub Actions webhook events."""
    signature = request.META.get('HTTP_X_HUB_SIGNATURE_256')
    if not signature:
        return HttpResponseBadRequest("Missing signature")
    
    # Verify webhook signature
    provider = PipelineProvider.objects.filter(
        provider_type='github', is_active=True
    ).first()
    
    if not provider:
        return HttpResponseBadRequest("No active GitHub provider")
    
    webhook_secret = provider.configuration.get('webhook_secret', '')
    expected_signature = 'sha256=' + hmac.new(
        webhook_secret.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return HttpResponseBadRequest("Invalid signature")
    
    payload = json.loads(request.body)
    event_type = request.META.get('HTTP_X_GITHUB_EVENT')
    
    if event_type == 'workflow_run':
        handle_workflow_run_event(payload, provider)
    
    return HttpResponse("OK")

def handle_workflow_run_event(payload, provider):
    """Process GitHub workflow run events."""
    workflow_run = payload['workflow_run']
    repository = payload['repository']['full_name']
    
    # Update or create pipeline run record
    run, created = PipelineRun.objects.update_or_create(
        provider=provider,
        repository=repository,
        run_id=str(workflow_run['id']),
        defaults={
            'branch': workflow_run['head_branch'],
            'commit_sha': workflow_run['head_sha'],
            'status': workflow_run['status'],
            'started_at': workflow_run['created_at'],
            'completed_at': workflow_run.get('updated_at'),
            'logs_url': workflow_run['logs_url'],
            'artifacts_url': workflow_run.get('artifacts_url', ''),
        }
    )
    
    # Trigger async task to sync additional data
    sync_pipeline_status.delay(run.id)
```

## Architecture Options

1. Python package addons with `entry_points` for discovery.
   - Pros: mature ecosystem, easy publishing.
   - Cons: requires packaging and versioning discipline.
2. Django app addons loaded dynamically by manifest.
   - Pros: tight Control Panel integration.
   - Cons: increased coupling to server and migrations.
3. Hybrid approach (recommended): core discovery via Python entry points; server UI via optional Django apps.

### Example 3: Log Aggregation and Analytics Addon

This addon provides centralized log management and analytics for all WebOps deployments, addressing the gap in scattered logging across services.

```
addons/
└── log-aggregation-analytics/
    ├── addon.yaml
    ├── __init__.py
    ├── cli/
    │   ├── __init__.py
    │   ├── logs.py
    │   ├── search.py
    │   └── analytics.py
    ├── control_panel/
    │   ├── __init__.py
    │   ├── apps.py
    │   ├── models.py
    │   ├── views.py
    │   ├── urls.py
    │   ├── admin.py
    │   ├── templates/
    │   │   └── logs/
    │   │       ├── dashboard.html
    │   │       ├── search.html
    │   │       ├── analytics.html
    │   │       └── stream.html
    │   └── static/
    │       └── logs/
    │           ├── css/
    │           │   └── logs.css
    │           └── js/
    │               ├── log-stream.js
    │               └── search.js
    ├── collectors/
    │   ├── __init__.py
    │   ├── docker_logs.py
    │   ├── syslog.py
    │   └── application_logs.py
    ├── processors/
    │   ├── __init__.py
    │   ├── parsers.py
    │   ├── enrichers.py
    │   └── filters.py
    ├── storage/
    │   ├── __init__.py
    │   ├── elasticsearch.py
    │   └── retention.py
    ├── analytics/
    │   ├── __init__.py
    │   ├── patterns.py
    │   ├── anomalies.py
    │   └── metrics.py
    ├── websockets/
    │   ├── __init__.py
    │   └── consumers.py
    └── tests/
        ├── __init__.py
        ├── test_collectors.py
        ├── test_processors.py
        └── test_analytics.py
```

**addon.yaml:**
```yaml
name: log-aggregation-analytics
version: 1.0.0
description: Centralized log management and analytics with ELK stack integration
author: WebOps Team
license: MIT
webops_version: ">=1.0.0"

capabilities:
  - network.http_client
  - storage.database
  - storage.elasticsearch
  - hooks.deployment
  - websockets.consumer
  - system.docker_logs

integration:
  hooks:
    - name: post_deployment
      handler: log_aggregation_analytics.hooks.setup_log_collection
    - name: pre_deployment_cleanup
      handler: log_aggregation_analytics.hooks.cleanup_old_logs
  
  django_app:
    name: log_aggregation_analytics.control_panel
    url_prefix: logs
  
  cli_commands:
    - name: logs
      module: log_aggregation_analytics.cli.logs
    - name: log-search
      module: log_aggregation_analytics.cli.search
    - name: log-analytics
      module: log_aggregation_analytics.cli.analytics
  
  websocket_consumers:
    - path: /ws/logs/stream/
      consumer: log_aggregation_analytics.websockets.consumers.LogStreamConsumer

dependencies:
  python:
    - elasticsearch>=8.5.0
    - elasticsearch-dsl>=8.5.0
    - logstash-python>=1.0.0
    - docker>=6.0.0
    - channels>=4.0.0
    - channels-redis>=4.0.0
    - celery>=5.2.0
    - redis>=4.5.0
  
  system:
    - elasticsearch>=8.5
    - logstash>=8.5
    - kibana>=8.5
    - redis>=6.0

configuration:
  schema:
    elasticsearch:
      type: object
      properties:
        hosts:
          type: array
          items:
            type: string
          default: ["http://localhost:9200"]
          description: Elasticsearch cluster hosts
        username:
          type: string
          description: Elasticsearch username
        password:
          type: string
          secret: true
          description: Elasticsearch password
        index_prefix:
          type: string
          default: webops-logs
          description: Index prefix for log storage
    logstash:
      type: object
      properties:
        host:
          type: string
          default: localhost
          description: Logstash host
        port:
          type: integer
          default: 5044
          description: Logstash beats input port
    retention:
      type: object
      properties:
        default_days:
          type: integer
          default: 30
          description: Default log retention in days
        error_logs_days:
          type: integer
          default: 90
          description: Error log retention in days
        archive_enabled:
          type: boolean
          default: true
          description: Enable log archiving to S3/storage
    analytics:
      type: object
      properties:
        anomaly_detection:
          type: boolean
          default: true
          description: Enable anomaly detection
        pattern_analysis:
          type: boolean
          default: true
          description: Enable log pattern analysis
        alert_threshold:
          type: integer
          default: 100
          description: Error count threshold for alerts

security:
  signature: "sha256:ghi789..."
  
marketplace:
  category: monitoring
  tags: [logs, analytics, elasticsearch, monitoring, observability]
  screenshots: [dashboard.png, search.png, analytics.png]
```

**CLI Implementation (cli/logs.py):**
```python
import click
import json
from datetime import datetime, timedelta
from webops.cli.decorators import webops_command
from ..storage.elasticsearch import ElasticsearchClient
from ..analytics.patterns import PatternAnalyzer

@webops_command()
@click.group()
def logs():
    """Manage log aggregation and analytics."""
    pass

@logs.command()
@click.option('--service', help='Filter by service name')
@click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), help='Log level filter')
@click.option('--since', help='Show logs since (e.g., 1h, 30m, 2d)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--lines', '-n', default=100, help='Number of lines to show')
def tail(service, level, since, follow, lines):
    """Tail logs from deployments."""
    es_client = ElasticsearchClient()
    
    query_filters = []
    if service:
        query_filters.append({'term': {'service.keyword': service}})
    if level:
        query_filters.append({'term': {'level.keyword': level}})
    
    if since:
        since_time = parse_time_delta(since)
        query_filters.append({
            'range': {
                '@timestamp': {
                    'gte': since_time.isoformat()
                }
            }
        })
    
    if follow:
        # Implement real-time log following
        for log_entry in es_client.stream_logs(query_filters):
            print_log_entry(log_entry)
    else:
        logs = es_client.search_logs(query_filters, size=lines)
        for log_entry in logs:
            print_log_entry(log_entry)

@logs.command()
@click.argument('query')
@click.option('--service', help='Filter by service name')
@click.option('--since', help='Search since (e.g., 1h, 30m, 2d)')
@click.option('--regex', is_flag=True, help='Use regex search')
def search(query, service, since, regex):
    """Search logs with advanced filtering."""
    es_client = ElasticsearchClient()
    
    search_query = {
        'bool': {
            'must': []
        }
    }
    
    if regex:
        search_query['bool']['must'].append({
            'regexp': {
                'message': query
            }
        })
    else:
        search_query['bool']['must'].append({
            'multi_match': {
                'query': query,
                'fields': ['message', 'logger', 'service']
            }
        })
    
    if service:
        search_query['bool']['must'].append({
            'term': {'service.keyword': service}
        })
    
    if since:
        since_time = parse_time_delta(since)
        search_query['bool']['must'].append({
            'range': {
                '@timestamp': {
                    'gte': since_time.isoformat()
                }
            }
        })
    
    results = es_client.search_logs_advanced(search_query)
    
    click.echo(f"Found {results['total']} matching log entries:")
    for log_entry in results['hits']:
        print_log_entry(log_entry['_source'])

@logs.command()
@click.option('--service', help='Analyze specific service')
@click.option('--period', default='24h', help='Analysis period (e.g., 1h, 24h, 7d)')
def analyze(service, period):
    """Analyze log patterns and anomalies."""
    analyzer = PatternAnalyzer()
    
    since_time = parse_time_delta(period)
    analysis = analyzer.analyze_logs(
        service=service,
        since=since_time
    )
    
    click.echo("Log Analysis Report")
    click.echo("=" * 50)
    click.echo(f"Period: {period}")
    click.echo(f"Total Logs: {analysis['total_logs']:,}")
    click.echo(f"Error Rate: {analysis['error_rate']:.2%}")
    
    if analysis['anomalies']:
        click.echo("\nAnomalies Detected:")
        for anomaly in analysis['anomalies']:
            click.echo(f"  - {anomaly['type']}: {anomaly['description']}")
    
    if analysis['top_patterns']:
        click.echo("\nTop Log Patterns:")
        for pattern in analysis['top_patterns']:
            click.echo(f"  - {pattern['pattern']} ({pattern['count']} occurrences)")

def print_log_entry(log_entry):
    """Format and print a log entry."""
    timestamp = log_entry.get('@timestamp', '')
    level = log_entry.get('level', 'INFO')
    service = log_entry.get('service', 'unknown')
    message = log_entry.get('message', '')
    
    # Color coding for log levels
    level_colors = {
        'DEBUG': 'blue',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red'
    }
    
    color = level_colors.get(level, 'white')
    click.echo(f"{timestamp} [{click.style(level, fg=color)}] {service}: {message}")

def parse_time_delta(time_str):
    """Parse time delta string (e.g., '1h', '30m', '2d') to datetime."""
    import re
    
    match = re.match(r'(\d+)([hmd])', time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'm':
        delta = timedelta(minutes=value)
    elif unit == 'h':
        delta = timedelta(hours=value)
    elif unit == 'd':
        delta = timedelta(days=value)
    
    return datetime.utcnow() - delta
```

**Django Models (control_panel/models.py):**
```python
from django.db import models
from django.contrib.auth.models import User

class LogSource(models.Model):
    SOURCE_TYPES = [
        ('docker', 'Docker Container'),
        ('syslog', 'System Log'),
        ('application', 'Application Log'),
        ('nginx', 'Nginx Access/Error'),
        ('database', 'Database Log'),
    ]
    
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    service_name = models.CharField(max_length=100)
    log_path = models.CharField(max_length=500, blank=True)
    docker_container_id = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    parser_config = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class LogRetentionPolicy(models.Model):
    name = models.CharField(max_length=100)
    service_pattern = models.CharField(max_length=200, help_text="Regex pattern for service names")
    log_level_filter = models.CharField(max_length=20, blank=True)
    retention_days = models.IntegerField(default=30)
    archive_enabled = models.BooleanField(default=True)
    archive_storage_path = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class LogAlert(models.Model):
    ALERT_TYPES = [
        ('error_rate', 'Error Rate Threshold'),
        ('pattern_match', 'Pattern Match'),
        ('anomaly', 'Anomaly Detection'),
        ('volume', 'Log Volume Threshold'),
    ]
    
    name = models.CharField(max_length=100)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    service_filter = models.CharField(max_length=200, blank=True)
    condition_config = models.JSONField()
    notification_channels = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class LogAnalyticsReport(models.Model):
    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=50)
    service_filter = models.CharField(max_length=200, blank=True)
    time_period = models.CharField(max_length=20)  # e.g., '24h', '7d', '30d'
    report_data = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
```

**Elasticsearch Client (storage/elasticsearch.py):**
```python
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q, A
from django.conf import settings
import json
from datetime import datetime

class ElasticsearchClient:
    def __init__(self):
        self.es = Elasticsearch(
            settings.ELASTICSEARCH_HOSTS,
            http_auth=(
                settings.ELASTICSEARCH_USERNAME,
                settings.ELASTICSEARCH_PASSWORD
            ) if hasattr(settings, 'ELASTICSEARCH_USERNAME') else None
        )
        self.index_prefix = getattr(settings, 'ELASTICSEARCH_INDEX_PREFIX', 'webops-logs')
    
    def index_log(self, log_data):
        """Index a single log entry."""
        index_name = f"{self.index_prefix}-{datetime.now().strftime('%Y.%m.%d')}"
        
        # Ensure required fields
        if '@timestamp' not in log_data:
            log_data['@timestamp'] = datetime.utcnow().isoformat()
        
        return self.es.index(
            index=index_name,
            body=log_data
        )
    
    def search_logs(self, filters=None, size=100, sort_order='desc'):
        """Search logs with filters."""
        search = Search(using=self.es, index=f"{self.index_prefix}-*")
        
        if filters:
            for filter_clause in filters:
                search = search.filter(Q(filter_clause))
        
        search = search.sort({
            '@timestamp': {'order': sort_order}
        })[:size]
        
        response = search.execute()
        return [hit.to_dict() for hit in response]
    
    def search_logs_advanced(self, query, size=100):
        """Advanced search with custom query."""
        search = Search(using=self.es, index=f"{self.index_prefix}-*")
        search = search.query(Q(query))
        search = search.sort({'@timestamp': {'order': 'desc'}})[:size]
        
        response = search.execute()
        
        return {
            'total': response.hits.total.value,
            'hits': [{'_source': hit.to_dict()} for hit in response]
        }
    
    def stream_logs(self, filters=None):
        """Stream logs in real-time."""
        # Implementation for real-time log streaming
        # This would typically use Elasticsearch's scroll API
        # or integrate with a message queue for real-time updates
        pass
    
    def aggregate_logs(self, field, filters=None, time_range='24h'):
        """Aggregate logs by field."""
        search = Search(using=self.es, index=f"{self.index_prefix}-*")
        
        if filters:
            for filter_clause in filters:
                search = search.filter(Q(filter_clause))
        
        # Add time range filter
        search = search.filter('range', **{
            '@timestamp': {
                'gte': f'now-{time_range}'
            }
        })
        
        # Add aggregation
        agg = A('terms', field=f'{field}.keyword', size=50)
        search.aggs.bucket('field_agg', agg)
        
        response = search.execute()
        
        return {
            'buckets': [
                {
                    'key': bucket.key,
                    'doc_count': bucket.doc_count
                }
                for bucket in response.aggregations.field_agg.buckets
            ]
        }
```

**Log Collector (collectors/docker_logs.py):**
```python
import docker
import json
import threading
from datetime import datetime
from ..storage.elasticsearch import ElasticsearchClient
from ..processors.parsers import LogParser

class DockerLogCollector:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.es_client = ElasticsearchClient()
        self.parser = LogParser()
        self.active_streams = {}
    
    def start_collection(self, container_id, service_name):
        """Start collecting logs from a Docker container."""
        if container_id in self.active_streams:
            return  # Already collecting
        
        try:
            container = self.docker_client.containers.get(container_id)
            
            # Start log streaming in a separate thread
            thread = threading.Thread(
                target=self._stream_container_logs,
                args=(container, service_name),
                daemon=True
            )
            thread.start()
            
            self.active_streams[container_id] = {
                'thread': thread,
                'service_name': service_name,
                'started_at': datetime.utcnow()
            }
            
        except docker.errors.NotFound:
            print(f"Container {container_id} not found")
    
    def stop_collection(self, container_id):
        """Stop collecting logs from a container."""
        if container_id in self.active_streams:
            # Note: In a real implementation, you'd need a way to signal
            # the thread to stop gracefully
            del self.active_streams[container_id]
    
    def _stream_container_logs(self, container, service_name):
        """Stream logs from a container and index them."""
        try:
            for log_line in container.logs(stream=True, follow=True):
                log_text = log_line.decode('utf-8').strip()
                
                if not log_text:
                    continue
                
                # Parse the log line
                parsed_log = self.parser.parse_log_line(log_text, service_name)
                
                # Add container metadata
                parsed_log.update({
                    'container_id': container.id,
                    'container_name': container.name,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'service': service_name,
                    '@timestamp': datetime.utcnow().isoformat()
                })
                
                # Index the log
                self.es_client.index_log(parsed_log)
                
        except Exception as e:
            print(f"Error streaming logs from container {container.id}: {e}")
```

### Capability-Based Security Model

**Capability System:**
```python
# Addon capabilities define what system resources they can access
ADDON_CAPABILITIES = {
    'filesystem': {
        'read': ['logs', 'configs'],
        'write': ['temp', 'addon_data']
    },
    'network': {
        'outbound': ['https', 'webhooks'],
        'inbound': ['api_endpoints']
    },
    'system': {
        'commands': ['docker', 'systemctl'],
        'services': ['nginx', 'postgresql']
    },
    'data': {
        'models': ['deployments', 'services'],
        'apis': ['webops_api', 'external_apis']
    }
}
```

**Permission Validation:**
```python
class AddonSecurityManager:
    def validate_capability(self, addon_name: str, capability: str, resource: str) -> bool:
        """Validate if addon has permission for specific capability"""
        addon_manifest = self.get_addon_manifest(addon_name)
        return capability in addon_manifest.get('capabilities', [])
    
    def sandbox_execution(self, addon_func: callable, context: dict):
        """Execute addon code in sandboxed environment"""
        # Implement capability-based sandboxing
        pass
```

### Code Signing and Verification

**Addon Signing Process:**
```yaml
# addon.yaml with signature
signature:
  algorithm: RSA-SHA256
  public_key_id: webops-community-2024
  signature_data: |
    -----BEGIN SIGNATURE-----
    [Base64 encoded signature]
    -----END SIGNATURE-----
```

**Verification Implementation:**
```python
class AddonVerifier:
    def verify_signature(self, addon_path: str) -> bool:
        """Verify addon signature against trusted public keys"""
        manifest = self.load_manifest(addon_path)
        signature_data = manifest.get('signature', {})
        
        # Verify against trusted key registry
        return self.crypto_verify(addon_path, signature_data)
    
    def check_integrity(self, addon_path: str) -> bool:
        """Verify addon file integrity"""
        # Check file hashes, detect tampering
        pass
```

### Secrets and Configuration Management

**Secure Configuration Storage:**
```python
# Encrypted addon settings storage
class AddonConfigManager:
    def store_secret(self, addon_name: str, key: str, value: str):
        """Store encrypted addon secrets"""
        encrypted_value = self.encrypt(value, self.get_addon_key(addon_name))
        AddonSecret.objects.create(
            addon=addon_name,
            key=key,
            encrypted_value=encrypted_value
        )
    
    def get_secret(self, addon_name: str, key: str) -> str:
        """Retrieve and decrypt addon secret"""
        secret = AddonSecret.objects.get(addon=addon_name, key=key)
        return self.decrypt(secret.encrypted_value, self.get_addon_key(addon_name))
```

### Runtime Isolation

**Process Isolation:**
```python
class AddonExecutor:
    def execute_with_limits(self, addon_func: callable, limits: dict):
        """Execute addon code with resource limits"""
        import resource
        
        # Set memory limits
        resource.setrlimit(resource.RLIMIT_AS, (limits['memory'], limits['memory']))
        
        # Set CPU time limits  
        resource.setrlimit(resource.RLIMIT_CPU, (limits['cpu_time'], limits['cpu_time']))
        
        # Execute in separate process
        return self.run_in_subprocess(addon_func)
```

### Audit and Monitoring

**Addon Activity Logging:**
```python
class AddonAuditLogger:
    def log_addon_action(self, addon_name: str, action: str, details: dict):
        """Log addon actions for security audit"""
        AddonAuditLog.objects.create(
            addon=addon_name,
            action=action,
            details=json.dumps(details),
            timestamp=timezone.now(),
            user=self.get_current_user()
        )
    
    def detect_suspicious_activity(self, addon_name: str) -> list:
        """Detect potentially malicious addon behavior"""
        # Analyze patterns, rate limits, unusual API calls
        pass
```

### Governance Policies

**Addon Review Process:**
1. **Automated Security Scan:** Static analysis, dependency vulnerability check
2. **Code Review:** Manual review for community/marketplace addons  
3. **Testing Requirements:** Unit tests, integration tests, security tests
4. **Documentation Standards:** API docs, security considerations, usage examples

**Marketplace Governance:**
```yaml
# Addon marketplace metadata
marketplace:
  category: integration
  maturity: stable  # alpha, beta, stable
  support_level: community  # community, commercial, official
  security_review: passed
  last_updated: 2024-01-15
  download_count: 1250
  rating: 4.8
```

## Addon Contract

### Manifest Schema (`addon.yaml`)

```yaml
# Required fields
name: slack-notifications
version: 1.0.0
description: Send deployment notifications to Slack channels
author: WebOps Community
license: MIT
webops_version: ">=2.0.0"

# Capabilities and permissions
capabilities:
  - notifications
  - webhooks
  - api_access

# Integration points
hooks:
  - post_deployment
  - service_health_check
  - backup_complete

# Optional Django app integration
django_app: slack_addon

# Optional CLI command integration  
cli_commands: slack_addon.cli:slack_group

# Dependencies
dependencies:
  - slack-sdk>=3.0.0
  - requests>=2.28.0

# Configuration schema
settings_schema:
  webhook_url:
    type: string
    required: true
    description: Slack webhook URL for notifications
    validation: ^https://hooks\.slack\.com/.*
  default_channel:
    type: string
    default: "#deployments"
    description: Default Slack channel for notifications
  notification_level:
    type: enum
    options: [info, warning, error, critical]
    default: info
    description: Minimum notification level

# Security and governance
signature:
  algorithm: RSA-SHA256
  public_key_id: webops-community-2024
  signature_data: |
    -----BEGIN SIGNATURE-----
    [Base64 encoded signature]
    -----END SIGNATURE-----

# Marketplace metadata (optional)
marketplace:
  category: integration
  tags: [slack, notifications, messaging]
  maturity: stable
  support_level: community
  homepage: https://github.com/webops/addon-slack
  documentation: https://docs.webops.dev/addons/slack
```

### Python Module Contract

**Required Exports:**
```python
# addon_module/__init__.py
def register() -> dict:
    """Return addon registration information"""
    return {
        'cli_commands': get_cli_commands(),
        'django_app': get_django_app_config(),
        'hooks': get_hook_registrations(),
        'providers': get_provider_classes(),
        'api_routes': get_api_routes()
    }

def get_cli_commands() -> list:
    """Return CLI command groups for registration"""
    from .cli import slack_group
    return [slack_group]

def get_django_app_config():
    """Return Django AppConfig if addon provides web interface"""
    from .apps import SlackAddonConfig
    return SlackAddonConfig

def get_hook_registrations() -> dict:
    """Return hook callbacks for system events"""
    from .hooks import post_deployment_notification
    return {
        'post_deployment': [post_deployment_notification],
        'service_health_check': []
    }
```

## Migration Strategy and Backward Compatibility

### Phased Implementation Approach

**Phase 1: Foundation (Weeks 1-2)**
- Implement addon discovery and loading system
- Create basic CLI `webops addon` commands
- Establish addon manifest validation
- Build simple hook registry

**Phase 2: Core Integration (Weeks 3-4)**  
- Django app dynamic loading
- CLI command registration system
- Basic security framework (capabilities)
- Configuration management

**Phase 3: Advanced Features (Weeks 5-6)**
- Code signing and verification
- Runtime isolation and sandboxing
- Audit logging and monitoring
- Marketplace integration

**Phase 4: Production Readiness (Weeks 7-8)**
- Performance optimization
- Comprehensive testing
- Documentation and examples
- Migration tools for existing customizations

### Backward Compatibility Strategy

**Existing Customization Migration:**
```python
# Migration tool for existing custom scripts
class LegacyMigrationTool:
    def migrate_custom_scripts(self, scripts_dir: str) -> list:
        """Convert existing custom scripts to addon format"""
        migrations = []
        
        for script in self.find_custom_scripts(scripts_dir):
            addon_structure = self.analyze_script(script)
            addon_manifest = self.generate_manifest(addon_structure)
            migrations.append({
                'original': script,
                'addon_path': self.create_addon_structure(addon_manifest),
                'migration_notes': addon_structure['notes']
            })
        
        return migrations
    
    def migrate_django_customizations(self, apps_dir: str) -> list:
        """Convert existing Django app customizations"""
        # Analyze existing apps and create addon wrappers
        pass
```

**Configuration Migration:**
```python
# Migrate existing configuration to addon settings
def migrate_existing_config():
    """Migrate existing WebOps configuration to addon format"""
    
    # Identify configuration that should become addon settings
    legacy_config = load_legacy_config()
    
    addon_configs = {
        'slack-notifications': {
            'webhook_url': legacy_config.get('SLACK_WEBHOOK_URL'),
            'default_channel': legacy_config.get('SLACK_DEFAULT_CHANNEL', '#deployments')
        },
        'monitoring': {
            'datadog_api_key': legacy_config.get('DATADOG_API_KEY'),
            'alert_thresholds': legacy_config.get('ALERT_THRESHOLDS', {})
        }
    }
    
    # Create addon configurations
    for addon_name, config in addon_configs.items():
        if config and any(config.values()):
            create_addon_config(addon_name, config)
```

### Version Compatibility Matrix

```yaml
# Addon compatibility with WebOps versions
compatibility_matrix:
  webops_2.0.x:
    addon_api_version: 1.0
    supported_capabilities: [basic_hooks, cli_commands, django_apps]
    deprecated_features: []
    
  webops_2.1.x:
    addon_api_version: 1.1
    supported_capabilities: [basic_hooks, cli_commands, django_apps, advanced_security]
    deprecated_features: [legacy_hook_format]
    
  webops_2.2.x:
    addon_api_version: 1.2
    supported_capabilities: [all]
    deprecated_features: [legacy_hook_format, old_manifest_schema]
```

### Rollback and Safety Mechanisms

**Safe Addon Management:**
```python
class AddonSafetyManager:
    def safe_install(self, addon_path: str) -> dict:
        """Install addon with rollback capability"""
        checkpoint = self.create_system_checkpoint()
        
        try:
            result = self.install_addon(addon_path)
            self.validate_system_health()
            return result
        except Exception as e:
            self.rollback_to_checkpoint(checkpoint)
            raise AddonInstallationError(f"Installation failed: {e}")
    
    def validate_system_health(self):
        """Ensure system is still functional after addon changes"""
        # Check critical services, API endpoints, CLI functionality
        pass
```

### Example Manifest (sketch)

```yaml
name: "Slack Notifications"
slug: "slack"
version: "1.0.0"
webops_api: ">=1.2.0"
capabilities: ["add_cli", "add_ui", "use_network", "read_secrets"]
hooks:
  deployment.post_create: "slack.hooks.on_deployment_create"
settings:
  webhook_url: { type: "string", secret: true }
ui:
  admin_panel: { template: "templates/slack/settings.html", static: "static/slack/" }
cli:
  commands: ["slack.notify"]
```

## Lifecycle

- Install: fetch, verify signature, parse manifest, register.
- Enable: add to `INSTALLED_APPS` (if server), expose CLI commands, run migrations.
- Configure: apply settings and secrets via Control Panel or CLI.
- Update: check compatibility, run migrations, perform schema changes.
- Disable: unload commands/routes, hide UI, stop hooks.
- Uninstall: clean migrations and assets if opted; leave data per policy.

## Hook Registry

- Deployment: `deployment.pre_create`, `deployment.post_create`, `deployment.post_update`, `deployment.deleted`
- Databases: `database.backup.completed`, `database.provisioned`, `database.decommissioned`
- Services: `service.health_changed`, `service.scaled`, `ssl.certificate.renewed`
- System: `user.invited`, `org.plan_changed`, `audit.event_logged`
- CLI: `cli.before_command`, `cli.after_command`, `cli.error`

## Security & Governance

- Capabilities and permissions: addons declare needs; admins approve.
- Isolation: run risky hooks in subprocess or containers; restrict imports and environment.
- Secrets: use central secret manager and avoid exposing raw values in logs.
- Signing: accept signed wheels/zips; verify publisher; maintain allowlist/denylist.
- Telemetry: per-addon audit trail (installed, enabled, hooks executed, resource usage).

## Distribution & Installation

- Local development: load from `addons/` directory or editable pip installs.
- Packages: publish wheels to internal or public index; discover via `entry_points`.
- Sources: path, VCS URL, registry URL.
- CLI: `webops addon install <source>`, `enable`, `disable`, `configure`, `remove`, `list`.
- Control Panel: Addons page for install, enable, configure, and status.

## Versioning & Compatibility

- Use semantic versioning with strict `webops_api` ranges.
- Feature flags for progressive rollout.
- Backward-compatible hook signatures; deprecate with warnings and timelines.

## Data Model (Control Panel)

- `Addon` model: `slug`, `name`, `version`, `enabled`, `capabilities`, `config`, `publisher`, `verified`.
- `AddonEvent` for audit logs; `AddonSecretBinding` for secret references.
- Admin UI: list, details, configuration, logs.

## CLI Integration

- New root command: `webops addon`.
- Subcommands: `list`, `install`, `enable`, `disable`, `configure`, `remove`, `info`.
- Integrate help texts and examples with `cli` flows.

## UI/UX

- Control Panel: “Addons” section aligned with `docs/reference/design-system-v2.md`.
- Clear states: installed vs enabled, compatibility warnings, required settings.
- Per-addon Settings page with validation and environment targeting.

## MVP Scope

### Phase 1: Foundation (Essential Addons Priority)
- Define comprehensive `addon.yaml` schema with security and capability model
- Implement addon discovery in CLI via Python `entry_points`
- Implement server addon loader: dynamic `INSTALLED_APPS` via manifest
- Create robust hook registry system with pre/post deployment hooks
- Add comprehensive "Addons" page in Control Panel: list, install, enable/disable, configure
- Implement capability-based security model with permission validation

### Phase 2: Essential Addons Implementation
**Priority 1: CI/CD Pipeline Integration Addon**
- GitHub Actions, GitLab CI, and Jenkins integration
- Pipeline status tracking and deployment gates
- Build artifact management and coordination
- Webhook handlers for real-time pipeline updates
- CLI commands: `webops pipeline status`, `webops artifacts deploy`, `webops gates configure`

**Priority 2: Log Aggregation and Analytics Addon**
- Centralized log collection from all deployments
- Elasticsearch/ELK stack integration
- Real-time log streaming with WebSocket support
- Advanced search and filtering capabilities
- Log analytics with pattern detection and anomaly alerts
- CLI commands: `webops logs tail`, `webops logs search`, `webops logs analyze`

### Phase 3: Core Integration Features
- Code signing and verification system for addon security
- Secrets management with encrypted storage and capability-based access
- Runtime isolation with resource limits and subprocess execution
- Audit logging and monitoring for all addon activities
- Migration tools for existing customizations and configurations

### Phase 4: Production Readiness
- Addon marketplace with governance policies and review process
- Advanced analytics and monitoring for addon performance
- Comprehensive testing framework for addon validation
- Documentation and developer tools for addon creation
- Enterprise features: role-based access control, compliance reporting

## Assumptions To Validate

- Third-party addons are desired in addition to internal extensions.
- Both CLI and Control Panel should be extensible.
- Addons may need network access and secrets with admin approval.
- Prefer Python packaging with entry points for discovery.

## Open Questions

- Which addon types are highest priority (CLI, UI, providers, integrations)?
- Do we need strict sandboxing (containers) from the start, or is subprocess isolation sufficient initially?
- Should addons contribute `nginx/systemd` template fragments, or keep infra templates limited to core for now?
- Do we want an internal registry, or rely on filesystem/VCS installs for early phases?

## Next Steps

### Immediate Actions (Phase 1 - Foundation)
1. **Finalize Addon Contract Specification**
   - Complete `addon.yaml` schema validation rules
   - Define comprehensive hook registry with event types
   - Establish capability-based security model documentation

2. **Implement Core Infrastructure**
   - Scaffold CLI `webops addon` command group with discovery mechanisms
   - Build server-side addon loader with dynamic Django app integration
   - Create Control Panel addon management interface with security controls

3. **Security and Governance Framework**
   - Implement code signing and verification system
   - Design secrets management with encrypted storage
   - Establish audit logging for all addon operations

### Priority Implementation (Phase 2 - Essential Addons)
4. **CI/CD Pipeline Integration Addon Development**
   - Build GitHub Actions integration with webhook handlers
   - Implement pipeline status tracking and deployment gates
   - Create CLI commands for pipeline management and artifact deployment
   - Validate end-to-end CI/CD workflow integration

5. **Log Aggregation and Analytics Addon Development**
   - Integrate Elasticsearch/ELK stack for centralized logging
   - Implement real-time log streaming with WebSocket support
   - Build advanced search and analytics capabilities
   - Create CLI commands for log management and analysis

### Validation and Testing (Phase 3)
6. **End-to-End Testing**
   - Test addon installation, configuration, and lifecycle management
   - Validate security model with capability restrictions
   - Performance testing with multiple addons enabled
   - Integration testing with existing WebOps features

7. **Documentation and Developer Experience**
   - Complete developer guide for addon creation
   - Create comprehensive API documentation
   - Build example addons and tutorials
   - Establish addon review and certification process

### Future Roadmap (Phase 4)
8. **Marketplace and Ecosystem**
   - Design addon marketplace with governance policies
   - Implement addon discovery and rating system
   - Create enterprise features for compliance and monitoring
   - Build community contribution guidelines and tools

### Success Metrics
- **Technical:** Addon system supports 10+ concurrent addons without performance degradation
- **Developer Experience:** New addon development time reduced to <2 days for simple integrations
- **Security:** Zero security incidents related to addon vulnerabilities in first 6 months
- **Adoption:** 80% of WebOps deployments use at least one of the essential addons within 3 months