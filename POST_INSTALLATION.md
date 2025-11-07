# Post-Installation Guide

## How to Access the Server After Installation

### For Development Setup (quickstart.sh)

After running `quickstart.sh`, the server is **NOT automatically started**. You must manually start it:

```bash
cd control-panel
./start_dev.sh
```

**Access the server:**
```
URL: http://127.0.0.1:8000
Username: admin
Password: (shown during quickstart or in .dev_admin_password file)
```

**To view your password:**
```bash
cat control-panel/.dev_admin_password
```

**To stop the development server:**
```bash
# Press Ctrl+C in the terminal where start_dev.sh is running
# Or run:
./control-panel/stop_dev.sh
```

---

### For Production Setup (install.sh)

After running the production installer, services **ARE automatically started** and verified. The installation will **FAIL** if services don't start successfully.

**What happens during installation:**
- ✅ Services are enabled for auto-start on boot
- ✅ Services are started with up to 3 retry attempts
- ✅ Installation waits 5 seconds for web services to initialize
- ✅ Network accessibility is verified (0.0.0.0 binding)
- ✅ HTTP connectivity is tested
- ❌ Installation **FAILS** if any critical service doesn't start

**If installation completed successfully, your services ARE running.**

#### Verify Services Are Running (Optional)

If you want to double-check:

```bash
# Check all WebOps services
systemctl status webops-web
systemctl status webops-worker
systemctl status webops-beat
systemctl status webops-channels

# Or check all at once
systemctl status "webops-*"
```

#### If Installation Failed Due to Service Startup

If the installation failed with "Critical services failed to start":

1. **Check the error logs** shown during installation
2. **Fix the underlying issue** (usually PostgreSQL, Redis, or port conflicts)
3. **Re-run the installation**

Common fixes:
```bash
# Ensure PostgreSQL is running
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Ensure Redis is running
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Check for port conflicts
sudo ss -tulpn | grep :8000

# Then re-run install
sudo ./provisioning/versions/v1.0.0/lifecycle/install.sh
```

#### Access the Control Panel

The server is **automatically accessible** from your network on port 8000:

```bash
# Find your server IP
hostname -I | awk '{print $1}'

# Open in browser:
# http://YOUR_SERVER_IP:8000
```

**Default Configuration:**
- **Binding:** 0.0.0.0 (all network interfaces)
- **Port:** 8000
- **Access:** From any IP address on your network

This means you can access the control panel from:
- The server itself: `http://localhost:8000`
- Other computers on the network: `http://SERVER_IP:8000`
- The internet (if firewall allows): `http://YOUR_PUBLIC_IP:8000`

#### Get Admin Credentials

```bash
# View admin credentials
sudo cat /opt/webops/.secrets/admin_credentials.txt

# The file contains:
# - Username (usually: admin)
# - Randomly generated password
# - Control panel URL
```

#### Step 5: Verify Auto-Restart is Working

Check that services are configured for automatic restart:

```bash
# Check restart policy
systemctl show webops-web | grep "Restart="
# Should show: Restart=always

# Check service status
systemctl is-enabled webops-web
# Should show: enabled
```

---

## Auto-Restart Configuration

### How Auto-Restart Works

All WebOps systemd services are configured with:

```ini
Restart=always
RestartSec=10s              # Wait 10 seconds before restart
StartLimitBurst=3           # Max 3 restart attempts
StartLimitInterval=600s     # Within 10-minute window
```

**This means:**
- If a service crashes, systemd automatically restarts it after 10 seconds
- Up to 3 restart attempts within 10 minutes
- After 3 failures, systemd stops trying (prevents restart loops)

### Testing Auto-Restart

To verify auto-restart is working:

```bash
# Kill the web service process
sudo systemctl kill webops-web

# Wait 10 seconds, then check status
sleep 10
systemctl status webops-web

# Should show "active (running)" if auto-restart worked
```

### Checking Restart History

```bash
# View recent restart events
journalctl -u webops-web -n 50 --no-pager

# Check how many times a service has restarted
systemctl show webops-web | grep "NRestarts"
```

### Resetting Failed Services

If a service fails to start and is in "failed" state:

```bash
# Reset the failure count
sudo systemctl reset-failed webops-web

# Then try starting again
sudo systemctl start webops-web
```

---

## Common Issues and Solutions

### Issue: Services Not Running After Installation

**Check if PostgreSQL and Redis are running:**
```bash
systemctl status postgresql
systemctl status redis-server
```

If they're not running:
```bash
sudo systemctl start postgresql
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl enable redis-server
```

Then restart WebOps services:
```bash
sudo systemctl restart webops-web
sudo systemctl restart webops-worker
sudo systemctl restart webops-beat
```

### Issue: Can't Access Port 8000

**Check if the port is listening:**
```bash
sudo ss -tulpn | grep :8000
```

If nothing appears, the web service isn't running. Check logs:
```bash
sudo journalctl -u webops-web -n 100 --no-pager
```

**Check firewall:**
```bash
sudo ufw status
```

If port 8000 is not allowed:
```bash
sudo ufw allow 8000/tcp
```

### Issue: Service Keeps Failing

**View detailed error logs:**
```bash
# View recent logs with errors
sudo journalctl -u webops-web -p err -n 50

# Follow logs in real-time
sudo journalctl -u webops-web -f
```

**Common causes:**
1. Database connection failed (check PostgreSQL is running)
2. Port already in use (check with `ss -tulpn | grep :8000`)
3. Permission issues (check `/var/log/webops/` permissions)
4. Missing environment variables (check `/opt/webops/control-panel/.env`)

### Issue: Auto-Restart Not Working

**Check if systemd service has restart enabled:**
```bash
systemctl show webops-web | grep Restart
```

If `Restart=no`, the service file wasn't installed correctly. Reinstall:
```bash
sudo /opt/webops/provisioning/versions/v1.0.0/bin/webops install
```

**Check if StartLimit was reached:**
```bash
systemctl status webops-web
```

If you see "Start request repeated too quickly", reset it:
```bash
sudo systemctl reset-failed webops-web
sudo systemctl start webops-web
```

---

## Service Management Commands

### Start/Stop/Restart Services

```bash
# Start
sudo systemctl start webops-web
sudo systemctl start webops-worker
sudo systemctl start webops-beat

# Stop
sudo systemctl stop webops-web
sudo systemctl stop webops-worker
sudo systemctl stop webops-beat

# Restart (graceful)
sudo systemctl restart webops-web
sudo systemctl restart webops-worker
sudo systemctl restart webops-beat

# Reload configuration without restart
sudo systemctl reload webops-web
```

### Enable/Disable Auto-Start

```bash
# Enable auto-start on boot
sudo systemctl enable webops-web
sudo systemctl enable webops-worker
sudo systemctl enable webops-beat

# Disable auto-start
sudo systemctl disable webops-web
sudo systemctl disable webops-worker
sudo systemctl disable webops-beat

# Check if enabled
systemctl is-enabled webops-web
```

### View Service Status and Logs

```bash
# View current status
systemctl status webops-web

# View recent logs (last 50 lines)
sudo journalctl -u webops-web -n 50

# Follow logs in real-time
sudo journalctl -u webops-web -f

# View logs from last hour
sudo journalctl -u webops-web --since "1 hour ago"

# View logs with errors only
sudo journalctl -u webops-web -p err

# View all WebOps service logs
sudo journalctl -u "webops-*" -f
```

---

## Verification Checklist

After installation, verify everything is working:

- [ ] PostgreSQL is running: `systemctl status postgresql`
- [ ] Redis is running: `systemctl status redis-server`
- [ ] webops-web is running: `systemctl status webops-web`
- [ ] webops-worker is running: `systemctl status webops-worker`
- [ ] webops-beat is running: `systemctl status webops-beat`
- [ ] Port 8000 is listening: `ss -tulpn | grep :8000`
- [ ] Can access control panel: `curl -I http://localhost:8000`
- [ ] Auto-restart is enabled: `systemctl show webops-web | grep "Restart=always"`
- [ ] Services are enabled on boot: `systemctl is-enabled webops-web`
- [ ] Can retrieve admin credentials: `sudo cat /opt/webops/.secrets/admin_credentials.txt`
- [ ] Can login to control panel in browser

---

## Getting Help

If services still won't start:

1. **Check installation logs:**
   ```bash
   ls -la /var/log/webops/install-*.log
   sudo cat /var/log/webops/install-*.log
   ```

2. **Run the platform validator:**
   ```bash
   sudo /opt/webops/provisioning/versions/v1.0.0/bin/webops validate
   ```

3. **Check system health:**
   ```bash
   sudo /opt/webops/provisioning/versions/v1.0.0/bin/webops state
   ```

4. **Review full service configuration:**
   ```bash
   systemctl cat webops-web
   ```

5. **Check for port conflicts:**
   ```bash
   sudo ss -tulpn | grep :8000
   sudo lsof -i :8000
   ```

---

## Summary

**Development:**
- ❌ Does NOT auto-start after `quickstart.sh`
- ✅ Must manually run `./start_dev.sh` to access server
- 🌐 Access at: http://127.0.0.1:8000

**Production (Updated Behavior):**
- ✅✅ **GUARANTEED to auto-start** - installation fails if services don't start
- ✅ Up to 3 retry attempts per service with 5-second delays
- ✅ Network accessibility verified (0.0.0.0 binding)
- ✅ HTTP connectivity tested before completion
- ✅ Services have `Restart=always` for automatic recovery after crashes
- ✅ Services are enabled for boot auto-start
- 🌐 **Access at:** http://YOUR_SERVER_IP:8000
- 🌐 **Accessible from:** Server itself, LAN, and internet (if firewall allows)

**If installation completed successfully:**
```bash
# Services ARE running and accessible
# Simply access: http://YOUR_SERVER_IP:8000

# View admin credentials
sudo cat /opt/webops/.secrets/admin_credentials.txt
```

**If installation FAILED:**
```bash
# Check the error logs shown during installation
# Fix the underlying issue (PostgreSQL, Redis, ports)
# Re-run the installation - it will not complete until services start successfully
```
