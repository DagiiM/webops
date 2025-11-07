# Connection Timeout Fix

## Problem
After cloning WebOps, accessing the server via IP address (e.g., 213.199.34.33) resulted in:
```
ERR_CONNECTION_TIMED_OUT
This site can't be reached
```

## Root Cause
The installation was incomplete - files were cloned but no services were set up or running:
- No web server (nginx) installed
- No Django application configured or running
- No database setup
- Sudo configuration issues blocking service management

## Solution

### 1. Fix Sudo Configuration
```bash
chown root:root /etc/sudoers /etc/sudo.conf /etc/sudoers.d
chmod 440 /etc/sudoers
chmod 644 /etc/sudo.conf
chmod 755 /etc/sudoers.d
```

### 2. Install Nginx
```bash
apt-get update
apt-get install -y nginx
```

### 3. Run WebOps Setup
```bash
cd /home/user/webops/control-panel
WEBOPS_SKIP_DEPENDENCY_CHECK=1 bash quickstart.sh
```

This creates:
- Python virtual environment with all dependencies
- SQLite database with migrations
- Admin user (credentials in `.dev_admin_password`)
- Static files collected

### 4. Start Gunicorn
```bash
cd /home/user/webops/control-panel
source venv/bin/activate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --daemon
```

### 5. Configure Nginx
Create `/etc/nginx/sites-available/webops`:
```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 100M;

    location /static/ {
        alias /home/user/webops/control-panel/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /home/user/webops/control-panel/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable the site:
```bash
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/webops /etc/nginx/sites-enabled/webops
nginx -t
nginx
```

### 6. Update Django Settings
Edit `.env` to allow all hosts:
```bash
ALLOWED_HOSTS=*
```

For production, specify exact domains:
```bash
ALLOWED_HOSTS=yourdomain.com,213.199.34.33,21.0.0.22
```

Restart Gunicorn after changes:
```bash
pkill -f gunicorn
source venv/bin/activate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --daemon
```

## Verification

1. Check services are running:
```bash
ps aux | grep gunicorn
ps aux | grep nginx
```

2. Test local access:
```bash
curl -I http://127.0.0.1/
# Should return: HTTP/1.1 302 Found (redirect to login)
```

3. Access via browser:
```
http://YOUR_SERVER_IP/
```

## Login Credentials

- **Username**: `admin`
- **Password**: Check `/home/user/webops/control-panel/.dev_admin_password`

## For Persistent Service (Production)

Since systemd is not available in this environment, consider:

1. **Use a process manager like supervisor**:
```bash
apt-get install supervisor
```

2. **Or create startup script** that runs on boot:
```bash
#!/bin/bash
cd /home/user/webops/control-panel
source venv/bin/activate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --daemon
nginx
```

3. **For proper production deployment**, use a server with systemd and follow the full installation guide in `docs/getting-started/installation.md`.

## Notes

- This is a development setup suitable for testing
- For production:
  - Set `DEBUG=False` in `.env`
  - Use PostgreSQL instead of SQLite
  - Set up SSL certificates
  - Configure proper firewall rules
  - Use systemd services for auto-restart
  - Set specific ALLOWED_HOSTS
  - Enable fail2ban and other security measures

## Related Documentation

- [Installation Guide](../getting-started/installation.md)
- [Quick Start Guide](../getting-started/quick-start-guide.md)
- [Troubleshooting Guide](../operations/troubleshooting.md)
