# Docker Addon - Quick Start Guide

## What You Need to Know

The Docker addon was not showing up because WebOps' addon system requires **YAML manifest files** (`.yaml` or `.yml`), not JSON.

**✅ Fixed:** Created `addon.yaml` instead of `addon.json`

## Files in Place

```
control-panel/addons/docker/
├── addon.yaml          ← YAML manifest (REQUIRED for discovery)
├── docker_service.py   ← Docker operations (build, run, manage containers)
├── hooks.py            ← Integration hooks (pre/post deployment, health checks)
├── __init__.py         ← Package initialization
└── README.md           ← Comprehensive documentation
```

## Activation Checklist

### 1. Verify Files Exist
```bash
ls -la control-panel/addons/docker/
# Should show: addon.yaml, docker_service.py, hooks.py, __init__.py, README.md
```

### 2. Run Verification Script (Optional but Recommended)
```bash
python verify_docker_addon.py
```

This checks:
- ✓ Addon directory structure
- ✓ YAML manifest format
- ✓ Discovery system can find the addon
- ✓ Hook handlers are defined

### 3. Run Database Migration
```bash
cd control-panel
python manage.py migrate
```

This adds Docker-related fields to the Deployment model.

### 4. Restart WebOps

**Development:**
```bash
# Stop current runserver (Ctrl+C)
python manage.py runserver
```

**Production:**
```bash
sudo systemctl restart webops-control-panel
```

### 5. Verify Addon is Loaded

**Check logs:**
Look for: `Addons discovered and hooks registered at startup.`

**Check database:**
```bash
python manage.py shell
```

```python
from apps.addons.models import Addon

# Check if Docker addon exists
docker_addon = Addon.objects.get(name='docker')
print(f"{docker_addon.name} v{docker_addon.version} - Enabled: {docker_addon.enabled}")
# Output: docker v1.0.0 - Enabled: True
```

**Check hook registry:**
```python
from apps.addons.registry import hook_registry

# Check registered hooks
pre_hooks = hook_registry.get_hooks('pre_deployment')
docker_pre = [h for h in pre_hooks if h.addon_name == 'docker']
print(f"Docker pre-deployment hooks: {len(docker_pre)}")
# Output: Docker pre-deployment hooks: 1
```

## Using the Docker Addon

### Create a Docker Deployment

1. **Navigate to WebOps dashboard**
2. **Click "New Deployment"**
3. **Fill in standard fields:**
   - Name: `my-dockerized-app`
   - Repository URL: `https://github.com/user/repo`
   - Branch: `main`

4. **Enable Docker:**
   - ✅ Check "Use Docker containerization"
   - ✅ Check "Auto-generate Dockerfile if not present" (recommended)
   - Select Network Mode: `Bridge` (default)
   - Dockerfile Path: `Dockerfile` (default)

5. **Click "Create Deployment"**

### What Happens Next

1. **Pre-deployment:**
   - Checks if Docker is installed
   - Generates Dockerfile if needed
   - Validates Dockerfile exists

2. **Deployment:**
   - Clones repository
   - Builds Docker image: `webops/my-dockerized-app:latest`
   - Creates container: `webops-my-dockerized-app`
   - Starts container on allocated port

3. **Monitoring:**
   - Health checks monitor container status
   - Container logs available in deployment logs
   - Start/stop/restart via WebOps UI

## Docker Requirements

### On the Server

1. **Docker Engine installed:**
   ```bash
   docker --version
   # Should show: Docker version 20.10.0 or higher
   ```

2. **User has Docker permissions:**
   ```bash
   docker ps
   # Should NOT show permission denied
   ```

   If permission denied:
   ```bash
   sudo usermod -aG docker $USER
   # Then logout and login again
   ```

3. **Docker service running:**
   ```bash
   sudo systemctl status docker
   # Should show: active (running)
   ```

## Troubleshooting

### Addon Not Appearing

**Problem:** Docker addon not in database after restart

**Solution:**
1. Check `addon.yaml` exists (not `addon.json`)
2. Verify YAML syntax is valid:
   ```bash
   python -c "import yaml; yaml.safe_load(open('control-panel/addons/docker/addon.yaml'))"
   ```
3. Check WebOps logs for errors
4. Ensure `ADDONS_PATH` points to correct directory

### Hooks Not Executing

**Problem:** Docker builds not happening during deployment

**Solution:**
1. Check deployment has `use_docker=True`
2. Verify hooks registered:
   ```python
   from apps.addons.registry import hook_registry
   hook_registry.get_hooks('post_deployment')
   ```
3. Check deployment logs for error messages

### Docker Build Fails

**Problem:** "Docker is not available" error

**Solution:**
1. Install Docker: `sudo apt-get install docker.io`
2. Start Docker: `sudo systemctl start docker`
3. Add permissions: `sudo usermod -aG docker $USER`

### Container Won't Start

**Problem:** Container created but not running

**Solution:**
1. Check container logs:
   ```bash
   docker logs webops-{deployment-name}
   ```
2. Verify Dockerfile is correct
3. Check port not already in use:
   ```bash
   netstat -tuln | grep {port}
   ```

## Quick Reference

### Docker Addon Files
```
control-panel/addons/docker/addon.yaml    ← Manifest (REQUIRED)
control-panel/addons/docker/hooks.py      ← Hook handlers
```

### Database Models
```
Deployment.use_docker                  ← Enable Docker (Boolean)
Deployment.auto_generate_dockerfile    ← Auto-gen Dockerfile (Boolean)
Deployment.dockerfile_path             ← Path to Dockerfile (String)
Deployment.docker_image_name           ← Image name (String)
Deployment.docker_network_mode         ← Network mode (String)
Deployment.docker_env_vars             ← Env vars (JSON)
Deployment.docker_volumes              ← Volumes (JSON)
Deployment.docker_ports                ← Ports (JSON)
```

### Hooks
```
pre_deployment       ← Validate Docker, generate Dockerfile
post_deployment      ← Build image, create container
service_health_check ← Monitor container status
```

### Docker Resources Created
```
Image:     webops/{deployment-name}:latest
Container: webops-{deployment-name}
Network:   bridge (default) or custom
```

## Next Steps

1. ✅ Verify addon files in place
2. ✅ Run migration
3. ✅ Restart WebOps
4. ✅ Check addon loaded
5. 🚀 Create your first Docker deployment!

## Documentation

- **Full Implementation Guide:** `DOCKER_ADDON_SUMMARY.md`
- **Discovery Fix Details:** `ADDON_DISCOVERY_FIX.md`
- **User Guide:** `control-panel/addons/docker/README.md`
- **Verification Script:** `verify_docker_addon.py`

## Support

If issues persist:
1. Check WebOps logs: `control-panel/logs/webops.log`
2. Run verification script: `python verify_docker_addon.py`
3. Review deployment logs in WebOps UI
4. Check Docker daemon: `sudo journalctl -u docker`

---

**The Docker addon is ready to use!** Just restart WebOps and start deploying containerized applications. 🐳
