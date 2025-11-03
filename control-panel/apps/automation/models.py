"""
Automation Workflow Models.

This module provides a visual workflow builder system for creating
automation pipelines with:
- Data sources (Google Docs, Custom URLs, Webhooks, etc.)
- Processors (LLMs, Transformers, Filters)
- Output handlers (Email, Webhooks, Database, etc.)
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.common.models import BaseModel
import json


class Workflow(BaseModel):
    """
    Automation workflow that connects data sources, processors, and outputs.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        DISABLED = 'disabled', 'Disabled'

    class TriggerType(models.TextChoices):
        MANUAL = 'manual', 'Manual Trigger'
        SCHEDULE = 'schedule', 'Scheduled'
        WEBHOOK = 'webhook', 'Webhook'
        EVENT = 'event', 'Event-Based'

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflows')

    # Status and configuration
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices, default=TriggerType.MANUAL)

    # Schedule configuration (for scheduled workflows)
    schedule_cron = models.CharField(
        max_length=100,
        blank=True,
        help_text='Cron expression for scheduled workflows'
    )

    # Visual canvas data
    canvas_data = models.JSONField(
        default=dict,
        help_text='Visual canvas state (nodes, connections, positions)'
    )

    # Execution statistics
    total_executions = models.IntegerField(default=0)
    successful_executions = models.IntegerField(default=0)
    failed_executions = models.IntegerField(default=0)
    last_executed_at = models.DateTimeField(null=True, blank=True)
    average_duration_ms = models.IntegerField(default=0)

    # Settings
    timeout_seconds = models.IntegerField(default=300, help_text='Workflow timeout in seconds')
    retry_on_failure = models.BooleanField(default=True)
    max_retries = models.IntegerField(default=3)

    class Meta:
        db_table = 'automation_workflows'
        verbose_name = 'Workflow'
        verbose_name_plural = 'Workflows'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"


class WorkflowNode(BaseModel):
    """
    Individual node in a workflow (data source, processor, or output).
    """

    class NodeType(models.TextChoices):
        # Data Sources
        DATA_SOURCE_GOOGLE_DOCS = 'google_docs', 'Google Docs'
        DATA_SOURCE_GOOGLE_SHEETS = 'google_sheets', 'Google Sheets'
        DATA_SOURCE_WEBHOOK = 'webhook', 'Webhook Input'
        DATA_SOURCE_DATABASE = 'database', 'Database Query'
        DATA_SOURCE_API = 'api', 'API Request'
        DATA_SOURCE_FILE = 'file', 'File Input'
        DATA_SOURCE_CUSTOM_URL = 'custom_url', 'Custom URL'

        # Processors
        PROCESSOR_LLM = 'llm', 'LLM Processor'
        PROCESSOR_TRANSFORM = 'transform', 'Data Transform'
        PROCESSOR_FILTER = 'filter', 'Filter'
        PROCESSOR_AGGREGATE = 'aggregate', 'Aggregate'
        PROCESSOR_SPLIT = 'split', 'Split'
        PROCESSOR_MERGE = 'merge', 'Merge'
        PROCESSOR_CODE = 'code', 'Custom Code'

        # Outputs
        OUTPUT_EMAIL = 'email', 'Email'
        OUTPUT_WEBHOOK = 'webhook_output', 'Webhook Output'
        OUTPUT_DATABASE = 'database_output', 'Database Write'
        OUTPUT_FILE = 'file_output', 'File Output'
        OUTPUT_SLACK = 'slack', 'Slack Message'
        OUTPUT_API = 'api_output', 'API Call'
        OUTPUT_NOTIFICATION = 'notification', 'System Notification'

        # Control Flow
        CONTROL_CONDITION = 'condition', 'Conditional'
        CONTROL_LOOP = 'loop', 'Loop'
        CONTROL_DELAY = 'delay', 'Delay'
        CONTROL_ERROR_HANDLER = 'error_handler', 'Error Handler'

        # Agent Integration
        AGENT_TASK = 'agent_task', 'Agent Task'
        AGENT_QUERY = 'agent_query', 'Agent Query'
        AGENT_MEMORY = 'agent_memory', 'Agent Memory'
        AGENT_DECISION = 'agent_decision', 'Agent Decision'
        AGENT_LEARNING = 'agent_learning', 'Agent Learning'

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='nodes')

    # Node identification
    node_id = models.CharField(max_length=100, help_text='Unique ID within workflow')
    node_type = models.CharField(max_length=50, choices=NodeType.choices)
    label = models.CharField(max_length=255)

    # Visual position on canvas
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)

    # Node configuration
    config = models.JSONField(
        default=dict,
        help_text='Node-specific configuration (API keys, URLs, settings, etc.)'
    )

    # For addon-based nodes
    addon = models.ForeignKey(
        'addons.Addon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Linked addon for data source nodes'
    )

    # Execution settings
    enabled = models.BooleanField(default=True)
    timeout_seconds = models.IntegerField(default=60)
    retry_on_failure = models.BooleanField(default=False)
    max_retries = models.IntegerField(default=1)

    class Meta:
        db_table = 'automation_workflow_nodes'
        verbose_name = 'Workflow Node'
        verbose_name_plural = 'Workflow Nodes'
        unique_together = [['workflow', 'node_id']]
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"{self.label} ({self.get_node_type_display()})"


class WorkflowConnection(BaseModel):
    """
    Connection between two workflow nodes (edge in the graph).
    """

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='connections')

    # Source and target nodes
    source_node = models.ForeignKey(
        WorkflowNode,
        on_delete=models.CASCADE,
        related_name='outgoing_connections'
    )
    target_node = models.ForeignKey(
        WorkflowNode,
        on_delete=models.CASCADE,
        related_name='incoming_connections'
    )

    # Connection configuration
    source_handle = models.CharField(
        max_length=50,
        default='output',
        help_text='Output handle of source node'
    )
    target_handle = models.CharField(
        max_length=50,
        default='input',
        help_text='Input handle of target node'
    )

    # Conditional connection
    condition = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional condition for connection activation'
    )

    # Data transformation
    transform = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional data transformation between nodes'
    )

    class Meta:
        db_table = 'automation_workflow_connections'
        verbose_name = 'Workflow Connection'
        verbose_name_plural = 'Workflow Connections'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"{self.source_node.label} → {self.target_node.label}"


class WorkflowExecution(BaseModel):
    """
    Record of workflow execution.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        TIMEOUT = 'timeout', 'Timeout'

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='executions')

    # Execution details
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    # Trigger information
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    trigger_type = models.CharField(max_length=20)
    trigger_data = models.JSONField(default=dict, blank=True)

    # Results
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    error_traceback = models.TextField(blank=True)

    # Node execution logs
    node_logs = models.JSONField(
        default=list,
        help_text='Execution log for each node'
    )

    class Meta:
        db_table = 'automation_workflow_executions'
        verbose_name = 'Workflow Execution'
        verbose_name_plural = 'Workflow Executions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['workflow', '-started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self) -> str:
        return f"{self.workflow.name} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"


class WorkflowTemplate(BaseModel):
    """
    Pre-built workflow templates for common automation patterns.
    """

    class Category(models.TextChoices):
        DATA_PROCESSING = 'data_processing', 'Data Processing'
        CONTENT_GENERATION = 'content_generation', 'Content Generation'
        MONITORING = 'monitoring', 'Monitoring & Alerts'
        INTEGRATION = 'integration', 'Integration'
        CUSTOM = 'custom', 'Custom'

    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=Category.choices)

    # Template data
    workflow_data = models.JSONField(
        help_text='Complete workflow configuration (nodes, connections, settings)'
    )

    # Template metadata
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_official = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)

    # Preview image
    thumbnail_url = models.URLField(blank=True)

    class Meta:
        db_table = 'automation_workflow_templates'
        verbose_name = 'Workflow Template'
        verbose_name_plural = 'Workflow Templates'
        ordering = ['-usage_count', '-created_at']

    def __str__(self) -> str:
        return f"{self.name} ({self.get_category_display()})"


class DataSourceCredential(BaseModel):
    """
    Stored credentials for external data sources (encrypted).
    """

    class Provider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        GITHUB = 'github', 'GitHub'
        SLACK = 'slack', 'Slack'
        CUSTOM = 'custom', 'Custom API'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='data_source_credentials')
    provider = models.CharField(max_length=50, choices=Provider.choices)
    name = models.CharField(max_length=255, help_text='Friendly name for this credential')

    # Encrypted credentials
    credentials = models.JSONField(
        help_text='Encrypted credentials (tokens, keys, etc.)'
    )

    # Status
    is_valid = models.BooleanField(default=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'automation_data_source_credentials'
        verbose_name = 'Data Source Credential'
        verbose_name_plural = 'Data Source Credentials'
        unique_together = [['user', 'provider', 'name']]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.name} ({self.get_provider_display()})"

    def save(self, *args, **kwargs):
        """
        Override save to encrypt credentials before saving.
        """
        # Encrypt sensitive fields in credentials
        if self.credentials:
            self.credentials = self._encrypt_credentials(self.credentials)
        
        super().save(*args, **kwargs)

    def get_credentials(self) -> dict:
        """
        Get decrypted credentials.
        """
        if not self.credentials:
            return {}
        
        return self._decrypt_credentials(self.credentials)

    def _encrypt_credentials(self, credentials: dict) -> dict:
        """
        Encrypt sensitive fields in credentials.
        """
        from apps.core.utils import encrypt_password
        
        # Fields that should be encrypted
        sensitive_fields = [
            'api_key', 'token', 'access_token', 'refresh_token',
            'private_key', 'password', 'secret', 'client_secret'
        ]
        
        encrypted = {}
        for key, value in credentials.items():
            if any(field in key.lower() for field in sensitive_fields) and value:
                # Encrypt sensitive values
                if isinstance(value, str):
                    encrypted[key] = encrypt_password(value)
                else:
                    # For non-string values, convert to string, encrypt, and store
                    encrypted[key] = encrypt_password(str(value))
            else:
                # Keep non-sensitive values as-is
                encrypted[key] = value
        
        return encrypted

    def _decrypt_credentials(self, credentials: dict) -> dict:
        """
        Decrypt sensitive fields in credentials.
        """
        from apps.core.utils import decrypt_password
        
        # Fields that would have been encrypted
        sensitive_fields = [
            'api_key', 'token', 'access_token', 'refresh_token',
            'private_key', 'password', 'secret', 'client_secret'
        ]
        
        decrypted = {}
        for key, value in credentials.items():
            if any(field in key.lower() for field in sensitive_fields) and value:
                try:
                    # Try to decrypt sensitive values
                    if isinstance(value, str):
                        decrypted[key] = decrypt_password(value)
                    else:
                        # For non-string values, convert to string first
                        decrypted[key] = decrypt_password(str(value))
                except Exception:
                    # If decryption fails, keep the original value
                    # This handles the case where the value wasn't encrypted
                    decrypted[key] = value
            else:
                # Keep non-sensitive values as-is
                decrypted[key] = value
        
        return decrypted
