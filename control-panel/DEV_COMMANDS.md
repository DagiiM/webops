# WebOps Development Commands

Quick reference for starting and managing the WebOps development environment.

## Starting Development Environment

### Start Everything (Recommended)
Starts Django development server + Celery worker + Celery Beat together:
```bash
./start_dev.sh
```

**Features:**
- ✅ Auto-starts Celery worker for background tasks
- ✅ Auto-starts Celery Beat for scheduled tasks
- ✅ Checks Redis connection
- ✅ Cleans up existing workers
- ✅ Single Ctrl+C stops everything
- ✅ Logs available at `/tmp/celery_webops.log`

### Start Django Only
If you only need the Django server without background tasks:
```bash
source venv/bin/activate
python manage.py runserver
```

⚠️ **Note:** Deployments won't work without Celery!

## Stopping Services

### Stop Everything
```bash
./stop_dev.sh
```

Or just press **Ctrl+C** if you used `./start_dev.sh`

### Stop Celery Only
```bash
./start_celery.sh stop
```

## Managing Celery

### Check Celery Status
```bash
./start_celery.sh status
```

### View Celery Logs
```bash
./start_celery.sh logs
# or
tail -f /tmp/celery_webops.log
```

### Restart Celery (after code changes)
```bash
./start_celery.sh restart
```

## First Time Setup

```bash
cd control-panel
./quickstart.sh
./start_dev.sh
```

Visit: http://127.0.0.1:8000
Login: `admin` / `admin123`

## Troubleshooting

### "Redis is not running"
```bash
# WSL2/Ubuntu
sudo service redis-server start

# macOS
brew services start redis

# Check if running
redis-cli ping
# Should respond: PONG
```

### Celery workers stuck
```bash
# Kill all Celery processes
pkill -9 -f celery

# Restart
./start_dev.sh
```

### Port already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
./start_dev.sh 8001
```

## Development Workflow

### Making Code Changes

**For Django changes:**
- Just save the file
- Django auto-reloads

**For Celery task changes:**
```bash
# Restart Celery to pick up new code
./start_celery.sh restart
```

**For model changes:**
```bash
python manage.py makemigrations
python manage.py migrate

# Restart Celery if tasks use the new models
./start_celery.sh restart
```

### Running Tests
```bash
./venv/bin/python manage.py test apps.deployments
```

### Creating Deployments

Deployments require Celery to be running!

1. Ensure Celery is running: `./start_celery.sh status`
2. Create deployment via web UI or API
3. Check logs: `./start_celery.sh logs`

## Production vs Development

### Development (Current)
- Uses `./start_dev.sh`
- Celery runs in background
- Django development server
- SQLite database (default)
- No systemd required

### Production
- Uses systemd services
- Celery managed by `systemd`
- Gunicorn/Uvicorn for Django
- PostgreSQL database
- Nginx reverse proxy

## Quick Aliases (Optional)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# WebOps aliases
alias webops-start='cd ~/webops/control-panel && ./start_dev.sh'
alias webops-stop='cd ~/webops/control-panel && ./stop_dev.sh'
alias webops-celery='cd ~/webops/control-panel && ./start_celery.sh'
alias webops-logs='tail -f /tmp/celery_webops.log'
```

Then reload: `source ~/.bashrc`

Now you can just type:
- `webops-start` - Start everything
- `webops-stop` - Stop everything
- `webops-logs` - View Celery logs
- `webops-celery status` - Check Celery status

---

**Need help?** Check `/docs` or create an issue on GitHub.
