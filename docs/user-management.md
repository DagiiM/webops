# WebOps User Management Guide 👥

**Multi-user setup, permissions, and team collaboration for WebOps v2.0**

**Project Owner:** [Douglas Mutethia](https://github.com/DagiiM) | **Company:** Eleso Solutions  
**Repository:** [https://github.com/DagiiM/webops](https://github.com/DagiiM/webops)

WebOps supports sophisticated user management with role-based access control, team collaboration features, and enterprise security.

---

## 👤 **User Management Overview**

### **User Types & Roles**
- **Super Admin**: Full platform access and configuration
- **Admin**: User management and deployment oversight
- **Developer**: Create and manage own deployments
- **Viewer**: Read-only access to dashboards and logs
- **Custom Roles**: Configurable permissions per organization needs

### **Key Features**
- ✅ **Role-Based Access Control (RBAC)** - Granular permission system
- ✅ **Two-Factor Authentication** - Enhanced security for all users
- ✅ **Team Management** - Organize users into teams with shared resources
- ✅ **Audit Logging** - Track all user actions and changes
- ✅ **API Token Management** - Secure programmatic access
- ✅ **SSO Integration** - Single sign-on with external providers

---

## 🔧 **Initial User Setup**

### **Admin User Creation**

**During Installation:**
```bash
# Automatic admin creation during setup
./quickstart.sh
# Creates admin user: admin / admin123

# Or manual admin creation
cd /opt/webops/control-panel
source venv/bin/activate
python manage.py createsuperuser
```

**Change Default Password:**
```bash
# Change admin password immediately
python manage.py changepassword admin

# Or via web interface
# Login: https://webops.yourdomain.com/admin/
# Navigate: Authentication and Authorization > Users > admin
```

### **Enable Multi-User Features**

```bash
# Configure multi-user support in .env
ENABLE_MULTI_USER=True
ENABLE_RBAC=True
ENABLE_TEAM_MANAGEMENT=True
REQUIRE_EMAIL_VERIFICATION=True

# Restart services
sudo systemctl restart webops-web
```

---

## 👥 **Creating and Managing Users**

### **Add Users via Admin Interface**

**Web Interface Method:**
1. **Login** to admin panel: `https://webops.yourdomain.com/admin/`
2. **Navigate** to Authentication and Authorization > Users
3. **Click** "Add User" button
4. **Fill** required information:
   - Username (unique identifier)
   - Email address
   - First name and Last name
   - Password (temporary)
   - Staff status (for admin access)
   - Active status
5. **Set** user permissions and groups
6. **Save** user profile

### **Add Users via Command Line**

```bash
# Create regular user
python manage.py create_user \
    --username johndoe \
    --email john@company.com \
    --first-name John \
    --last-name Doe \
    --role developer

# Create admin user
python manage.py create_user \
    --username jane.admin \
    --email jane@company.com \
    --role admin \
    --is-staff \
    --send-email

# Bulk user creation from CSV
python manage.py bulk_create_users --file users.csv --send-invites
```

**Sample CSV Format:**
```csv
username,email,first_name,last_name,role
developer1,dev1@company.com,Alice,Johnson,developer
developer2,dev2@company.com,Bob,Smith,developer
ops.manager,ops@company.com,Carol,Davis,admin
```

### **User Invitation System**

```bash
# Send invitation to new user
python manage.py invite_user \
    --email newuser@company.com \
    --role developer \
    --team backend-team \
    --message "Welcome to our WebOps platform"

# Resend invitation
python manage.py resend_invitation --email newuser@company.com

# List pending invitations
python manage.py list_invitations --status pending
```

---

## 🔐 **Role-Based Access Control (RBAC)**

### **Built-in Roles & Permissions**

**Super Admin Role:**
```python
PERMISSIONS = [
    'view_all_deployments',
    'create_deployment', 
    'modify_deployment',
    'delete_deployment',
    'manage_users',
    'manage_teams',
    'view_system_metrics',
    'modify_system_settings',
    'view_audit_logs',
    'manage_api_tokens',
    'access_admin_panel'
]
```

**Admin Role:**
```python
PERMISSIONS = [
    'view_all_deployments',
    'create_deployment',
    'modify_deployment', 
    'delete_own_deployment',
    'manage_team_users',
    'view_system_metrics',
    'view_audit_logs',
    'manage_own_tokens'
]
```

**Developer Role:**
```python
PERMISSIONS = [
    'view_own_deployments',
    'create_deployment',
    'modify_own_deployment',
    'delete_own_deployment',
    'view_deployment_logs',
    'manage_own_databases',
    'manage_own_tokens'
]
```

**Viewer Role:**
```python
PERMISSIONS = [
    'view_own_deployments',
    'view_deployment_logs',
    'view_system_dashboard'
]
```

### **Custom Role Creation**

```bash
# Create custom role via command line
python manage.py create_role \
    --name "QA Tester" \
    --permissions view_deployments,create_test_deployment,view_logs \
    --description "Quality assurance testing role"

# Assign custom role to user
python manage.py assign_role \
    --username testuser \
    --role "QA Tester"
```

**Custom Role Configuration (Admin Panel):**
```python
# Custom role example
{
    "name": "DevOps Engineer",
    "permissions": [
        "view_all_deployments",
        "create_deployment",
        "modify_deployment", 
        "view_system_metrics",
        "manage_databases",
        "view_audit_logs"
    ],
    "description": "DevOps team with deployment and monitoring access"
}
```

### **Permission Management**

```bash
# View user permissions
python manage.py user_permissions --username johndoe

# Grant specific permissions
python manage.py grant_permission \
    --username johndoe \
    --permission manage_databases

# Revoke permissions
python manage.py revoke_permission \
    --username johndoe \
    --permission delete_deployment

# Bulk permission updates
python manage.py update_permissions --file permission_updates.json
```

---

## 🏢 **Team Management**

### **Creating Teams**

```bash
# Create team via CLI
python manage.py create_team \
    --name "Backend Team" \
    --description "Backend developers and services" \
    --lead johndoe \
    --members alice,bob,carol

# Create team with specific permissions
python manage.py create_team \
    --name "Frontend Team" \
    --permissions create_deployment,manage_static_sites \
    --budget-limit 100  # Max deployments
```

**Team Creation via Admin Interface:**
1. Navigate to **Teams** section in admin panel
2. Click **Add Team**
3. Configure team details:
   - Team name and description
   - Team lead (optional)
   - Default permissions for team members
   - Resource limits and quotas
   - Shared resources (databases, domains)

### **Team Permissions & Resources**

**Team-Level Configuration:**
```json
{
  "team": "Backend Team",
  "permissions": {
    "deployments": {
      "max_deployments": 20,
      "allowed_types": ["django", "flask", "fastapi"],
      "resource_limits": {
        "cpu": "2 cores",
        "memory": "4GB",
        "storage": "20GB"
      }
    },
    "databases": {
      "max_databases": 10,
      "allowed_engines": ["postgresql", "mysql"]
    }
  },
  "shared_resources": {
    "domains": ["api.company.com", "*.backend.company.com"],
    "ssl_certificates": ["*.backend.company.com"],
    "environment_templates": ["production", "staging"]
  }
}
```

### **Team Collaboration Features**

**Shared Deployments:**
```bash
# Share deployment with team
python manage.py share_deployment \
    --deployment myapp \
    --team "Backend Team" \
    --permissions view,modify

# Transfer deployment ownership
python manage.py transfer_deployment \
    --deployment myapp \
    --from johndoe \
    --to backend-team
```

**Team Notifications:**
```bash
# Configure team notifications
TEAM_NOTIFICATIONS=True
NOTIFY_TEAM_DEPLOYMENTS=True
NOTIFY_TEAM_FAILURES=True
SLACK_TEAM_CHANNELS={
    "Backend Team": "#backend-deployments",
    "Frontend Team": "#frontend-deployments"
}
```

---

## 🔑 **API Token Management**

### **User API Tokens**

**Create Personal Access Tokens:**
```bash
# Create token via CLI
python manage.py create_token \
    --user johndoe \
    --name "CLI Access" \
    --permissions deployments,databases \
    --expires-in 90d

# Create token via web interface
# Login: https://webops.yourdomain.com/dashboard/
# Navigate: Settings > API Tokens > Generate New Token
```

**Token Scope Configuration:**
```json
{
  "token": "wop_abc123...",
  "name": "Production Deploy Token",
  "user": "johndoe",
  "permissions": [
    "create_deployment",
    "view_deployments", 
    "manage_databases"
  ],
  "rate_limits": {
    "requests_per_hour": 100,
    "deployments_per_hour": 5
  },
  "ip_restrictions": [
    "192.168.1.0/24",
    "10.0.0.0/8"
  ],
  "expires_at": "2024-06-15T00:00:00Z"
}
```

### **Service Account Tokens**

```bash
# Create service account for automation
python manage.py create_service_account \
    --name "CI/CD Pipeline" \
    --permissions create_deployment,view_logs \
    --rate-limit 200/hour \
    --no-expiry

# Create team service account
python manage.py create_team_token \
    --team "Backend Team" \
    --name "Team Automation" \
    --permissions team_deployments
```

---

## 🔒 **Security Features**

### **Two-Factor Authentication (2FA)**

**Enable 2FA for Users:**
```bash
# Enforce 2FA for admin users
ENFORCE_2FA_FOR_ADMINS=True

# Require 2FA for all users
REQUIRE_2FA_ALL_USERS=True

# Setup 2FA for specific user
python manage.py setup_2fa --username johndoe --send-qr-email
```

**2FA Configuration Options:**
- **TOTP Apps**: Google Authenticator, Authy, Microsoft Authenticator
- **Backup Codes**: 10 single-use recovery codes per user
- **SMS Backup**: Optional SMS-based backup authentication
- **Hardware Tokens**: Support for FIDO2/WebAuthn hardware keys

### **Password Policies**

```bash
# Configure password requirements in .env
PASSWORD_MIN_LENGTH=12
PASSWORD_REQUIRE_UPPERCASE=True
PASSWORD_REQUIRE_LOWERCASE=True
PASSWORD_REQUIRE_NUMBERS=True
PASSWORD_REQUIRE_SYMBOLS=True
PASSWORD_HISTORY_COUNT=5  # Prevent reuse of last 5 passwords
PASSWORD_EXPIRY_DAYS=90   # Force password change every 90 days
```

### **Session Management**

```bash
# Session security settings
SESSION_COOKIE_AGE=3600        # 1 hour session timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
MAX_CONCURRENT_SESSIONS=3      # Limit concurrent sessions per user
DETECT_UNUSUAL_LOGIN_PATTERNS=True
```

---

## 📊 **User Activity & Audit Logging**

### **Activity Monitoring**

```bash
# View user activity
python manage.py user_activity --username johndoe --period 7d

# Generate activity report
python manage.py activity_report --team "Backend Team" --format pdf

# Monitor active sessions
python manage.py list_sessions --active --detailed
```

**Activity Tracking Includes:**
- Login/logout events with IP addresses
- Deployment creation, modification, deletion
- Database operations
- Team membership changes
- Permission modifications
- API token usage
- Failed authentication attempts

### **Audit Log Analysis**

```bash
# Search audit logs
python manage.py search_audit_logs \
    --user johndoe \
    --action deployment_created \
    --date-range 2024-12-01,2024-12-15

# Export audit logs
python manage.py export_audit_logs \
    --format csv \
    --output audit_report.csv \
    --period 30d

# Security audit report
python manage.py security_audit --failed-logins --suspicious-activity
```

**Sample Audit Log Entry:**
```json
{
  "timestamp": "2024-12-14T10:30:00Z",
  "user": "johndoe",
  "action": "deployment_created", 
  "resource": "django-blog",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "details": {
    "deployment_name": "django-blog",
    "repo_url": "https://github.com/user/blog",
    "team": "Backend Team"
  },
  "success": true
}
```

---

## 🔗 **Single Sign-On (SSO) Integration**

### **LDAP/Active Directory**

```bash
# Configure LDAP authentication in .env
ENABLE_LDAP_AUTH=True
LDAP_SERVER_URI=ldap://your-ad-server.company.com
LDAP_BIND_DN=CN=webops,CN=Users,DC=company,DC=com
LDAP_BIND_PASSWORD=your_ldap_password
LDAP_USER_SEARCH_BASE=CN=Users,DC=company,DC=com
LDAP_GROUP_SEARCH_BASE=CN=Groups,DC=company,DC=com

# Map LDAP groups to WebOps roles
LDAP_GROUP_MAPPINGS={
    "CN=Developers,CN=Groups,DC=company,DC=com": "developer",
    "CN=DevOps,CN=Groups,DC=company,DC=com": "admin"
}
```

### **OAuth Providers**

```bash
# Google OAuth configuration
ENABLE_GOOGLE_SSO=True
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_ALLOWED_DOMAINS=company.com,subsidiary.com

# GitHub OAuth configuration  
ENABLE_GITHUB_SSO=True
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_ALLOWED_ORGS=your-github-org

# SAML SSO configuration
ENABLE_SAML_SSO=True
SAML_IDP_URL=https://your-saml-provider.com/sso
SAML_CERTIFICATE_PATH=/path/to/saml/certificate.pem
```

---

## 🛠️ **User Management Commands**

### **Bulk Operations**

```bash
# Bulk user import
python manage.py import_users \
    --file users.csv \
    --default-role developer \
    --send-invitations

# Bulk password reset
python manage.py bulk_password_reset \
    --team "Backend Team" \
    --send-email

# Bulk role assignment
python manage.py bulk_assign_role \
    --users alice,bob,carol \
    --role admin

# User cleanup (inactive users)
python manage.py cleanup_users \
    --inactive-days 90 \
    --dry-run
```

### **User Statistics**

```bash
# User statistics
python manage.py user_stats --detailed

# Team statistics
python manage.py team_stats --include-activity

# Permission usage analysis
python manage.py permission_analysis --unused --overused
```

**Sample User Statistics:**
```
👥 WebOps User Statistics
==========================

📊 TOTAL USERS: 25
   ✅ Active: 22 (88%)
   ⏸️  Inactive: 3 (12%)
   🔐 2FA Enabled: 18 (72%)

👑 ROLES DISTRIBUTION:
   Super Admin: 2 (8%)
   Admin: 4 (16%) 
   Developer: 16 (64%)
   Viewer: 3 (12%)

🏢 TEAMS:
   Backend Team: 8 users (5 deployments)
   Frontend Team: 6 users (12 deployments)
   DevOps Team: 4 users (3 deployments)
   Unassigned: 7 users

📈 ACTIVITY (Last 30 days):
   Total Logins: 342
   Deployments Created: 67
   API Requests: 1,245
   Average Session: 45 minutes
```

---

## 📱 **Mobile & Remote Access**

### **Progressive Web App (PWA)**

**Mobile User Management:**
- Install WebOps as native app on mobile devices
- Offline capability for viewing deployment status
- Push notifications for deployment events
- Touch-optimized interface for mobile management

### **Remote Access Security**

```bash
# Configure secure remote access
ENABLE_IP_RESTRICTIONS=True
ALLOWED_IP_RANGES=192.168.1.0/24,10.0.0.0/8
VPN_REQUIRED=True

# Device management
ENABLE_DEVICE_TRACKING=True
MAX_DEVICES_PER_USER=5
REQUIRE_DEVICE_APPROVAL=True
```

---

## 📞 **User Support & Training**

### **User Onboarding**

**Automated Onboarding Process:**
1. **Account Creation** with email verification
2. **Welcome Email** with login instructions
3. **2FA Setup** guided tutorial
4. **Platform Tour** interactive guide
5. **First Deployment** step-by-step walkthrough
6. **Team Assignment** and permissions setup

### **User Documentation**

**Built-in Help System:**
- Contextual help tooltips
- Interactive tutorial mode
- Video training library
- Keyboard shortcut reference
- API documentation access

**Training Resources:**
```bash
# Generate user training materials
python manage.py generate_user_guide --role developer --format pdf

# Create team-specific documentation
python manage.py create_team_docs --team "Backend Team" --include-examples
```

---

## 🔧 **Advanced User Management**

### **Custom User Fields**

```python
# Extend user model with custom fields
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cost_center = models.CharField(max_length=20)
    timezone = models.CharField(max_length=50, default='UTC')
    notification_preferences = models.JSONField(default=dict)
```

### **Integration APIs**

```bash
# HR system integration
python manage.py sync_hr_system --add-users --update-roles --disable-inactive

# Directory service sync
python manage.py sync_ldap --dry-run
python manage.py sync_ldap --execute --send-notifications
```

---

**WebOps User Management provides enterprise-grade multi-user capabilities with security, compliance, and team collaboration features.** 👥