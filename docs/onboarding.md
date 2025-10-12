# WebOps Platform Comprehensive Overview

## Introduction

WebOps is a Django-based self-hosted platform designed for automatically hosting static websites and Django applications from GitHub repositories. It provides a complete web-based control panel with a focus on simplicity, security, and automation. The platform transforms a fresh VPS into a fully-functional web application deployment system with minimal configuration.

## Architecture Overview

WebOps follows a modular Django architecture with the following key components:

```
┌─────────────────────────────────────────────────┐
│                 VPS Server                       │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │      Nginx (Reverse Proxy + SSL)          │ │
│  └──────┬─────────────────────────────────────┘ │
│         │                                        │
│  ┌──────▼──────────┐    ┌──────────────────┐   │
│  │  WebOps Panel   │    │  User Apps       │   │
│  │   (Django)      │    │  - Django Apps   │   │
│  └────────┬────────┘    │  - Static Sites  │   │
│           │             └─────────┬────────┘   │
│  ┌────────▼────────┐              │            │
│  │   PostgreSQL    │◄─────────────┘            │
│  └─────────────────┘                           │
│                                                  │
│  ┌─────────────────┐    ┌──────────────────┐   │
│  │  Redis          │    │  Celery Workers  │   │
│  └─────────────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Technology Stack

- **Backend**: Django 5.0, Python 3.11+
- **Database**: PostgreSQL with encrypted credential storage
- **Task Queue**: Celery with Redis broker
- **Web Server**: Nginx for reverse proxy and static file serving
- **Frontend**: Pure HTML5/CSS3/JavaScript (zero npm dependencies)
- **Process Management**: systemd for service management
- **SSL**: Let's Encrypt integration with Certbot

## Django Application Structure

The control panel is organized into five primary Django apps:

### 1. Core App (`apps/core`)
Handles shared utilities, authentication, and security features:
- **Base Models**: Provides abstract base models with common fields
- **Two-Factor Authentication**: TOTP-based 2FA with backup codes
- **GitHub Integration**: OAuth flow for private repository access
- **Security Audit Logging**: Comprehensive security event tracking
- **System Health Monitoring**: Resource usage and system metrics
- **SSL Certificate Management**: Automated certificate tracking
- **Branding Settings**: Customizable UI elements

### 2. Deployments App (`apps/deployments`)
Manages application deployment lifecycle:
- **Deployment Model**: Tracks application status, configuration, and metadata
- **Deployment Service**: Handles repository cloning, dependency installation, and service setup
- **Service Manager**: Manages systemd services for deployed applications
- **Task Processing**: Celery tasks for asynchronous deployment operations
- **Contract Parser**: Validates deployment configurations and resource limits

### 3. Databases App (`apps/databases`)
Manages PostgreSQL databases for deployments:
- **Database Model**: Stores encrypted credentials and connection details
- **Automatic Creation**: Generates databases for new deployments
- **Credential Management**: Secure storage and retrieval of database passwords

### 4. Services App (`apps/services`)
Provides monitoring and alerting:
- **Service Status**: Tracks application health and resource usage
- **Resource Monitoring**: System-wide resource metrics
- **Alerts**: Configurable notifications for system events
- **Health Checks**: Periodic application availability testing

### 5. API App (`apps/api`)
RESTful API for external integrations:
- **Token Authentication**: Secure API access with revocable tokens
- **Rate Limiting**: Prevents abuse with configurable limits
- **Complete CRUD**: Full API access to all platform features

## Database Schema

The platform uses PostgreSQL with the following key tables:

### Core Tables
- `core_two_factor_auth`: TOTP secrets and backup codes
- `core_github_connection`: Encrypted OAuth tokens
- `core_security_audit_log`: Security event tracking
- `core_system_health_check`: System metrics snapshots
- `core_ssl_certificate`: Certificate monitoring
- `core_branding_settings`: UI customization

### Deployment Tables
- `deployments`: Application metadata and configuration
- `deployment_logs`: Detailed operation logs

### Database Tables
- `databases`: Encrypted database credentials

### Service Tables
- `service_status`: Application health tracking
- `resource_usage`: System metrics history
- `alerts`: Notification system
- `health_checks`: Application availability results

### API Tables
- `api_tokens`: Authentication tokens

## Deployment Workflow

The deployment process is orchestrated through the following stages:

### 1. Repository Processing
- Clones Git repository (public or private via GitHub OAuth)
- Validates repository URLs for security (SSRF protection)
- Detects project type (Django or static site)

### 2. Environment Setup
- Creates isolated deployment directory
- Sets up Python virtual environment
- Installs dependencies from requirements.txt
- Generates secure environment variables

### 3. Database Configuration
- Creates PostgreSQL database with unique credentials
- Stores encrypted passwords in the database
- Provides connection strings via environment variables

### 4. Application Configuration
- Runs Django migrations automatically
- Collects static files
- Configures settings for production

### 5. Service Creation
- Generates systemd service file
- Configures Nginx reverse proxy
- Sets up SSL certificates with Let's Encrypt
- Enables and starts the service

### 6. Monitoring Setup
- Begins health checks
- Tracks resource usage
- Sets up alerting

## Security Features

WebOps implements enterprise-grade security with multiple layers:

### Authentication & Authorization
- **Two-Factor Authentication**: TOTP-based 2FA with QR code setup and backup codes
- **Password Security**: PBKDF2-SHA256 hashing with configurable policies
- **Session Management**: Secure cookies with configurable timeouts

### Input Validation & Protection
- **Repository URL Validation**: Prevents SSRF attacks, only allows approved hosts
- **Environment Variable Sanitization**: Blocks SQL injection and command injection patterns
- **XSS Prevention**: Django template auto-escaping with additional validation
- **CSRF Protection**: All forms protected with CSRF tokens

### Deployment Isolation
- **Per-Deployment Users**: Each application runs as dedicated system user
- **Resource Limits**: CPU, memory, and process restrictions via systemd
- **Filesystem Restrictions**: Controlled access to deployment directories only
- **Network Isolation**: Blocked access to private networks

### Monitoring & Auditing
- **Security Audit Log**: Tracks all security-relevant events with metadata
- **Failed Login Detection**: Blocks IPs after multiple failed attempts
- **Token Monitoring**: API token usage tracking and anomaly detection
- **System Health Monitoring**: Real-time resource usage tracking

### SSL/TLS Management
- **Automated Certificates**: Let's Encrypt integration with auto-renewal
- **Certificate Monitoring**: Expiry tracking and failure alerts
- **Secure Configuration**: TLS 1.2+ with strong cipher suites

## Setup and Deployment Process

### Development Setup (MVP)
```bash
cd webops/control-panel
./quickstart.sh
source venv/bin/activate
python manage.py runserver
```
- SQLite database for development
- Auto-generated admin user (admin/admin123)
- Local environment configuration

### Production Installation
```bash
git clone https://github.com/yourusername/webops.git
cd webops
sudo ./setup.sh
```
- System dependency installation
- PostgreSQL and Redis setup
- Nginx configuration
- SSL certificate issuance
- Security hardening

### Configuration
Key environment variables:
- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: PostgreSQL connection string
- `ENCRYPTION_KEY`: Fernet key for password encryption
- `WEBOPS_INSTALL_PATH`: Base installation directory
- `GITHUB_CLIENT_ID/SECRET`: For private repository access

## Key Features and Capabilities

### Core Functionality
- **One-Command Setup**: Complete VPS orchestration via setup script
- **GitHub Integration**: Deploy from public or private repositories
- **Automatic SSL**: Let's Encrypt certificates with renewal
- **Database Management**: Automatic PostgreSQL setup per application
- **Real-time Logs**: Stream deployment and application logs

### Developer Experience
- **Zero Dependencies**: No npm or build tools required
- **Clean UI**: Professional interface with keyboard shortcuts
- **Progressive Web App**: Installable on desktop and mobile
- **API Access**: Complete REST API with authentication
- **CLI Tool**: Command-line interface for power users

### Enterprise Features
- **Multi-User Support**: Team collaboration with role-based access
- **Resource Monitoring**: System health and performance metrics
- **Backup System**: Automated database backups
- **Security Auditing**: Comprehensive security audit script
- **Rate Limiting**: Configurable limits on API usage

## Production Considerations

### Performance
- Resource limits per deployment
- Efficient static file serving through Nginx
- Database connection pooling
- Cached template rendering

### Scalability
- Horizontal scaling through multiple VPSes
- Load balancer configuration support
- Database clustering preparation
- CDN integration capabilities

### Reliability
- Automated service recovery
- Health check monitoring
- Graceful degradation
- Backup and restore procedures

### Maintenance
- Automated security updates
- Log rotation and retention
- Certificate renewal
- System audit scheduling

## Potential Challenges

1. **Resource Management**: Ensuring fair resource allocation between deployments
2. **Security Isolation**: Maintaining strict separation between applications
3. **Backup Strategy**: Implementing reliable backup and recovery procedures
4. **Monitoring**: Scaling monitoring infrastructure as deployments grow
5. **Updates**: Managing system updates without disrupting services
6. **Complex Deployments**: Handling applications with non-standard requirements

## Conclusion

WebOps represents a comprehensive, enterprise-grade solution for self-hosted application deployment. By combining Django's robust framework with modern security practices and automation, it provides a compelling alternative to commercial hosting platforms. The platform's focus on simplicity, security, and automation makes it particularly suitable for development teams, small businesses, and organizations looking to maintain control over their hosting infrastructure while minimizing operational overhead.

The modular architecture allows for customization and extension, while the comprehensive security features ensure production readiness. With its clean separation of concerns and well-designed deployment workflow, WebOps successfully abstracts away the complexity of application hosting while providing the flexibility needed for real-world deployments.