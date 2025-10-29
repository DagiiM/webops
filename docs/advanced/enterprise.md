# WebOps Enterprise Features

**Advanced Capabilities for Large Organizations**

## Overview

WebOps Enterprise Edition provides enhanced features for large organizations requiring advanced security, compliance, team collaboration, and scalability beyond the standard offering.

## Enterprise Architecture

### Multi-Tenancy Support

#### Organization Structure
```python
# models.py
class Organization(models.Model):
    """Top-level organization entity."""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Billing and subscription information
    subscription_tier = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_TIERS,
        default='standard'
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS,
        default='active'
    )
    
    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

class Team(models.Model):
    """Team within an organization."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['organization', 'name']
        verbose_name = "Team"
        verbose_name_plural = "Teams"
```

#### Resource Isolation
```python
# Middleware for organization context
class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set organization context based on subdomain or header
        organization_slug = self.get_organization_slug(request)
        
        if organization_slug:
            try:
                organization = Organization.objects.get(slug=organization_slug)
                request.organization = organization
            except Organization.DoesNotExist:
                return HttpResponse('Organization not found', status=404)
        
        response = self.get_response(request)
        return response
    
    def get_organization_slug(self, request):
        # Get from subdomain: org-slug.webops.example.com
        host = request.get_host()
        if '.webops.example.com' in host:
            return host.split('.')[0]
        
        # Get from custom domain: org-slug.com
        # Implement custom domain resolution
        
        # Get from header (for API requests)
        return request.headers.get('X-Organization-Slug')
```

## Advanced Security

### Role-Based Access Control (RBAC)

#### Permission System
```python
# models.py
class Role(models.Model):
    """Predefined roles with specific permissions."""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    permissions = models.ManyToManyField('Permission', blank=True)
    
    # Built-in roles
    BUILTIN_ROLES = {
        'owner': ['*'],  # Full access
        'admin': ['deployment.*', 'user.manage', 'team.manage'],
        'developer': ['deployment.create', 'deployment.view', 'deployment.update'],
        'viewer': ['deployment.view', 'log.view'],
    }
    
    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"

class UserOrganization(models.Model):
    """Many-to-many relationship between users and organizations with roles."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    teams = models.ManyToManyField(Team, blank=True)
    
    class Meta:
        unique_together = ['user', 'organization']
        verbose_name = "User Organization"
        verbose_name_plural = "User Organizations"
```

#### Permission Checking
```python
# utils/permissions.py
from django.core.exceptions import PermissionDenied

def has_permission(user, permission_string, organization=None):
    """Check if user has specific permission."""
    if organization is None:
        organization = get_current_organization()
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    try:
        user_org = UserOrganization.objects.get(
            user=user,
            organization=organization
        )
        
        # Check if role has wildcard permission
        if '*' in user_org.role.permissions:
            return True
        
        # Check specific permission
        return permission_string in user_org.role.permissions
    
    except UserOrganization.DoesNotExist:
        return False

def permission_required(permission):
    """Decorator for view permission checking."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not has_permission(request.user, permission):
                raise PermissionDenied("Insufficient permissions")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
```

### Advanced Authentication

#### SAML/SSO Integration
```python
# settings.py
INSTALLED_APPS = [
    'django_saml2_auth',  # SAML authentication
    # ... other apps
]

# SAML Configuration
SAML2_AUTH = {
    'METADATA_AUTO_CONF_URL': os.environ.get('SAML_METADATA_URL'),
    'ENTITY_ID': os.environ.get('SAML_ENTITY_ID'),
    'NAME_ID_FORMAT': os.environ.get('SAML_NAME_ID_FORMAT'),
    'USE_JWT': True,
    'JWT_SECRET': os.environ.get('SAML_JWT_SECRET'),
    'ATTRIBUTES_MAP': {
        'email': 'Email',
        'username': 'UserName',
        'first_name': 'FirstName',
        'last_name': 'LastName',
    }
}
```

#### Two-Factor Authentication (2FA)
```python
# models.py
class UserTwoFactor(models.Model):
    """2FA configuration for users."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    secret_key = models.CharField(max_length=32)  # Base32 encoded
    backup_codes = models.JSONField(default=list)
    last_used = models.DateTimeField(null=True, blank=True)
    
    def generate_backup_codes(self):
        """Generate 10 backup codes."""
        codes = [secrets.token_hex(5).upper() for _ in range(10)]
        self.backup_codes = codes
        self.save()
        return codes
    
    def verify_code(self, code):
        """Verify TOTP code."""
        if code in self.backup_codes:
            # Remove used backup code
            self.backup_codes.remove(code)
            self.save()
            return True
        
        # Verify TOTP
        totp = pyotp.TOTP(self.secret_key)
        return totp.verify(code)
```

## Team Collaboration

### Team Management

#### Team-Based Resource Access
```python
# models.py
class TeamDeploymentAccess(models.Model):
    """Control which teams can access which deployments."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE)
    permission_level = models.CharField(
        max_length=20,
        choices=PERMISSION_LEVELS,
        default='view'
    )
    
    class Meta:
        unique_together = ['team', 'deployment']
        verbose_name = "Team Deployment Access"
        verbose_name_plural = "Team Deployment Accesses"

class TeamEnvironment(models.Model):
    """Environment-specific team access."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES
    )
    allowed = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['team', 'environment']
        verbose_name = "Team Environment"
        verbose_name_plural = "Team Environments"
```

#### Team Invitations
```python
# models.py
class TeamInvitation(models.Model):
    """Invitations to join teams."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['team', 'email']
        verbose_name = "Team Invitation"
        verbose_name_plural = "Team Invitations"
    
    def generate_token(self):
        """Generate secure invitation token."""
        self.token = secrets.token_urlsafe(48)
        self.expires_at = timezone.now() + timedelta(days=7)
        self.save()
        return self.token
```

### Collaboration Features

#### Deployment Comments
```python
# models.py
class DeploymentComment(models.Model):
    """Comments on deployments for team collaboration."""
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Mention tracking
    mentions = models.ManyToManyField(User, related_name='mentioned_in_comments')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Deployment Comment"
        verbose_name_plural = "Deployment Comments"
```

#### Activity Feed
```python
# models.py
class Activity(models.Model):
    """System-wide activity feed."""
    ACTIONS = [
        ('deployment.created', 'Deployment Created'),
        ('deployment.updated', 'Deployment Updated'),
        ('deployment.deleted', 'Deployment Deleted'),
        ('user.joined', 'User Joined'),
        ('comment.added', 'Comment Added'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTIONS)
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]
        verbose_name = "Activity"
        verbose_name_plural = "Activities"
    
    @property
    def target(self):
        """Get the target object."""
        if self.target_content_type and self.target_object_id:
            return self.target_content_type.get_object_for_this_type(
                pk=self.target_object_id
            )
        return None
```

## Advanced Deployment Features

### Environment Management

#### Multiple Environments
```python
# models.py
class Environment(models.Model):
    """Deployment environments (development, staging, production)."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    is_production = models.BooleanField(default=False)
    
    # Environment-specific configuration
    domain_suffix = models.CharField(max_length=100)
    resource_limits = models.JSONField(default=dict)
    
    class Meta:
        unique_together = ['organization', 'slug']
        verbose_name = "Environment"
        verbose_name_plural = "Environments"

class DeploymentEnvironment(models.Model):
    """Link deployments to specific environments."""
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE)
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE)
    configuration = models.JSONField(default=dict)
    
    class Meta:
        unique_together = ['deployment', 'environment']
        verbose_name = "Deployment Environment"
        verbose_name_plural = "Deployment Environments"
```

#### Environment-Specific Configuration
```python
# utils/environment.py
def get_environment_config(deployment, environment_slug):
    """Get environment-specific configuration."""
    try:
        env = Environment.objects.get(
            organization=deployment.organization,
            slug=environment_slug
        )
        
        deployment_env = DeploymentEnvironment.objects.get(
            deployment=deployment,
            environment=env
        )
        
        return deployment_env.configuration
    
    except (Environment.DoesNotExist, DeploymentEnvironment.DoesNotExist):
        return {}
```

### Advanced Deployment Strategies

#### Blue-Green Deployments
```python
# services/deployment.py
class BlueGreenDeploymentService:
    """Blue-green deployment strategy."""
    
    def deploy(self, deployment, version):
        """Execute blue-green deployment."""
        # Create new environment (green)
        green_env = self.create_environment(deployment, f'green-{version}')
        
        # Deploy to green environment
        self.deploy_to_environment(deployment, green_env, version)
        
        # Run tests on green environment
        if self.run_tests(green_env):
            # Switch traffic from blue to green
            self.switch_traffic(deployment, green_env)
            
            # Clean up old blue environment
            self.cleanup_old_environments(deployment, version)
        else:
            # Tests failed, roll back
            self.rollback(deployment, green_env)
            raise DeploymentError("Deployment tests failed")
```

#### Canary Deployments
```python
# services/deployment.py
class CanaryDeploymentService:
    """Canary deployment strategy."""
    
    def deploy(self, deployment, version, percentage=10):
        """Execute canary deployment."""
        # Deploy to canary environment
        canary_env = self.create_canary_environment(deployment, version)
        self.deploy_to_environment(deployment, canary_env, version)
        
        # Route percentage of traffic to canary
        self.route_traffic(deployment, canary_env, percentage)
        
        # Monitor canary performance
        monitoring_data = self.monitor_canary(canary_env)
        
        if self.is_canary_successful(monitoring_data):
            # Gradually increase traffic
            for step in [25, 50, 75, 100]:
                self.route_traffic(deployment, canary_env, step)
                time.sleep(300)  # 5 minutes between steps
                
                if not self.is_canary_successful():
                    self.rollback_traffic(deployment)
                    raise DeploymentError("Canary deployment failed")
        else:
            # Canary failed, roll back
            self.rollback_traffic(deployment)
            raise DeploymentError("Canary deployment failed")
```

## Compliance and Governance

### Audit Logging

#### Comprehensive Audit Trail
```python
# models.py
class AuditLog(models.Model):
    """Comprehensive audit logging."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
```

#### Audit Log Middleware
```python
# middleware/audit.py
class AuditMiddleware:
    """Middleware to log all significant actions."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.auditable_actions = {
            'POST': ['create', 'update', 'delete'],
            'PUT': ['update'],
            'PATCH': ['update'],
            'DELETE': ['delete'],
        }

    def __call__(self, request):
        response = self.get_response(request)
        
        # Log auditable actions
        if request.method in self.auditable_actions:
            self.log_action(request, response)
        
        return response
    
    def log_action(self, request, response):
        """Log the action to audit log."""
        if not hasattr(request, 'organization'):
            return
        
        action = self.get_action_type(request)
        resource_type = self.get_resource_type(request)
        
        AuditLog.objects.create(
            organization=request.organization,
            user=request.user if request.user.is_authenticated else None,
            action=action,
            resource_type=resource_type,
            resource_id=self.get_resource_id(request),
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=self.get_action_details(request, response)
        )
```

### Compliance Features

#### Data Retention Policies
```python
# models.py
class RetentionPolicy(models.Model):
    """Data retention policies for compliance."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    resource_type = models.CharField(max_length=50)
    retention_period = models.DurationField()  # e.g., timedelta(days=365)
    action = models.CharField(
        max_length=20,
        choices=[('archive', 'Archive'), ('delete', 'Delete')]
    )
    enabled = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['organization', 'resource_type']
        verbose_name = "Retention Policy"
        verbose_name_plural = "Retention Policies"

# Management command to enforce retention policies
class Command(BaseCommand):
    help = 'Enforce data retention policies'
    
    def handle(self, *args, **options):
        policies = RetentionPolicy.objects.filter(enabled=True)
        
        for policy in policies:
            cutoff_date = timezone.now() - policy.retention_period
            
            if policy.resource_type == 'audit_log':
                records = AuditLog.objects.filter(
                    organization=policy.organization,
                    timestamp__lt=cutoff_date
                )
            elif policy.resource_type == 'deployment_log':
                records = DeploymentLog.objects.filter(
                    deployment__organization=policy.organization,
                    created_at__lt=cutoff_date
                )
            
            if policy.action == 'delete':
                records.delete()
            elif policy.action == 'archive':
                self.archive_records(records)
```

#### GDPR Compliance
```python
# utils/gdpr.py
class GDPRComplianceService:
    """GDPR compliance utilities."""
    
    def process_right_to_be_forgotten(self, user):
        """Process right to be forgotten request."""
        # Anonymize user data
        self.anonymize_user_data(user)
        
        # Delete or anonymize associated data
        self.process_user_associated_data(user)
        
        # Log the request
        self.log_compliance_action(user, 'right_to_be_forgotten')
    
    def process_data_portability(self, user):
        """Process data portability request."""
        # Gather all user data
        user_data = self.gather_user_data(user)
        
        # Format for portability
        export_data = self.format_export_data(user_data)
        
        # Generate export file
        export_file = self.generate_export_file(export_data)
        
        # Log the request
        self.log_compliance_action(user, 'data_portability')
        
        return export_file
```

## Advanced Monitoring and Analytics

### Custom Metrics and Dashboards

#### Performance Metrics
```python
# utils/metrics.py
class OrganizationMetrics:
    """Organization-level performance metrics."""
    
    def __init__(self, organization):
        self.organization = organization
    
    def get_deployment_metrics(self, period='30d'):
        """Get deployment performance metrics."""
        return {
            'success_rate': self.calculate_success_rate(period),
            'average_deployment_time': self.calculate_avg_deployment_time(period),
            'failure_reasons': self.analyze_failure_reasons(period),
            'resource_usage': self.get_resource_usage(period),
        }
    
    def calculate_success_rate(self, period):
        """Calculate deployment success rate."""
        deployments = ApplicationDeployment.objects.filter(
            organization=self.organization,
            created_at__gte=timezone.now() - parse_duration(period)
        )
        
        total = deployments.count()
        successful = deployments.filter(status='success').count()
        
        return (successful / total) * 100 if total > 0 else 0
```

#### Custom Dashboard API
```python
# views/api.py
class OrganizationMetricsView(APIView):
    """API endpoint for organization metrics."""
    
    @permission_required('metrics.view')
    def get(self, request, organization_slug):
        organization = get_object_or_404(Organization, slug=organization_slug)
        metrics_service = OrganizationMetrics(organization)
        
        period = request.GET.get('period', '30d')
        
        data = {
            'deployment_metrics': metrics_service.get_deployment_metrics(period),
            'user_metrics': metrics_service.get_user_metrics(period),
            'resource_metrics': metrics_service.get_resource_metrics(period),
            'cost_metrics': metrics_service.get_cost_metrics(period),
        }
        
        return Response(data)
```

### Advanced Alerting

#### Custom Alert Rules
```python
# models.py
class AlertRule(models.Model):
    """Custom alert rules for organizations."""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Alert conditions
    metric = models.CharField(max_length=50)  # e.g., 'deployment.success_rate'
    operator = models.CharField(max_length=10)  # e.g., '<', '>', '=='
    threshold = models.FloatField()
    duration = models.DurationField()  # How long condition must be true
    
    # Alert actions
    actions = models.JSONField(default=list)  # e.g., ['email', 'slack', 'webhook']
    
    enabled = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Alert Rule"
        verbose_name_plural = "Alert Rules"
    
    def evaluate(self):
        """Evaluate alert rule conditions."""
        metrics_service = OrganizationMetrics(self.organization)
        current_value = getattr(metrics_service, f'get_{self.metric}')()
        
        # Evaluate condition
        condition_met = self.evaluate_condition(current_value, self.operator, self.threshold)
        
        if condition_met:
            self.trigger_alert(current_value)
    
    def trigger_alert(self, current_value):
        """Trigger alert actions."""
        for action in self.actions:
            if action == 'email':
                self.send_email_alert(current_value)
            elif action == 'slack':
                self.send_slack_alert(current_value)
            elif action == 'webhook':
                self.trigger_webhook(current_value)
```

## Enterprise Support

### Premium Support

#### Support Ticket System
```python
# models.py
class SupportTicket(models.Model):
    """Enterprise support tickets."""
    PRIORITIES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITIES, default='normal')
    status = models.CharField(
        max_length=20,
        choices=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
        ],
        default='open'
    )
    
    # Support team assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
```

#### SLA Management
```python
# utils/sla.py
class SLAService:
    """Service Level Agreement management."""
    
    def __init__(self, organization):
        self.organization = organization
        self.sla_config = self.load_sla_config()
    
    def load_sla_config(self):
        """Load SLA configuration based on subscription tier."""
        tier = self.organization.subscription_tier
        
        sla_configs = {
            'enterprise': {
                'response_time': timedelta(hours=1),
                'resolution_time': timedelta(hours=4),
                'availability': 99.99,
            },
            'business': {
                'response_time': timedelta(hours=4),
                'resolution_time': timedelta(hours=8),
                'availability': 99.9,
            },
            'standard': {
                'response_time': timedelta(hours=8),
                'resolution_time': timedelta(hours=24),
                'availability': 99.5,
            },
        }
        
        return sla_configs.get(tier, sla_configs['standard'])
    
    def check_sla_compliance(self, ticket):
        """Check if ticket meets SLA requirements."""
        response_time = self.calculate_response_time(ticket)
        resolution_time = self.calculate_resolution_time(ticket)
        
        return {
            'response_time_met': response_time <= self.sla_config['response_time'],
            'resolution_time_met': resolution_time <= self.sla_config['resolution_time'],
            'response_time': response_time,
            'resolution_time': resolution_time,
        }
```

### Professional Services

#### Custom Integration Support
```python
# services/integration.py
class IntegrationService:
    """Custom integration support services."""
    
    def create_custom_integration(self, organization, requirements):
        """Create custom integration based on requirements."""
        # Validate requirements
        self.validate_requirements(requirements)
        
        # Design integration architecture
        architecture = self.design_integration_architecture(requirements)
        
        # Develop integration components
        components = self.develop_integration_components(architecture)
        
        # Test integration
        test_results = self.test_integration(components, requirements)
        
        # Deploy integration
        deployment = self.deploy_integration(components, organization)
        
        return {
            'architecture': architecture,
            'components': components,
            'test_results': test_results,
            'deployment': deployment,
        }
    
    def validate_requirements(self, requirements):
        """Validate integration requirements."""
        required_fields = ['name', 'description', 'systems', 'data_flow']
        
        for field in required_fields:
            if field not in requirements:
                raise ValidationError(f"Missing required field: {field}")
```

## Getting Started with Enterprise Features

### Enable Enterprise Mode

#### Configuration
```bash
# Enable enterprise features
export WEBOPS_ENTERPRISE=true

# Set organization mode
export ORGANIZATION_MODE=multi-tenant

# Configure SAML/SSO
export SAML_ENABLED=true
export SAML_METADATA_URL=https://idp.example.com/metadata
export SAML_ENTITY_ID=https://webops.example.com/saml2
```

#### Initial Setup
```python
# Create initial organization
organization = Organization.objects.create(
    name="Example Corp",
    slug="example-corp",
    subscription_tier="enterprise"
)

# Create admin user
admin_user = User.objects.create_superuser(
    username="admin@example.com",
    email="admin@example.com",
    password="secure_password"
)

# Assign organization admin role
UserOrganization.objects.create(
    user=admin_user,
    organization=organization,
    role=Role.objects.get(name="owner")
)
```

### Migration from Standard Edition

#### Data Migration
```python
# Migration script for existing users
def migrate_to_enterprise():
    """Migrate existing users to enterprise structure."""
    
    # Create default organization
    default_org = Organization.objects.create(
        name="Default Organization",
        slug="default",
        subscription_tier="enterprise"
    )
    
    # Migrate users
    for user in User.objects.all():
        UserOrganization.objects.create(
            user=user,
            organization=default_org,
            role=Role.objects.get(name="admin")
        )
    
    # Migrate deployments
    for deployment in ApplicationDeployment.objects.all():
        deployment.organization = default_org
        deployment.save()
```

---

**WebOps Enterprise Edition** - *Advanced features for large organizations*