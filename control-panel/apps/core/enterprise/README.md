# WebOps Enterprise Features

Enterprise-grade multi-tenancy, RBAC, audit logging, rate limiting, and SSO for WebOps Platform.

## Features

### 🏢 Organizations & Teams
- **Multi-tenancy**: Complete data isolation per organization
- **Teams**: Group collaboration within organizations
- **Hierarchical structure**: Organization → Teams → Members
- **Configurable limits**: Members, teams, deployments per tier

### 🔐 Granular RBAC
- **Built-in roles**: Owner, Admin, Member, Viewer
- **Custom roles**: Create organization-specific roles
- **Granular permissions**: Resource-level access control (e.g., `deployment.create`, `database.backup`)
- **Resource permissions**: Grant/deny access to specific resources
- **Permission inheritance**: Org → Team → User

### 📝 Audit Logging
- **Immutable audit trail**: All actions logged, cannot be modified/deleted
- **Complete context**: User, IP, user agent, request details
- **Change tracking**: Before/after values for modifications
- **Compliance ready**: SOC 2, GDPR, HIPAA compliant
- **Query interface**: Efficient queries by user, organization, resource, time range

### ⏱️ API Rate Limiting
- **Tier-based limits**: Free, Starter, Pro, Enterprise
- **Multiple scopes**: Per-user, per-organization, per-IP
- **Granular control**: Different limits for different operations
- **Redis-backed**: Efficient, scalable
- **Decorator support**: Easy integration with views

### 🔑 SSO/SAML
- **SAML 2.0 support**: Enterprise SSO
- **Multiple IdPs**: Okta, Azure AD, Google Workspace, etc.
- **JIT provisioning**: Automatic user creation on first login
- **Attribute mapping**: Flexible user attribute mapping
- **Session tracking**: Complete SSO session audit trail

---

## Installation

### 1. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    ...
    'apps.core.enterprise',
    ...
]
```

### 2. Run Migrations

```bash
python manage.py makemigrations enterprise
python manage.py migrate enterprise
```

### 3. Seed Permissions & Roles

```bash
python manage.py seed_enterprise
```

This creates:
- **40+ permissions** (deployment.*, database.*, team.*, org.*, etc.)
- **4 built-in roles** (owner, admin, member, viewer)
- **Role-permission mappings**

### 4. Configure Rate Limiting (Optional)

```python
# settings.py
MIDDLEWARE = [
    ...
    'apps.core.enterprise.ratelimit.RateLimitMiddleware',  # Add for global rate limiting
    ...
]
```

---

## Usage

### Organizations & Teams

```python
from apps.core.enterprise.models import Organization, Team, OrganizationMember, Role

# Create organization
org = Organization.objects.create(
    name='Acme Corp',
    slug='acme-corp',
    owner=user,
    max_members=50,
    max_teams=10
)

# Add member to organization
member_role = Role.objects.get(slug='member', is_system=True)
OrganizationMember.objects.create(
    organization=org,
    user=new_user,
    role=member_role,
    invited_by=owner_user
)

# Create team
team = Team.objects.create(
    organization=org,
    name='Engineering',
    slug='engineering',
    created_by=owner_user
)

# Add member to team
TeamMember.objects.create(
    team=team,
    user=new_user,
    role=member_role
)
```

### Permission Checking

```python
from apps.core.enterprise.permissions import PermissionService

# Check if user has permission
service = PermissionService(user)

# Organization-level permission
if service.has_permission('deployment.create', organization=org):
    # User can create deployments
    pass

# Resource-level permission
if service.has_resource_permission('deployment.delete', deployment):
    # User can delete this specific deployment
    pass

# Get accessible organizations
orgs = service.get_accessible_organizations()
```

### Permission Decorator

```python
from apps.core.enterprise.permissions import require_permission

# Require general permission
@require_permission('deployment.view')
def list_deployments(request):
    ...

# Require resource-level permission
@require_permission('deployment.delete', resource_param='deployment')
def delete_deployment(request, deployment):
    ...
```

### Audit Logging

```python
from apps.core.enterprise.audit import log_audit, AuditLog, AuditLogQuery

# Log an action
log_audit(
    user=request.user,
    action=AuditLog.CREATE,
    resource_type='deployment',
    resource_id=deployment.id,
    resource_name=deployment.name,
    organization_id=org.id,
    request=request,
    success=True
)

# Query audit logs
logs = AuditLogQuery.for_user(user, days=30)
logs = AuditLogQuery.for_organization(org.id, days=30)
logs = AuditLogQuery.for_resource('deployment', deployment_id, days=7)
logs = AuditLogQuery.security_events(days=7)
logs = AuditLogQuery.failed_attempts(days=1)
```

### Rate Limiting

```python
from apps.core.enterprise.ratelimit import rate_limit

# Decorator-based rate limiting
@rate_limit(limit_type='api_calls', per='hour')
def api_view(request):
    ...

@rate_limit(limit_type='deployments', per='day')
def create_deployment(request):
    ...

# Manual rate limiting
from apps.core.enterprise.ratelimit import RateLimiter

limiter = RateLimiter()
try:
    allowed, remaining, reset_time = limiter.check_limit(
        key=f"user:{user.id}:api_calls",
        max_calls=100,
        window=3600
    )
except RateLimitExceeded:
    return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
```

### SSO/SAML

```python
from apps.core.enterprise.sso import SSOProvider, SSOService

# Create SSO provider
provider = SSOProvider.objects.create(
    organization=org,
    provider_name='Okta',
    provider_type=SSOProvider.SAML,
    saml_entity_id='https://idp.example.com',
    saml_sso_url='https://idp.example.com/sso',
    saml_slo_url='https://idp.example.com/slo',
    saml_x509_cert='CERTIFICATE_DATA',
    enable_jit_provisioning=True,
    default_role_slug='member',
    created_by=owner
)

# Get SSO login URL
service = SSOService(org)
if service.is_enabled():
    login_url = service.get_login_url(relay_state='/dashboard')

# Process SAML response (in callback view)
user = service.process_saml_response(saml_response, request)
if user:
    django.contrib.auth.login(request, user)
```

---

## Models

### Organization
- Top-level tenant with complete isolation
- Owner, limits (members, teams, deployments)
- Active/inactive status

### Team
- Group within organization
- Name, description, member limits
- Created by user

### Role
- Defines set of permissions
- Built-in: owner, admin, member, viewer
- Custom roles per organization

### OrganizationMember
- User membership in organization
- Role assignment
- Active/inactive status

### TeamMember
- User membership in team
- Role assignment
- Active/inactive status

### Permission
- Granular permission (resource.action)
- Examples: deployment.create, database.backup
- System or custom

### RolePermission
- Maps permissions to roles

### ResourcePermission
- Grant/deny specific user access to specific resource
- Optional expiration

### AuditLog
- Immutable audit trail
- User, action, resource, changes, context
- Query interface

### SSOProvider
- SSO/SAML configuration per organization
- SAML 2.0, OAuth 2.0, OIDC support
- JIT provisioning settings

### SSOSession
- SSO session tracking
- Session index, expiration, logout tracking

---

## API Endpoints (Future)

```
# Organizations
GET    /api/v1/organizations/
POST   /api/v1/organizations/
GET    /api/v1/organizations/{id}/
PATCH  /api/v1/organizations/{id}/
DELETE /api/v1/organizations/{id}/

# Organization Members
GET    /api/v1/organizations/{id}/members/
POST   /api/v1/organizations/{id}/members/
DELETE /api/v1/organizations/{id}/members/{member_id}/

# Teams
GET    /api/v1/organizations/{id}/teams/
POST   /api/v1/organizations/{id}/teams/
GET    /api/v1/teams/{id}/
PATCH  /api/v1/teams/{id}/
DELETE /api/v1/teams/{id}/

# Team Members
GET    /api/v1/teams/{id}/members/
POST   /api/v1/teams/{id}/members/
DELETE /api/v1/teams/{id}/members/{member_id}/

# Roles & Permissions
GET    /api/v1/roles/
GET    /api/v1/permissions/

# Audit Logs
GET    /api/v1/audit-logs/
GET    /api/v1/audit-logs/{id}/

# SSO
GET    /api/v1/organizations/{id}/sso/
POST   /api/v1/organizations/{id}/sso/
PATCH  /api/v1/organizations/{id}/sso/{provider_id}/
```

---

## Testing

```bash
# Run all enterprise tests
python manage.py test apps.core.enterprise

# Run specific test cases
python manage.py test apps.core.enterprise.tests.OrganizationTestCase
python manage.py test apps.core.enterprise.tests.PermissionTestCase
python manage.py test apps.core.enterprise.tests.AuditLogTestCase
python manage.py test apps.core.enterprise.tests.RateLimitTestCase
python manage.py test apps.core.enterprise.tests.SSOTestCase

# Run with coverage
coverage run --source='apps.core.enterprise' manage.py test apps.core.enterprise
coverage report
coverage html
```

---

## Permissions Reference

### Deployment Permissions
- `deployment.create` - Create deployments
- `deployment.view` - View deployments
- `deployment.update` - Update deployments
- `deployment.delete` - Delete deployments
- `deployment.deploy` - Trigger deployment
- `deployment.rollback` - Rollback deployment
- `deployment.logs` - View deployment logs

### Database Permissions
- `database.create` - Create databases
- `database.view` - View databases
- `database.update` - Update databases
- `database.delete` - Delete databases
- `database.backup` - Backup databases
- `database.restore` - Restore databases
- `database.credentials` - View credentials

### Team Permissions
- `team.create` - Create teams
- `team.view` - View teams
- `team.update` - Update teams
- `team.delete` - Delete teams
- `team.invite` - Invite members
- `team.remove` - Remove members

### Organization Permissions
- `organization.view` - View organization
- `organization.update` - Update organization
- `organization.delete` - Delete organization
- `organization.billing` - Manage billing
- `organization.settings` - Manage settings

### Monitoring Permissions
- `monitoring.view` - View monitoring data
- `monitoring.alerts` - Manage alerts

### Audit Permissions
- `audit.view` - View audit logs
- `audit.export` - Export audit logs

---

## Rate Limit Tiers

### Free Tier
- **API Calls**: 100/hour, 20/minute
- **Deployments**: 10/day
- **Concurrent**: 2

### Starter Tier
- **API Calls**: 1,000/hour, 100/minute
- **Deployments**: 50/day
- **Concurrent**: 5

### Pro Tier
- **API Calls**: 10,000/hour, 500/minute
- **Deployments**: 200/day
- **Concurrent**: 20

### Enterprise Tier
- **API Calls**: 100,000/hour, 5,000/minute
- **Deployments**: 1,000/day
- **Concurrent**: 100

---

## Security Considerations

### Audit Logs
- ✅ Immutable (cannot be modified or deleted)
- ✅ Preserved even if user/org is deleted
- ✅ Includes IP address and user agent
- ✅ Includes full request context
- ✅ Includes before/after values for changes

### Permissions
- ✅ Cached for performance (5 minute TTL)
- ✅ Explicit deny overrides implicit allow
- ✅ Superusers bypass all checks
- ✅ Resource-level permissions override role permissions

### Rate Limiting
- ✅ Redis-backed (efficient, scalable)
- ✅ Per-user, per-org, per-IP
- ✅ Configurable per tier
- ✅ Headers included (X-RateLimit-*)

### SSO/SAML
- ✅ SAML request signing
- ✅ Certificate validation
- ✅ Force authentication option
- ✅ Session expiration
- ✅ Logout tracking

---

## Migration Guide

### From Single-User to Multi-Tenant

```python
# 1. Create organization for existing deployments
org = Organization.objects.create(
    name='Default Organization',
    slug='default',
    owner=admin_user
)

# 2. Migrate existing deployments
from apps.deployments.models import Deployment

for deployment in Deployment.objects.all():
    deployment.organization = org
    deployment.save()

# 3. Add all existing users to organization
from django.contrib.auth import get_user_model

User = get_user_model()
member_role = Role.objects.get(slug='member', is_system=True)

for user in User.objects.all():
    OrganizationMember.objects.get_or_create(
        organization=org,
        user=user,
        defaults={'role': member_role}
    )
```

---

## Performance

### Permission Caching
- Permissions cached for 5 minutes
- Cache invalidated on role/permission changes
- Cache key: `perm:{user_id}:{permission}:{org_id}`

### Audit Log Indexing
- Indexed on: `user`, `organization_id`, `resource_type`, `timestamp`
- Composite indexes for common queries
- Retention policy recommended (90-365 days)

### Rate Limiting
- Redis-backed (O(1) operations)
- Minimal overhead (<1ms)
- Scales horizontally with Redis cluster

---

## Future Enhancements

- [ ] **GraphQL API** for enterprise features
- [ ] **Webhook notifications** for audit events
- [ ] **SCIM provisioning** for user sync
- [ ] **OAuth 2.0 / OIDC** full support
- [ ] **Compliance reports** (SOC 2, GDPR, HIPAA)
- [ ] **Advanced RBAC** (conditions, temporal access)
- [ ] **Multi-factor auth** for SSO sessions
- [ ] **Session management** dashboard
- [ ] **Anomaly detection** in audit logs
- [ ] **Cost tracking** per organization

---

## Support

For enterprise support:
- **Email**: enterprise@webops.io
- **Documentation**: https://docs.webops.io/enterprise
- **Issues**: https://github.com/DagiiM/webops/issues

---

**Built for enterprise. Designed for scale. Secured by default.**
