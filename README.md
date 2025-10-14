# WebOps

> A minimal, self-hosted VPS hosting platform for deploying and managing web applications

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-5.0+-green.svg)](https://www.djangoproject.com/)
[![GitHub](https://img.shields.io/badge/GitHub-DagiiM%2Fwebops-blue.svg)](https://github.com/DagiiM/webops)

WebOps is a lightweight hosting platform that transforms a fresh VPS into a fully-functional web application deployment system with a single command. Deploy Django applications, static sites, and more through a clean web interface or CLI.

## ✨ Features

- **🚀 One-Command Setup** - Complete VPS orchestration via `./setup.sh`
- **🎯 Minimal & Fast** - Zero npm dependencies, pure HTML/CSS/JS frontend
- **🔒 Secure by Default** - Automated SSL, encrypted credentials, isolated processes
- **🐘 PostgreSQL Included** - Automatic database creation per application
- **⚡ Background Tasks** - Celery integration for async operations
- **🌐 Nginx Powered** - Automatic reverse proxy and virtual host configuration
- **📊 Simple Management** - Clean web UI for all operations
- **🔧 CLI Available** - Command-line tool for power users
- **📝 Real-time Logs** - Stream application logs from the dashboard

## 🎯 Use Cases

- Personal project hosting
- Development/staging environments
- Small team deployments
- Learning DevOps practices
- Alternative to Heroku/Railway/Render for small projects

## 📋 Prerequisites

- Fresh VPS or dedicated server
- Ubuntu 22.04 LTS (or Debian 11+)
- Minimum 2GB RAM, 2 CPU cores
- Root or sudo access
- Domain name (optional, but recommended for SSL)

## 🚀 Quick Start

### Development (MVP)

**Current Status**: ✅ MVP Complete - Minimal working version ready for testing

For development and testing the MVP:

```bash
cd webops/control-panel
./quickstart.sh
source venv/bin/activate
python manage.py runserver
```

Then visit http://127.0.0.1:8000 (login: `admin` / `admin123`)

See **[docs/quick-start-guide.md](docs/quick-start-guide.md)** for detailed development setup.

### Production Installation (Coming Soon)

1. **SSH into your server**:
```bash
ssh root@your-server-ip
```

2. **Clone the repository**:
```bash
git clone https://github.com/DagiiM/webops.git
cd webops
```

3. **Run the setup script**:
```bash
chmod +x setup.sh
sudo ./setup.sh
```

4. **Follow the prompts**:
   - Enter domain name for control panel (or use IP)
   - Create admin username and password
   - Confirm installation

5. **Access WebOps**:
   - Open browser and navigate to: `https://your-domain.com` or `http://your-server-ip:8000`
   - Login with the admin credentials you created

That's it! Your VPS is now ready to host applications.

## 📖 Usage

### Via Web Interface

1. **Login** to the WebOps control panel
2. **Navigate** to "New Deployment"
3. **Fill in** the deployment form:
   - Service name: `my-django-app`
   - Repository URL: `https://github.com/username/django-project`
   - Branch: `main`
   - Domain: `myapp.example.com` (optional)
4. **Click** "Deploy" and watch the progress
5. **Access** your application at the configured domain

### Via CLI

Install the CLI tool:
```bash
pip install webops-cli
```

Configure:
```bash
webops config --url https://panel.yourdomain.com --token YOUR_API_TOKEN
```

Deploy an application:
```bash
webops deploy --repo https://github.com/user/repo --name myapp --domain myapp.com
```

List deployments:
```bash
webops list
```

View logs:
```bash
webops logs myapp --tail 100 --follow
```

Restart service:
```bash
webops restart myapp
```

## 🏗️ Architecture

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

**Tech Stack:**
- **Backend**: Django 5.0+, Python 3.11+
- **Frontend**: Pure HTML5/CSS3/Vanilla JavaScript (zero npm dependencies)
- **Database**: PostgreSQL 14+
- **Web Server**: Nginx
- **Task Queue**: Celery + Redis
- **Process Manager**: systemd
- **SSL**: Let's Encrypt (Certbot)

## 📁 Project Structure

```
webops/
├── setup.sh                 # Main installation script
├── control-panel/           # Django control panel
│   ├── apps/
│   │   ├── core/           # Shared utilities
│   │   ├── deployments/    # Deployment management
│   │   ├── databases/      # Database management
│   │   └── services/       # Service monitoring
│   ├── templates/          # HTML templates
│   └── static/             # CSS and JS (no build required)
├── cli/                     # Command-line tool
├── templates/               # System templates (Nginx, systemd)
├── scripts/                 # Helper scripts
└── docs/                    # Documentation
```

## 🔧 Configuration

WebOps uses environment variables for configuration. After installation, edit `/opt/webops/control-panel/.env`:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/webops_db

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0

# Security
ENCRYPTION_KEY=your-encryption-key
```

## 🚢 Deploying Applications

### Django Applications

Your Django project should have:
- `requirements.txt` - Python dependencies
- `manage.py` - Django management script
- Proper `ALLOWED_HOSTS` configuration
- Static files configuration

WebOps will automatically:
1. Clone your repository
2. Create a virtual environment
3. Install dependencies
4. Create a PostgreSQL database
5. Run migrations
6. Collect static files
7. Configure Nginx and systemd
8. Obtain SSL certificate (if domain provided)
9. Start your application

### Static Sites

Simply point to a repository with HTML/CSS/JS files. WebOps will:
1. Clone the repository
2. Configure Nginx to serve files
3. Set up SSL certificate

## 🗄️ Database Management

Each deployed application gets its own PostgreSQL database with unique credentials.

**View credentials:**
- Web UI: Navigate to "Databases" → Select your database
- CLI: `webops db:credentials myapp`

**Connection string format:**
```
postgresql://username:password@localhost:5432/database_name
```

## 📊 Monitoring & Logs

### Web Interface
- Dashboard shows system resources (CPU, RAM, disk)
- Service status indicators
- Real-time log streaming

### CLI
```bash
# View logs
webops logs myapp --tail 100

# Follow logs in real-time
webops logs myapp --follow

# System logs
journalctl -u webops-web -f
```

### Log Files
- Control panel: `/opt/webops/control-panel/logs/webops.log`
- Applications: `/opt/webops/deployments/<app-name>/logs/`
- Nginx: `/var/log/nginx/`

## 🔐 Security

WebOps implements multiple security layers:

- **Dedicated System User**: All services run as `webops` user (not root)
- **Limited Sudo Access**: Passwordless sudo only for specific deployment commands
- **SSL/TLS**: Automatic HTTPS with Let's Encrypt
- **Firewall**: UFW configured (ports 80, 443, 22 only)
- **Process Isolation**: Each app isolated via systemd with resource limits
- **Encrypted Credentials**: Database passwords encrypted at rest
- **CSRF Protection**: All forms protected
- **Session Security**: Secure cookies, configurable timeout
- **Audit Trail**: All sudo commands logged to /var/log/auth.log
- **Regular Updates**: Easy update mechanism

### Security Architecture

The `webops` system user provides security through:
- **Principle of Least Privilege**: Services don't run as root
- **Command Whitelisting**: Limited sudo access (nginx, systemd, certbot only)
- **Attack Surface Reduction**: Compromised deployment ≠ root access
- **Complete Auditability**: All operations logged and traceable

See [docs/webops-user-guide.md](docs/webops-user-guide.md) for detailed security documentation.

**Validation & Monitoring:**
```bash
# Validate webops user setup
sudo ./scripts/validate-user-setup.sh

# Run security audit
sudo ./scripts/webops-security-check.sh

# Audit sudo usage
sudo ./scripts/webops-admin.sh sudo-audit
```

## 🔄 Updates

Update WebOps to the latest version:

```bash
cd /opt/webops
sudo ./scripts/update.sh
```

Or via CLI:
```bash
webops self-update
```

## 🛠️ Troubleshooting

### Setup fails
```bash
# Check logs
tail -f /var/log/webops-setup.log

# Verify system requirements
df -h  # Check disk space
free -h  # Check RAM
```

### Deployment fails
```bash
# Check deployment logs in web UI
# Or via CLI
webops logs myapp

# Check Celery workers
sudo systemctl status webops-celery
```

### Application won't start
```bash
# Check systemd service
sudo systemctl status <app-name>

# Check application logs
journalctl -u <app-name> -n 50
```

### Nginx issues
```bash
# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Check error logs
sudo tail -f /var/log/nginx/error.log
```

### Database connection issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -h localhost -U postgres -l
```

## 📚 Documentation

**Getting Started:**
- [Installation Guide](docs/installation.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Quick Start Guide](docs/quick-start-guide.md)

**Security:**
- [WebOps User Guide](docs/webops-user-guide.md) - Comprehensive guide to the webops system user
- [Security Features](docs/security-features.md) - All security features and architecture
- [Security Hardening](docs/security-hardening.md) - Security best practices

**Reference:**
- [API Reference](docs/api-reference.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development Guide](CLAUDE.md)

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Development Setup:**
```bash
# Clone repository
git clone https://github.com/DagiiM/webops.git
cd webops

# Set up development environment
python -m venv venv
source venv/bin/activate
pip install -r control-panel/requirements.txt

# Run tests
cd control-panel
python manage.py test

# Run development server
python manage.py runserver
```

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run with coverage
coverage run --source='.' manage.py test
coverage report

# Run specific app tests
python manage.py test apps.deployments
```

## 📝 Roadmap

- [x] Core deployment system
- [x] Django application support
- [x] Static site support
- [x] PostgreSQL management
- [x] CLI tool
- [ ] Docker container support
- [ ] Automatic backups
- [ ] Multi-user support
- [ ] GitLab/Bitbucket integration
- [ ] Webhook auto-deployments
- [ ] Resource usage alerts
- [ ] Blue-green deployments
- [ ] MySQL support

## ❓ FAQ

**Q: Can I host multiple applications on one server?**  
A: Yes! WebOps is designed to host multiple applications with isolated environments.

**Q: Do I need a domain name?**  
A: No, but it's recommended for SSL certificates. You can use IP addresses for initial setup.

**Q: Can I use my own SSL certificates?**  
A: Yes, you can manually configure custom certificates in Nginx.

**Q: What happens if deployment fails?**  
A: WebOps will log the error and keep your previous deployment running (if any). Check logs for details.

**Q: Can I SSH into deployed applications?**  
A: Yes, all deployments are in `/opt/webops/deployments/<app-name>/`

**Q: How do I backup my data?**  
A: Use the included backup script: `sudo /opt/webops/scripts/backup.sh`

**Q: Can I use WebOps in production?**  
A: Yes, but ensure you follow security best practices and keep the system updated.

**Q: Is there a migration path from Heroku?**  
A: Yes! WebOps supports standard Django deployments. Just point to your repository.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Django project for the amazing framework
- Celery for distributed task queue
- Nginx for rock-solid web serving
- PostgreSQL for reliable database
- The open-source community

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/DagiiM/webops/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DagiiM/webops/discussions)
- **Email**: support@ifinsta.com
- **Owner**: Douglas Mutethia ([GitHub](https://github.com/DagiiM))

## 🌟 Star History

If you find WebOps useful, please consider giving it a star on GitHub!

---

**Built with ❤️ for developers who want simple, reliable hosting without the complexity.**

Made with pure HTML, CSS, and vanilla JavaScript - no build tools required.