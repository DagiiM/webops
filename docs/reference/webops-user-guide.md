# WebOps User Guide

**Complete guide to using WebOps for application deployment and management**

**Project Owner:** [Douglas Mutethia](https://github.com/DagiiM) | **Company:** Eleso Solutions  
**Repository:** [https://github.com/DagiiM/webops](https://github.com/DagiiM/webops)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [Deployment Management](#deployment-management)
5. [Database Management](#database-management)
6. [User Management](#user-management)
7. [Team Management](#team-management)
8. [Role-Based Access Control](#role-based-access-control)
9. [Security Features](#security-features)
10. [Service Monitoring](#service-monitoring)
11. [Advanced Features](#advanced-features)
12. [Command Line Interface](#command-line-interface)
13. [API Token Management](#api-token-management)
14. [Single Sign-On Integration](#single-sign-on-integration)
15. [Troubleshooting](#troubleshooting)
16. [Best Practices](#best-practices)
17. [Support and Resources](#support-and-resources)

---

## 🎯 Overview

WebOps is a self-hosted deployment platform that provides:
- **Application Deployment**: Deploy any web application from Git repositories
- **Database Management**: PostgreSQL database creation and management
- **Service Monitoring**: Real-time health monitoring and logging
- **Security**: Enterprise-grade security with role-based access control
- **Team Collaboration**: Multi-user support with team management
- **LLM Deployment**: Large Language Model deployment with vLLM
- **API Management**: RESTful API with token-based authentication

### Key Features

- ✅ **Multi-User Support** - Role-based access control and team management
- ✅ **Enterprise Security** - Two-factor authentication, SSO, and audit logging
- ✅ **Automated Deployments** - Git-based continuous deployment
- ✅ **Database Management** - PostgreSQL with automated backups
- ✅ **SSL/TLS Certificates** - Automatic Let's Encrypt integration
- ✅ **Service Monitoring** - Real-time metrics and alerting
- ✅ **API Access** - Comprehensive REST API with authentication

---

## 🚀 Getting Started

### Prerequisites
- WebOps control panel installed and running
- Valid user account with appropriate permissions
- Git repository with your application code

### First Login
1. Navigate to your WebOps instance (e.g., `https://webops.yourdomain.com`)
2. Log in with your credentials
3. Complete the onboarding tutorial (if available)
4. Set up two-factor authentication (recommended)

### Initial Setup Checklist
- [ ] Change default password
- [ ] Enable two-factor authentication
- [ ] Complete user profile
- [ ] Join appropriate teams
- [ ] Review available permissions
- [ ] Create first deployment

---

## 📊 Dashboard Overview

### Main Dashboard
- **Deployment Statistics**: Overview of all deployments
- **System Health**: CPU, memory, and disk usage
- **Recent Activity**: Latest deployment and system events
- **Quick Actions**: Common tasks and shortcuts
- **Team Activity**: Team-specific deployment status
- **Resource Usage**: Current resource consumption

### Navigation Menu
- **Dashboard**: Home screen with overview
- **Deployments**: Manage all applications
- **Databases**: Database management
- **Services**: System services and monitoring
- **Team**: User and team management
- **Settings**: System configuration
- **API Tokens**: Manage API access tokens
- **Audit Logs**: Security and activity logs

---

## 🚀 Deployment Management

### Creating a Deployment

#### Via Web Interface
1. Navigate to **Deployments** → **New Deployment**
2. Fill in deployment details:
   - **Name**: Unique identifier (lowercase, hyphens/underscores)
   - **Repository URL**: Git repository HTTPS URL
   - **Branch**: Default branch (main/master)
   - **Environment**: Production/Staging/Development
   - **Domain**: Custom domain (optional)
   - **Team**: Assign to team (if applicable)
3. Click **Create Deployment**

#### Via Command Line
```bash
# Switch to webops user
sudo -u webops -i

# Navigate to control panel
cd /opt/webops/control-panel
source venv/bin/activate

# Create deployment
python manage.py deploy_app \
    --name my-app \
    --repo https://github.com/user/repo \
    --branch main \
    --env production \
    --team backend-team
```

### Deployment Process

1. **Repository Cloning**: Git repository is cloned locally
2. **Dependency Installation**: Python/Node.js dependencies installed
3. **Build Process**: Application is built (if needed)
4. **Service Configuration**: Systemd service created
5. **Nginx Configuration**: Reverse proxy setup
6. **SSL Certificate**: Let's Encrypt certificate generation
7. **Service Start**: Application service started
8. **Health Check**: Deployment health verification

### Deployment Status

- **Pending**: Deployment queued
- **In Progress**: Deployment running
- **Success**: Deployment completed successfully
- **Failed**: Deployment failed (check logs)
- **Stopped**: Deployment manually stopped
- **Maintenance**: Deployment in maintenance mode

---

## 🗄️ Database Management

### Creating Databases

#### Via Web Interface
1. Navigate to **Databases** → **New Database**
2. Specify database name and owner
3. Configure access permissions
4. Set team access (if applicable)
5. Create database

#### Via Command Line
```bash
# Create PostgreSQL database
sudo -u webops psql -c "CREATE DATABASE myapp;"

# Create database user
sudo -u webops psql -c "CREATE USER myapp_user WITH PASSWORD 'secure_password';"

# Grant permissions
sudo -u webops psql -c "GRANT ALL PRIVILEGES ON DATABASE myapp TO myapp_user;"
```

### Database Features

- **Encrypted Storage**: All credentials encrypted at rest
- **Automatic Backups**: Regular database backups
- **Access Control**: Team-based database permissions
- **Connection Pooling**: Optimized connection management
- **Performance Monitoring**: Query performance tracking

---

## 👥 User Management

### User Types & Roles

WebOps supports sophisticated user management with role-based access control:

- **Super Admin**: Full platform access and configuration
- **Admin**: User management and deployment oversight
- **Developer**: Create and manage own deployments
- **Viewer**: Read-only access to dashboards and logs
- **Custom Roles**: Configurable permissions per organization needs

### Creating Users

#### Via Admin Interface
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

#### Via Command Line
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

### User Invitation System

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

## 🏢 Team Management

### Creating Teams

Teams allow you to organize users and share resources efficiently.

#### Via Command Line
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

#### Via Admin Interface
1. Navigate to **Teams** section in admin panel
2. Click **Add Team**
3. Configure team details:
   - Team name and description
   - Team lead (optional)
   - Default permissions for team members
   - Resource limits and quotas
   - Shared resources (databases, domains)

### Team Features

- **Shared Deployments**: Team members can collaborate on deployments
- **Resource Quotas**: Set limits on team resource usage
- **Team Notifications**: Slack/email notifications for team activities
- **Shared Databases**: Team-accessible database resources
- **Team-specific Domains**: Dedicated domains for team projects

### Team Collaboration

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

---

## 🔐 Role-Based Access Control (RBAC)

### Built-in Roles & Permissions

#### Super Admin Role
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

#### Admin Role
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

#### Developer Role
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

#### Viewer Role
```python
PERMISSIONS = [
    'view_own_deployments',
    'view_deployment_logs',
    'view_system_dashboard'
]
```

### Custom Role Creation

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

### Permission Management

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
```

---

## 🔒 Security Features

### Authentication Methods

#### Multi-Factor Authentication (2FA)
- **TOTP Apps**: Google Authenticator, Authy, Microsoft Authenticator
- **Backup Codes**: 10 single-use recovery codes per user
- **SMS Backup**: Optional SMS-based backup authentication
- **Hardware Tokens**: Support for FIDO2/WebAuthn hardware keys

```bash
# Enable 2FA for users
ENFORCE_2FA_FOR_ADMINS=True
REQUIRE_2FA_ALL_USERS=True

# Setup 2FA for specific user
python manage.py setup_2fa --username johndoe --send-qr-email
```

#### Single Sign-On (SSO)
- **SAML Integration**: Enterprise SAML providers
- **OAuth Providers**: Google, GitHub, Microsoft
- **LDAP/Active Directory**: Corporate directory integration
- **Custom Providers**: Extensible authentication system

### Password Policies

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

### Session Management

```bash
# Session security settings
SESSION_COOKIE_AGE=3600        # 1 hour session timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
MAX_CONCURRENT_SESSIONS=3      # Limit concurrent sessions per user
DETECT_UNUSUAL_LOGIN_PATTERNS=True
```

### Data Protection

- **Encryption at Rest**: Database and file encryption
- **TLS/SSL Encryption**: HTTPS everywhere
- **Secure Credentials**: Encrypted credential storage
- **Input Validation**: Comprehensive input sanitization
- **Audit Logging**: Complete access tracking

---

## 📊 Service Monitoring

### Health Monitoring

- **CPU Usage**: Real-time CPU utilization
- **Memory Usage**: RAM consumption tracking
- **Disk Usage**: Storage space monitoring
- **Network Traffic**: Bandwidth usage statistics
- **Uptime**: Service availability tracking
- **Response Times**: Application performance metrics

### Log Management

- **Application Logs**: Deployment-specific logs
- **System Logs**: Infrastructure and service logs
- **Access Logs**: HTTP request logging
- **Error Logs**: Error and exception tracking
- **Real-time Streaming**: Live log viewing
- **Log Retention**: Configurable log retention policies

### Alerting

- **Email Notifications**: Critical event alerts
- **Slack Integration**: Team channel notifications
- **Webhook Support**: Custom integration endpoints
- **Threshold-based**: Configurable alert thresholds
- **Escalation Policies**: Multi-level alert escalation

### Activity Monitoring

```bash
# View user activity
python manage.py user_activity --username johndoe --period 7d

# Generate activity report
python manage.py activity_report --team "Backend Team" --format pdf

# Monitor active sessions
python manage.py list_sessions --active --detailed
```

---

## ⚙️ Advanced Features

### Environment Management

- **Multiple Environments**: Dev, Staging, Production
- **Environment-specific Config**: Different settings per environment
- **Variable Management**: Secure environment variables
- **Configuration Templates**: Reusable configuration patterns

### Custom Domains

- **Domain Management**: Add custom domains to deployments
- **SSL Certificates**: Automatic Let's Encrypt certificates
- **DNS Configuration**: Automated DNS record management
- **Domain Verification**: Ownership verification

### Backup and Recovery

- **Automated Backups**: Regular database and file backups
- **Point-in-time Recovery**: Specific timestamp recovery
- **Export/Import**: Data migration between instances
- **Disaster Recovery**: Complete system restoration

### LLM Deployment

WebOps supports Large Language Model deployment using vLLM:

- **Hugging Face Integration**: Direct model deployment from HF Hub
- **GPU Acceleration**: NVIDIA GPU support with CUDA
- **Model Quantization**: AWQ, GPTQ support for memory efficiency
- **OpenAI-Compatible API**: Standard API endpoints
- **Multi-GPU Support**: Tensor parallelism for large models

---

## 💻 Command Line Interface

### Common Commands

```bash
# Deployment management
python manage.py deploy_app --name myapp --repo https://github.com/user/repo
python manage.py list_deployments
python manage.py restart_deployment myapp
python manage.py stop_deployment myapp

# Database operations
python manage.py create_database myapp_db
python manage.py list_databases
python manage.py backup_database myapp_db

# Service management
python manage.py service_status
python manage.py restart_services
python manage.py view_logs myapp

# User management
python manage.py create_user username email password
python manage.py list_users
python manage.py reset_password username
```

### Administration Commands

```bash
# System status
sudo ./scripts/webops-admin.sh status
sudo ./scripts/webops-admin.sh health

# Log management
sudo ./scripts/webops-admin.sh logs webops-web
sudo ./scripts/webops-admin.sh logs webops-worker

# Backup and restore
sudo ./scripts/webops-admin.sh backup
sudo ./scripts/webops-admin.sh restore backup_file.tar.gz

# Security audit
sudo ./scripts/webops-admin.sh security-check
sudo ./scripts/webops-admin.sh sudo-audit
```

---

## 🔑 API Token Management

### Personal Access Tokens

Create and manage API tokens for programmatic access:

#### Via Web Interface
1. Login to WebOps dashboard
2. Navigate to **Settings** → **API Tokens**
3. Click **Generate New Token**
4. Configure token settings:
   - Token name and description
   - Permissions and scopes
   - Expiration date
   - IP restrictions (optional)
5. Copy and securely store the token

#### Via Command Line
```bash
# Create token via CLI
python manage.py create_token \
    --user johndoe \
    --name "CLI Access" \
    --permissions deployments,databases \
    --expires-in 90d

# List user tokens
python manage.py list_tokens --user johndoe

# Revoke token
python manage.py revoke_token --token-id abc123
```

### Token Configuration

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

### Service Account Tokens

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

## 🔗 Single Sign-On Integration

### LDAP/Active Directory

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

### OAuth Providers

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

## 🔧 Troubleshooting

### Common Issues

#### Deployment Failures
- Check repository URL and access permissions
- Verify build dependencies and requirements
- Review application logs for specific errors
- Ensure sufficient system resources

#### Database Connection Issues
- Verify database credentials
- Check PostgreSQL service status
- Review connection string configuration
- Validate network connectivity

#### Service Startup Problems
- Check system resource availability
- Review service configuration files
- Examine systemd journal logs
- Verify file permissions

#### Permission Errors
- Verify user role assignments
- Check team membership
- Review resource ownership
- Validate API token permissions

#### Authentication Issues
- Verify 2FA setup
- Check SSO configuration
- Review session settings
- Validate password policies

### Diagnostic Tools

```bash
# System diagnostics
sudo ./scripts/webops-admin.sh diagnose

# Resource monitoring
top -u webops
free -h
df -h /opt/webops

# Network connectivity
curl -I http://localhost:8000
netstat -tlnp | grep :8000

# Process inspection
ps aux | grep webops
pstree -p | grep webops

# User activity analysis
python manage.py user_activity --username johndoe --detailed
python manage.py security_audit --failed-logins --suspicious-activity
```

---

## 📋 Best Practices

### Deployment Best Practices

- **Use Semantic Versioning**: Tag releases properly
- **Implement Health Checks**: Add /health endpoints
- **Configure Proper Timeouts**: Set reasonable timeouts
- **Use Environment Variables**: Avoid hardcoded configuration
- **Implement Graceful Shutdown**: Handle SIGTERM properly
- **Team Collaboration**: Use team-based deployments
- **Resource Monitoring**: Set up alerts and monitoring

### Security Best Practices

- **Enable 2FA**: Require two-factor authentication
- **Regular Updates**: Keep system and dependencies updated
- **Minimal Permissions**: Principle of least privilege
- **Regular Audits**: Security and access reviews
- **Backup Strategy**: Comprehensive backup plan
- **Incident Response**: Prepared response procedures
- **API Token Security**: Rotate tokens regularly
- **Session Management**: Configure secure sessions

### User Management Best Practices

- **Role-Based Access**: Use appropriate roles for users
- **Team Organization**: Organize users into logical teams
- **Regular Reviews**: Periodic access reviews
- **Onboarding Process**: Standardized user onboarding
- **Offboarding Process**: Secure user deactivation
- **Training Programs**: User education and training

### Performance Optimization

- **Caching Strategy**: Implement appropriate caching
- **Database Optimization**: Query optimization and indexing
- **Resource Limits**: Set appropriate resource constraints
- **CDN Integration**: Content delivery network usage
- **Compression**: Enable gzip/brotli compression
- **Monitoring**: Continuous performance monitoring

---

## 📞 Support and Resources

### Documentation
- [Quick Start Guide](../getting-started/quick-start-guide.md)
- [Installation Guide](../getting-started/installation.md)
- [Deployment Guide](../deployment/deployment-guide.md)
- [LLM Deployment Guide](../deployment/llm-deployment-guide.md)
- [Security Features](../security/security-features.md)
- [API Reference](./api-reference.md)

### Community Support
- **GitHub Issues**: Bug reports and feature requests
- **Discussion Forums**: Community discussions
- **Slack Channel**: Real-time support and chat
- **Documentation Contributions**: Help improve docs

### Professional Support
- **Enterprise Support**: Priority support for businesses
- **Consulting Services**: Custom implementation help
- **Training Programs**: Team training and workshops
- **Managed Services**: Fully managed WebOps instances

### User Statistics Dashboard

```bash
# View comprehensive user statistics
python manage.py user_stats --detailed
```

**Sample Output:**
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

## 📱 Mobile & Remote Access

### Progressive Web App (PWA)

**Mobile User Management:**
- Install WebOps as native app on mobile devices
- Offline capability for viewing deployment status
- Push notifications for deployment events
- Touch-optimized interface for mobile management

### Remote Access Security

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

## 📚 Version Information

**Current Version**: v2.0.0  
**Release Date**: 2024-12-20  
**Status**: Production Ready  
**Python Version**: 3.13+  
**Django Version**: 5.2.6+  

### Recent Updates
- Enhanced user management with RBAC
- Team collaboration features
- LLM deployment support
- Improved security features
- API token management
- SSO integration

---

**Need help?** Check our [troubleshooting guide](../operations/troubleshooting.md) or create an issue on GitHub.

---

**WebOps - Enterprise-grade self-hosted deployment platform with comprehensive user management** 🚀👥