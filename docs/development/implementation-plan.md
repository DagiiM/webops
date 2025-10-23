# WebOps Production Readiness Implementation Plan

**Goal**: Make WebOps bulletproof for fresh VPS installations and intelligent for Django deployments

**Addresses Issues From**: audit.md - Deployment "Building" State Issues

---

## Executive Summary

This plan addresses the 7 critical issues identified in audit.md that cause deployments to get stuck in "Building" state:

1. ✅ **Celery Worker Not Running** - Enhanced service validation
2. ✅ **Redis Connection Issues** - Connection testing and recovery
3. ✅ **Permission Issues** - Comprehensive permission setup
4. ✅ **Missing Dependencies** - Robust dependency installation
5. ✅ **Insufficient System Resources** - Resource monitoring
6. ✅ **Repository Access Issues** - GitHub OAuth integration
7. ✅ **Configuration Issues** - Intelligent .env management

Additionally, we'll implement:
- Intelligent .env.example parsing with UI
- Auto-generation of required keys (SECRET_KEY, ENCRYPTION_KEY, etc.)
- Post-installation diagnostics
- Self-healing capabilities

---

## Phase 1: Enhanced setup.sh (Bulletproof VPS Installation)

### 1.1 Pre-Installation Validation

**Current Gap**: Basic checks for root, OS, and resources - but no service validation

**Enhancement**:
```bash
# New validation functions:
- check_internet_connectivity()      # Verify internet access
- check_dns_resolution()              # Verify DNS works
- check_package_manager()             # Verify apt-get works
- check_existing_services()           # Check for port conflicts
- validate_hostname()                 # Ensure valid hostname
- check_disk_io()                     # Verify disk write capability
```

**Location**: setup.sh lines 58-112

---

### 1.2 Robust Package Installation

**Current Gap**: No retry logic, no validation after installation

**Enhancement**:
```bash
install_with_retry() {
    # Install packages with:
    # - 3 retry attempts
    # - Exponential backoff
    # - Detailed error logging
    # - Fix broken packages automatically
    # - Validate installation success
}

validate_service_installation() {
    # After each service installation:
    # - Verify binary exists
    # - Test basic functionality
    # - Check service can start
    # - Log version information
}
```

**Services to validate**:
- PostgreSQL: Test psql command, check socket exists
- Redis: Test redis-cli ping
- Nginx: Test nginx -t (config validation)
- Python: Test python3 --version and venv creation

**Location**: setup.sh lines 118-242

---

### 1.3 Service Health Verification

**Current Gap**: Services are started but never verified as running

**Enhancement**:
```bash
verify_postgresql() {
    # - Check systemd status
    # - Test local connection with psql
    # - Verify port 5432 listening
    # - Test database creation
    # - Retry 3 times with 5s delays
}

verify_redis() {
    # - Check systemd status
    # - Test PING command
    # - Verify port 6379 listening
    # - Test SET/GET operations
}

verify_nginx() {
    # - Check systemd status
    # - Test config with nginx -t
    # - Verify port 80 listening
    # - Test HTTP request to localhost
}
```

**Location**: After each service installation (lines 176, 192, 206)

---

### 1.4 Enhanced Database Setup

**Current Gap**: Password generation works once, then fails on re-run

**Enhancement**:
```bash
setup_postgresql() {
    # Generate and STORE password securely
    POSTGRES_PASS_FILE="/opt/webops/.secrets/postgres_password"

    if [[ ! -f "$POSTGRES_PASS_FILE" ]]; then
        PG_PASSWORD=$(openssl rand -base64 32)
        mkdir -p /opt/webops/.secrets
        echo "$PG_PASSWORD" > "$POSTGRES_PASS_FILE"
        chmod 600 "$POSTGRES_PASS_FILE"

        # Create user with password
        sudo -u postgres psql -c "CREATE USER $WEBOPS_USER WITH PASSWORD '$PG_PASSWORD';"
    else
        # Password already exists, use it
        PG_PASSWORD=$(cat "$POSTGRES_PASS_FILE")
    fi

    # Store in .env file for control panel
    # Test database connection
    # Verify permissions
}
```

**Location**: setup.sh lines 284-306

---

### 1.5 Celery Worker Validation

**Current Gap**: Celery service is created but never verified to be processing tasks

**Enhancement**:
```bash
verify_celery_worker() {
    log_step "Verifying Celery worker is processing tasks..."

    # 1. Check systemd status
    systemctl is-active webops-celery

    # 2. Check process is running
    pgrep -f "celery.*worker"

    # 3. Test task execution (use Django management command)
    sudo -u $WEBOPS_USER $CONTROL_PANEL_DIR/venv/bin/python \
        $CONTROL_PANEL_DIR/manage.py test_celery_connection

    # 4. Check Redis connection from Celery
    # 5. Verify logs show "ready" message

    # Retry 5 times with 10s delays
}
```

**Location**: After systemd services creation (line 594)

**New Django Management Command Needed**:
```python
# apps/core/management/commands/test_celery_connection.py
# Simple task that verifies Celery is working
```

---

### 1.6 Post-Installation Diagnostics

**Current Gap**: No comprehensive system check after installation

**Enhancement**:
```bash
run_diagnostics() {
    log_step "Running post-installation diagnostics..."

    # Create diagnostic report
    DIAG_FILE="/opt/webops/installation-diagnostics.txt"

    {
        echo "WebOps Installation Diagnostics"
        echo "Generated: $(date)"
        echo "================================"
        echo ""

        # System info
        echo "[System Information]"
        uname -a
        cat /etc/os-release
        echo ""

        # Services status
        echo "[Service Status]"
        systemctl status postgresql --no-pager -l | head -10
        systemctl status redis-server --no-pager -l | head -10
        systemctl status nginx --no-pager -l | head -10
        systemctl status webops-web --no-pager -l | head -10
        systemctl status webops-celery --no-pager -l | head -10
        systemctl status webops-celerybeat --no-pager -l | head -10
        echo ""

        # Port status
        echo "[Port Status]"
        ss -tlnp | grep -E ':(80|443|5432|6379|8000)'
        echo ""

        # Directory permissions
        echo "[Directory Permissions]"
        ls -la /opt/webops/
        echo ""

        # Python packages
        echo "[Python Packages]"
    $CONTROL_PANEL_DIR/venv/bin/python -m pip list
        echo ""

        # Database connectivity
        echo "[Database Connectivity]"
        sudo -u postgres psql -l
        echo ""

        # Redis connectivity
        echo "[Redis Connectivity]"
        redis-cli ping
        echo ""

        # Nginx config test
        echo "[Nginx Configuration]"
        nginx -t

    } > "$DIAG_FILE" 2>&1

    log_info "Diagnostics saved to: $DIAG_FILE"

    # Check for critical errors
    if grep -qi "failed\|error\|inactive" "$DIAG_FILE"; then
        log_warn "Diagnostics detected potential issues. Review: $DIAG_FILE"
    else
        log_info "All diagnostics passed ✓"
    fi
}
```

**Location**: Before print_success_message (line 654)

---

### 1.7 Admin User Creation Fix

**Current Gap**: createsuperuser with --noinput doesn't set password

**Enhancement**:
```bash
create_admin_user() {
    log_info "Creating admin user..."

    # Use Django shell for better control
    sudo -u "$WEBOPS_USER" "$CONTROL_PANEL_DIR/venv/bin/python" \
        "$CONTROL_PANEL_DIR/manage.py" shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@webops.local',
        password='$(openssl rand -base64 16)'
    )
    print('Admin user created successfully')
else:
    print('Admin user already exists')
EOF

    # Store credentials for user
    echo "Admin username: admin" > /opt/webops/admin-credentials.txt
    echo "Admin password: (set during first login)" >> /opt/webops/admin-credentials.txt
    chmod 600 /opt/webops/admin-credentials.txt

    log_info "Admin credentials saved to /opt/webops/admin-credentials.txt"
}
```

**Location**: Replace lines 455-459

---

### 1.8 Idempotency Improvements

**Current Gap**: Script partially handles re-runs but not completely

**Enhancement**:
- Add state tracking file: `/opt/webops/.installation-state`
- Track completed steps: `packages_installed`, `services_configured`, etc.
- Allow selective re-run: `./setup.sh --retry-step services`
- Skip completed steps gracefully

```bash
# State tracking
STATE_FILE="/opt/webops/.installation-state"

mark_step_complete() {
    local step=$1
    echo "${step}=completed:$(date +%s)" >> "$STATE_FILE"
}

is_step_complete() {
    local step=$1
    grep -q "^${step}=completed" "$STATE_FILE" 2>/dev/null
}

run_step() {
    local step_name=$1
    local step_function=$2

    if is_step_complete "$step_name"; then
        log_info "Step '$step_name' already completed, skipping..."
        return 0
    fi

    log_step "Running step: $step_name"
    $step_function
    mark_step_complete "$step_name"
}
```

---

### 1.9 Cleanup on Failure

**Current Gap**: Partial installations leave system in inconsistent state

**Enhancement**:
```bash
cleanup_on_failure() {
    log_error "Installation failed! Cleaning up..."

    # Stop services
    systemctl stop webops-web 2>/dev/null || true
    systemctl stop webops-celery 2>/dev/null || true
    systemctl stop webops-celerybeat 2>/dev/null || true

    # Remove systemd files
    rm -f /etc/systemd/system/webops-*.service
    systemctl daemon-reload

    # Remove Nginx config
    rm -f /etc/nginx/sites-enabled/webops-panel.conf
    rm -f /etc/nginx/sites-available/webops-panel.conf

    # Keep /opt/webops for debugging
    log_warn "Installation files kept in /opt/webops for debugging"
    log_warn "To completely remove: sudo rm -rf /opt/webops"
}

# Set trap for cleanup
trap cleanup_on_failure ERR
```

---

## Phase 2: Intelligent Environment Variable Management

### 2.1 Integration of Existing env_parser.py

**Current State**: env_parser.py exists but is NOT used in deployment workflow

**Integration Points**:

1. **During Repository Clone** (services.py:256)
   - After cloning, immediately parse .env.example
   - Store parsed variables in deployment model

2. **Before Creating .env** (services.py:494)
   - Use env_parser instead of hardcoded template
   - Apply user-provided values
   - Auto-generate keys where needed

---

### 2.2 Enhanced Key Generation

**Current Gap**: Only generates SECRET_KEY, nothing else

**Enhancement** in `apps/core/utils.py`:
```python
def generate_django_secret_key() -> str:
    """Generate Django SECRET_KEY (50 chars recommended)."""
    chars = string.ascii_letters + string.digits + string.punctuation
    # Escape special chars for shell safety
    key = ''.join(secrets.choice(chars) for _ in range(50))
    return key.replace('$', '\\$').replace('`', '\\`')

def generate_fernet_key() -> str:
    """Generate Fernet encryption key for Django."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()

def generate_jwt_secret() -> str:
    """Generate JWT secret key."""
    return secrets.token_urlsafe(64)

def generate_database_url(deployment_name: str, password: str) -> str:
    """Generate DATABASE_URL for deployment."""
    db_name = f"{deployment_name}_db".replace('-', '_')
    username = deployment_name.replace('-', '_')
    return f"postgresql://{username}:{password}@localhost:5432/{db_name}"

def auto_generate_env_value(key: str, deployment: 'Deployment') -> str:
    """
    Auto-generate value for environment variable based on key name.

    Args:
        key: Environment variable key
        deployment: Deployment instance for context

    Returns:
        Generated value
    """
    key_lower = key.lower()

    # SECRET_KEY patterns
    if any(x in key_lower for x in ['secret_key', 'secretkey']):
        return generate_django_secret_key()

    # Encryption keys
    if any(x in key_lower for x in ['encryption_key', 'fernet_key']):
        return generate_fernet_key()

    # JWT secrets
    if any(x in key_lower for x in ['jwt_secret', 'token_secret']):
        return generate_jwt_secret()

    # Database URL
    if 'database_url' in key_lower or 'db_url' in key_lower:
        password = generate_password()
        return generate_database_url(deployment.name, password)

    # Debug mode
    if key_lower == 'debug':
        return 'False'

    # Allowed hosts
    if 'allowed_hosts' in key_lower:
        hosts = ['localhost', '127.0.0.1']
        if deployment.domain:
            hosts.append(deployment.domain)
        return ','.join(hosts)

    # Default: empty string
    return ''
```

---

### 2.3 Database Model Updates

**Add fields to Deployment model**:
```python
# apps/deployments/models.py

class Deployment(BaseModel):
    # ... existing fields ...

    # New fields for env management
    env_config_required = models.BooleanField(
        default=False,
        help_text="Whether this deployment requires .env configuration"
    )
    env_config_complete = models.BooleanField(
        default=False,
        help_text="Whether .env configuration is complete"
    )
    env_variables_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="Parsed .env.example schema"
    )

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIGURING = 'configuring', 'Awaiting Configuration'  # NEW
        BUILDING = 'building', 'Building'
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        FAILED = 'failed', 'Failed'
```

---

### 2.4 Enhanced Deployment Workflow

**New Workflow** in `services.py`:

```python
def prepare_deployment(self, deployment: Deployment) -> Tuple[bool, str]:
    """
    Enhanced deployment preparation with .env wizard.
    """
    try:
        # 1. Clone repository
        repo_path = self.clone_repository(deployment)

        # 2. Parse .env.example
        from .env_parser import EnvWizard
        wizard = EnvWizard(repo_path)
        wizard_data = wizard.get_wizard_data()

        # 3. Check if configuration needed
        if wizard_data['available']:
            self.log(
                deployment,
                f"Found .env.example with {len(wizard_data['variables'])} variables"
            )

            # Store schema for UI
            deployment.env_variables_schema = wizard_data
            deployment.env_config_required = True
            deployment.status = Deployment.Status.CONFIGURING
            deployment.save()

            # Return early - wait for user configuration
            return True, "needs_configuration"

        # 4. No .env needed, proceed normally
        return self._continue_deployment(deployment)

    except Exception as e:
        # ... error handling ...
```

**New method** for continuing after configuration:
```python
def apply_env_configuration(
    self,
    deployment: Deployment,
    user_values: Dict[str, str]
) -> Tuple[bool, str]:
    """
    Apply user-provided environment configuration.

    Args:
        deployment: Deployment instance
        user_values: User-provided values from UI form

    Returns:
        Tuple of (success, error_message)
    """
    from .env_parser import EnvWizard, EnvVariable
    from apps.core.utils import auto_generate_env_value

    repo_path = self.get_repo_path(deployment)
    wizard = EnvWizard(repo_path)

    # Parse schema
    found, variables, error = wizard.parser.parse_env_example()
    if not found:
        return False, error

    # Build final env dict
    final_env = {}

    for var in variables:
        if var.key in user_values and user_values[var.key]:
            # User provided value
            final_env[var.key] = user_values[var.key]
        elif var.key in user_values and user_values[var.key] == '<auto-generate>':
            # Auto-generate requested
            final_env[var.key] = auto_generate_env_value(var.key, deployment)
        elif var.default_value:
            # Use default
            final_env[var.key] = var.default_value
        else:
            # Auto-generate for required vars
            if var.required:
                final_env[var.key] = auto_generate_env_value(var.key, deployment)

    # Create .env file
    env_file = repo_path / '.env'
    env_content = '\n'.join(f"{k}={v}" for k, v in final_env.items())
    env_file.write_text(env_content)

    # Store in deployment model
    deployment.env_vars = final_env
    deployment.env_config_complete = True
    deployment.status = Deployment.Status.BUILDING
    deployment.save()

    self.log(
        deployment,
        "Environment configuration applied successfully",
        DeploymentLog.Level.SUCCESS
    )

    # Continue with normal deployment
    return self._continue_deployment(deployment)
```

---

## Phase 3: UI for Environment Variable Configuration

### 3.1 New View for Configuration

**Location**: `apps/deployments/views.py`

```python
@login_required
def deployment_configure(request, pk):
    """Configure environment variables for deployment."""
    deployment = get_object_or_404(Deployment, pk=pk)

    # Only show for deployments needing configuration
    if not deployment.env_config_required:
        return redirect('deployment_detail', pk=pk)

    if deployment.env_config_complete:
        messages.info(request, "Configuration already complete")
        return redirect('deployment_detail', pk=pk)

    if request.method == 'POST':
        # Collect user values
        user_values = {}
        for key in request.POST:
            if key.startswith('env_'):
                env_key = key[4:]  # Remove 'env_' prefix
                user_values[env_key] = request.POST[key]

        # Apply configuration
        from .services import DeploymentService
        service = DeploymentService()
        success, error = service.apply_env_configuration(deployment, user_values)

        if success:
            # Queue deployment task
            from .tasks import deploy_application
            deploy_application.delay(deployment.id)

            messages.success(
                request,
                "Configuration saved! Deployment started."
            )
            return redirect('deployment_detail', pk=pk)
        else:
            messages.error(request, f"Configuration failed: {error}")

    # Parse schema for form
    schema = deployment.env_variables_schema

    context = {
        'deployment': deployment,
        'categories': schema.get('categories', {}),
        'variables': schema.get('variables', []),
    }

    return render(request, 'deployments/configure_env.html', context)
```

---

### 3.2 New Template for Configuration

**Location**: `control-panel/templates/deployments/configure_env.html`

```html
{% extends "base.html" %}

{% block title %}Configure {{ deployment.name }} - WebOps{% endblock %}

{% block content %}
<div class="container">
    <div class="config-wizard">
        <h1>Configure Environment Variables</h1>
        <p class="subtitle">
            Your deployment requires environment configuration.
            Fill in the values below or use auto-generated values.
        </p>

        <div class="deployment-info">
            <strong>{{ deployment.name }}</strong>
            <span class="repo-url">{{ deployment.repo_url }}</span>
        </div>

        <form method="post" class="env-config-form">
            {% csrf_token %}

            {% for category, variables in categories.items %}
            <div class="env-category">
                <h2>{{ category }}</h2>

                {% for var in variables %}
                <div class="env-variable {% if var.is_secret %}is-secret{% endif %} {% if var.required %}required{% endif %}">
                    <label for="env_{{ var.key }}">
                        {{ var.key }}
                        {% if var.required %}
                        <span class="required-indicator">*</span>
                        {% endif %}
                    </label>

                    {% if var.comment %}
                    <p class="help-text">{{ var.comment }}</p>
                    {% endif %}

                    <div class="input-group">
                        {% if var.is_secret %}
                        <input
                            type="password"
                            id="env_{{ var.key }}"
                            name="env_{{ var.key }}"
                            value="{{ var.suggested_value }}"
                            {% if var.required %}required{% endif %}
                            placeholder="{{ var.suggested_value }}"
                        />
                        <button type="button" class="toggle-visibility" data-target="env_{{ var.key }}">
                            <span class="icon">👁️</span>
                        </button>
                        {% else %}
                        <input
                            type="text"
                            id="env_{{ var.key }}"
                            name="env_{{ var.key }}"
                            value="{{ var.default_value }}"
                            {% if var.required %}required{% endif %}
                            placeholder="{{ var.suggested_value }}"
                        />
                        {% endif %}

                        {% if var.is_secret and 'key' in var.key.lower %}
                        <button
                            type="button"
                            class="webops-btn-generate"
                            data-target="env_{{ var.key }}"
                        >
                            Generate
                        </button>
                        {% endif %}
                    </div>

                    {% if var.default_value %}
                    <span class="default-value">Default: {{ var.default_value }}</span>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endfor %}

            <div class="form-actions">
                <button type="submit" class="webops-btn webops-btn-primary">
                    Save Configuration & Deploy
                </button>
                <a href="{% url 'deployment_detail' deployment.id %}" class="webops-btn btn-secondary">
                    Cancel
                </a>
            </div>
        </form>
    </div>
</div>

<script>
// Toggle password visibility
document.querySelectorAll('.toggle-visibility').forEach(btn => {
    btn.addEventListener('click', function() {
        const targetId = this.dataset.target;
        const input = document.getElementById(targetId);
        input.type = input.type === 'password' ? 'text' : 'password';
    });
});

// Generate random keys
document.querySelectorAll('.btn-generate').forEach(btn => {
    btn.addEventListener('click', async function() {
        const targetId = this.dataset.target;
        const input = document.getElementById(targetId);

        // Call API to generate key
        const response = await fetch('/api/generate-key/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                key_type: input.id.includes('SECRET_KEY') ? 'django' : 'fernet'
            })
        });

        const data = await response.json();
        input.value = data.key;
        input.type = 'text'; // Show generated key
    });
});
</script>
{% endblock %}
```

---

### 3.3 API Endpoint for Key Generation

**Location**: `apps/deployments/views.py`

```python
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.core.utils import generate_django_secret_key, generate_fernet_key

@login_required
@require_POST
def api_generate_key(request):
    """Generate cryptographic keys via API."""
    import json
    data = json.loads(request.body)
    key_type = data.get('key_type', 'django')

    if key_type == 'django':
        key = generate_django_secret_key()
    elif key_type == 'fernet':
        key = generate_fernet_key()
    else:
        return JsonResponse({'error': 'Invalid key type'}, status=400)

    return JsonResponse({'key': key})
```

---

### 3.4 CSS Styling

**Location**: `control-panel/static/css/main.css`

```css
/* Environment Configuration Wizard */
.config-wizard {
    max-width: 800px;
    margin: 2rem auto;
    padding: 2rem;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.config-wizard h1 {
    margin-bottom: 0.5rem;
    color: #1a202c;
}

.config-wizard .subtitle {
    color: #718096;
    margin-bottom: 2rem;
}

.deployment-info {
    padding: 1rem;
    background: #f7fafc;
    border-radius: 4px;
    margin-bottom: 2rem;
}

.env-category {
    margin-bottom: 2rem;
}

.env-category h2 {
    font-size: 1.25rem;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e2e8f0;
}

.env-variable {
    margin-bottom: 1.5rem;
}

.env-variable label {
    display: block;
    font-weight: 600;
    margin-bottom: 0.25rem;
    color: #2d3748;
}

.env-variable.required label::after {
    content: " *";
    color: #e53e3e;
}

.env-variable .help-text {
    font-size: 0.875rem;
    color: #718096;
    margin: 0.25rem 0;
}

.env-variable .input-group {
    display: flex;
    gap: 0.5rem;
}

.env-variable input {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: 1px solid #cbd5e0;
    border-radius: 4px;
    font-family: 'Monaco', 'Courier New', monospace;
    font-size: 0.875rem;
}

.env-variable.is-secret input {
    background: #fff8e1;
}

.env-variable input:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.toggle-visibility,
.btn-generate {
    padding: 0.5rem 0.75rem;
    background: #f7fafc;
    border: 1px solid #cbd5e0;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.2s;
}

.toggle-visibility:hover,
.btn-generate:hover {
    background: #edf2f7;
}

.btn-generate {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
}

.btn-generate:hover {
    background: #2563eb;
}

.default-value {
    display: block;
    font-size: 0.75rem;
    color: #a0aec0;
    margin-top: 0.25rem;
}

.form-actions {
    display: flex;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 2px solid #e2e8f0;
}

.form-actions .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: #3b82f6;
    color: white;
    border: none;
}

.btn-primary:hover {
    background: #2563eb;
}

.btn-secondary {
    background: white;
    color: #4a5568;
    border: 1px solid #cbd5e0;
    text-decoration: none;
    display: inline-block;
    text-align: center;
}

.btn-secondary:hover {
    background: #f7fafc;
}
```

---

## Phase 4: System Monitoring & Self-Healing

### 4.1 Deployment Health Checks

**New Celery Periodic Task**:
```python
# apps/deployments/tasks.py

@shared_task
def check_deployment_health():
    """
    Periodic task to check health of all deployments.
    Runs every 5 minutes.
    """
    from .models import Deployment, DeploymentLog
    from .service_manager import ServiceManager

    manager = ServiceManager()
    stuck_deployments = ApplicationDeployment.objects.filter(
        status=ApplicationDeployment.Status.BUILDING,
        updated_at__lt=timezone.now() - timedelta(minutes=10)
    )

    for deployment in stuck_deployments:
        # Deployment stuck for 10+ minutes
        DeploymentLog.objects.create(
            deployment=deployment,
            level=DeploymentLog.Level.WARNING,
            message="Deployment stuck in Building state for >10 minutes. Investigating..."
        )

        # Check Celery worker
        # Check service status
        # Attempt recovery or mark as failed
```

**Register in Celery Beat**:
```python
# config/settings.py

CELERY_BEAT_SCHEDULE = {
    'check-deployment-health': {
        'task': 'apps.deployments.tasks.check_deployment_health',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

---

### 4.2 System Resource Monitoring

**New Management Command**:
```python
# apps/core/management/commands/system_health.py

from django.core.management.base import BaseCommand
import psutil
import subprocess

class Command(BaseCommand):
    help = 'Check system health and resource usage'

    def handle(self, *args, **options):
        self.stdout.write("System Health Check")
        self.stdout.write("=" * 50)

        # Check Celery
        self.check_celery()

        # Check Redis
        self.check_redis()

        # Check PostgreSQL
        self.check_postgresql()

        # Check Nginx
        self.check_nginx()

        # Check disk space
        self.check_disk_space()

        # Check memory
        self.check_memory()

    def check_celery(self):
        """Check if Celery worker is running."""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'webops-celery'],
                capture_output=True,
                text=True
            )

            if result.stdout.strip() == 'active':
                self.stdout.write(self.style.SUCCESS('✓ Celery worker: RUNNING'))
            else:
                self.stdout.write(self.style.ERROR('✗ Celery worker: NOT RUNNING'))
        except:
            self.stdout.write(self.style.ERROR('✗ Celery worker: ERROR'))

    # ... similar checks for other services
```

---

## Phase 5: Documentation & Testing

### 5.1 Updated Documentation

**Files to update**:
1. `README.md` - Add troubleshooting section
2. `docs/installation.md` - Document new setup.sh features
3. `docs/deployment-guide.md` - Document .env wizard
4. `docs/troubleshooting.md` - Add common issues and solutions

---

### 5.2 Test Suite

**New tests needed**:
```python
# apps/deployments/tests/test_env_parser.py
class EnvParserTestCase(TestCase):
    def test_parse_env_example(self):
        """Test parsing .env.example file."""
        pass

    def test_categorize_variables(self):
        """Test variable categorization."""
        pass

    def test_generate_env_dict(self):
        """Test environment dict generation."""
        pass

# apps/deployments/tests/test_deployment_flow.py
class DeploymentFlowTestCase(TestCase):
    def test_deployment_with_env_config(self):
        """Test deployment requiring .env configuration."""
        pass

    def test_auto_key_generation(self):
        """Test automatic key generation."""
        pass
```

---

## Implementation Timeline

### Week 1: Setup.sh Enhancements
- ✅ Day 1-2: Pre-installation validation
- ✅ Day 3-4: Robust package installation
- ✅ Day 5: Service health verification
- ✅ Day 6-7: Testing and bug fixes

### Week 2: Environment Management
- ✅ Day 8-9: Deployment model updates
- ✅ Day 10-11: Enhanced deployment workflow
- ✅ Day 12-13: Key generation utilities
- ✅ Day 14: Integration testing

### Week 3: UI Development
- ✅ Day 15-16: Configuration view and template
- ✅ Day 17-18: CSS styling and JavaScript
- ✅ Day 19-20: API endpoints
- ✅ Day 21: End-to-end testing

### Week 4: Monitoring & Polish
- ✅ Day 22-23: Health check tasks
- ✅ Day 24-25: System monitoring
- ✅ Day 26-27: Documentation
- ✅ Day 28: Final testing and deployment

---

## Success Metrics

1. **Setup Success Rate**: 95%+ successful installations on fresh VPS
2. **Service Reliability**: All services (PostgreSQL, Redis, Celery, Nginx) running after setup
3. **Deployment Success**: 90%+ deployments complete without manual intervention
4. **Configuration UX**: Users can configure .env in <3 minutes
5. **Zero Stuck Deployments**: No deployments stuck in "Building" for >10 minutes

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Package installation fails | 3 retry attempts with exponential backoff |
| Service doesn't start | Diagnostic logs + self-healing restart |
| Celery worker crashes | Health checks + automatic restart |
| User misconfigures .env | Validation + suggested values |
| Database connection fails | Automatic credential generation + testing |

---

## Appendix A: File Changes Summary

### Modified Files
1. `setup.sh` - ~500 lines added (validation, health checks, diagnostics)
2. `apps/deployments/models.py` - 3 new fields
3. `apps/deployments/services.py` - New methods for env config
4. `apps/deployments/views.py` - New configuration view
5. `apps/deployments/tasks.py` - New health check task
6. `apps/core/utils.py` - Key generation utilities
7. `control-panel/static/css/main.css` - ~200 lines for wizard UI

### New Files
1. `templates/deployments/configure_env.html` - Configuration wizard UI
2. `apps/core/management/commands/test_celery_connection.py` - Celery test
3. `apps/core/management/commands/system_health.py` - Health check command
4. `apps/deployments/tests/test_env_parser.py` - Tests
5. `docs/implementation-plan.md` - This document

---

## Appendix B: Configuration Examples

### Example .env.example (User's Django Project)
```bash
# Django Configuration
SECRET_KEY=change-me-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost/dbname

# Optional: Email Configuration (Leave empty to disable)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True

# Optional: Redis Cache (Leave empty to use defaults)
REDIS_URL=redis://localhost:6379/0

# API Keys (Optional)
STRIPE_PUBLIC_KEY=
STRIPE_SECRET_KEY=
```

### Generated .env (After Wizard)
```bash
# Django Configuration
SECRET_KEY=k9#m$p*j@2x&w8v!n^q3r5t7y=u+i-o0p[a]s{d}f|g<h>
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,myapp.example.com

# Database Configuration
DATABASE_URL=postgresql://myapp:XkP9mN2vR8sT4wQ7@localhost:5432/myapp_db

# Optional: Email Configuration (Leave empty to disable)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=user@example.com
EMAIL_HOST_PASSWORD=app-specific-password
EMAIL_USE_TLS=True

# Optional: Redis Cache (Leave empty to use defaults)
REDIS_URL=redis://localhost:6379/0

# API Keys (Optional)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
```

---

## Next Steps

After approval of this plan:

1. **Review** - Get feedback on approach and priorities
2. **Estimate** - Refine timeline based on team capacity
3. **Implement** - Start with Phase 1 (setup.sh)
4. **Test** - Comprehensive testing on fresh VPS instances
5. **Deploy** - Gradual rollout with monitoring
6. **Document** - Update all documentation

**Questions for Discussion**:
1. Should we prioritize setup.sh fixes or env wizard first?
2. Do we want automatic recovery for stuck deployments or manual intervention?
3. Should .env configuration be mandatory or optional?
4. What level of validation do we want for user-provided env values?
