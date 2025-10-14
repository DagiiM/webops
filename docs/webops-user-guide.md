# WebOps User Guide

**Complete guide to using WebOps for application deployment and management**

**Project Owner:** [Douglas Mutethia](https://github.com/DagiiM) | **Company:** Eleso Solutions  
**Repository:** [https://github.com/DagiiM/webops](https://github.com/DagiiM/webops)

---

## Overview

WebOps is a self-hosted deployment platform that provides:
- **Application Deployment**: Deploy any web application from Git repositories
- **Database Management**: PostgreSQL database creation and management
- **Service Monitoring**: Real-time health monitoring and logging
- **Security**: Enterprise-grade security with role-based access control
- **Team Collaboration**: Multi-user support with team management

---

## Getting Started

### Prerequisites
- WebOps control panel installed and running
- Valid user account with appropriate permissions
- Git repository with your application code

### First Login
1. Navigate to your WebOps instance
2. Log in with your credentials
3. Complete the onboarding tutorial (if available)

---

## Dashboard Overview

### Main Dashboard
- **Deployment Statistics**: Overview of all deployments
- **System Health**: CPU, memory, and disk usage
- **Recent Activity**: Latest deployment and system events
- **Quick Actions**: Common tasks and shortcuts

### Navigation Menu
- **Dashboard**: Home screen with overview
- **Deployments**: Manage all applications
- **Databases**: Database management
- **Services**: System services and monitoring
- **Team**: User and team management
- **Settings**: System configuration

---

## Deployment Management

### Creating a Deployment

#### Via Web Interface
1. Navigate to **Deployments** → **New Deployment**
2. Fill in deployment details:
   - **Name**: Unique identifier (lowercase, hyphens/underscores)
   - **Repository URL**: Git repository HTTPS URL
   - **Branch**: Default branch (main/master)
   - **Environment**: Production/Staging/Development
   - **Domain**: Custom domain (optional)
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
    --env production
```

### Deployment Process

1. **Repository Cloning**: Git repository is cloned locally
2. **Dependency Installation**: Python/Node.js dependencies installed
3. **Build Process**: Application is built (if needed)
4. **Service Configuration**: Systemd service created
5. **Nginx Configuration**: Reverse proxy setup
6. **SSL Certificate**: Let's Encrypt certificate generation
7. **Service Start**: Application service started

### Deployment Status

- **Pending**: Deployment queued
- **In Progress**: Deployment running
- **Success**: Deployment completed successfully
- **Failed**: Deployment failed (check logs)
- **Stopped**: Deployment manually stopped

---

## Database Management

### Creating Databases

#### Via Web Interface
1. Navigate to **Databases** → **New Database**
2. Specify database name and owner
3. Configure access permissions
4. Create database

#### Via Command Line
```bash
# Create PostgreSQL database
sudo -u webops psql -c "CREATE DATABASE myapp;"

# Create database user
sudo -u webops psql -c "CREATE USER myapp_user WITH PASSWORD 'secure_password';"

# Grant permissions
sudo -u webops psql -c "GRANT ALL PRIVILEGES ON DATABASE myapp TO myapp_user;"
```

### Database Credentials

- **Encrypted Storage**: All credentials encrypted at rest
- **Automatic Rotation**: Regular credential rotation
- **Access Control**: Granular permission management
- **Connection Strings**: Automatically generated for applications

---

## Service Monitoring

### Health Monitoring

- **CPU Usage**: Real-time CPU utilization
- **Memory Usage**: RAM consumption tracking
- **Disk Usage**: Storage space monitoring
- **Network Traffic**: Bandwidth usage statistics
- **Uptime**: Service availability tracking

### Log Management

- **Application Logs**: Deployment-specific logs
- **System Logs**: Infrastructure and service logs
- **Access Logs**: HTTP request logging
- **Error Logs**: Error and exception tracking
- **Real-time Streaming**: Live log viewing

### Alerting

- **Email Notifications**: Critical event alerts
- **Slack Integration**: Team channel notifications
- **Webhook Support**: Custom integration endpoints
- **Threshold-based**: Configurable alert thresholds
- **Escalation Policies**: Multi-level alert escalation

---

## User and Team Management

### User Roles

- **Administrator**: Full system access
- **Developer**: Deployment and database management
- **Viewer**: Read-only access
- **Operator**: Service management only

### Team Management

- **Team Creation**: Organize users into teams
- **Resource Allocation**: Team-specific resource limits
- **Access Control**: Team-based permission management
- **Collaboration**: Shared deployments and resources

### Permission System

- **Role-Based Access Control**: Granular permissions
- **Resource-level Permissions**: Per-deployment access
- **Team Inheritance**: Team-level permission inheritance
- **Temporary Access**: Time-limited permissions

---

## Security Features

### Authentication

- **Multi-Factor Authentication**: TOTP-based 2FA
- **Single Sign-On**: SAML/SSO integration
- **API Token Authentication**: Programmatic access
- **Session Management**: Secure session handling

### Authorization

- **Role-Based Access Control**: Fine-grained permissions
- **Team-based Permissions**: Group-level access control
- **Resource Ownership**: Creator-based permissions
- **Audit Logging**: Complete access tracking

### Data Protection

- **Encryption at Rest**: Database and file encryption
- **TLS/SSL Encryption**: HTTPS everywhere
- **Secure Credentials**: Encrypted credential storage
- **Input Validation**: Comprehensive input sanitization

---

## Advanced Features

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

---

## Command Line Interface

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

## Troubleshooting

### Common Issues

#### Deployment Failures
- Check repository URL and access permissions
- Verify build dependencies and requirements
- Review application logs for specific errors

#### Database Connection Issues
- Verify database credentials
- Check PostgreSQL service status
- Review connection string configuration

#### Service Startup Problems
- Check system resource availability
- Review service configuration files
- Examine systemd journal logs

#### Permission Errors
- Verify file and directory permissions
- Check user and group ownership
- Review sudo configuration

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
```

---

## Best Practices

### Deployment Best Practices

- **Use Semantic Versioning**: Tag releases properly
- **Implement Health Checks**: Add /health endpoints
- **Configure Proper Timeouts**: Set reasonable timeouts
- **Use Environment Variables**: Avoid hardcoded configuration
- **Implement Graceful Shutdown**: Handle SIGTERM properly

### Security Best Practices

- **Regular Updates**: Keep system and dependencies updated
- **Minimal Permissions**: Principle of least privilege
- **Regular Audits**: Security and access reviews
- **Backup Strategy**: Comprehensive backup plan
- **Incident Response**: Prepared response procedures

### Performance Optimization

- **Caching Strategy**: Implement appropriate caching
- **Database Optimization**: Query optimization and indexing
- **Resource Limits**: Set appropriate resource constraints
- **CDN Integration**: Content delivery network usage
- **Compression**: Enable gzip/brotli compression

---

## Support and Resources

### Documentation
- [Quick Start Guide](./quick-start-guide.md)
- [Installation Guide](./installation.md)
- [Deployment Guide](./deployment-guide.md)
- [Security Features](./security-features.md)
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

---

## Version Information

**Current Version**: v2.0.0  
**Release Date**: 2024-12-20  
**Status**: Production Ready  
**Python Version**: 3.13+  
**Django Version**: 5.2.6+  

---

**Need help?** Check our [troubleshooting guide](./troubleshooting.md) or create an issue on GitHub.

---

**WebOps - Enterprise-grade self-hosted deployment platform** 🚀