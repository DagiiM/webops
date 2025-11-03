# Railway-Style Auto-Detection System

## Overview

WebOps now features a comprehensive auto-detection system similar to Railway, Heroku, and other modern PaaS platforms. **Just provide a GitHub repo URL, and WebOps automatically detects the project type and configures everything needed for deployment.**

## Supported Frameworks

### Python
- **Django** - Full Django projects with auto-detected settings modules
- **FastAPI** - Modern async Python web framework
- **Flask** - Lightweight Python web framework
- **Streamlit** - Data apps and dashboards
- Generic Python applications

### JavaScript/TypeScript
- **Next.js** - React framework with SSR
- **Nuxt.js** - Vue framework with SSR
- **Remix** - Full-stack React framework
- **SvelteKit** - Svelte application framework
- **Astro** - Content-focused framework
- **Vite** - Lightning-fast build tool (React, Vue, Svelte)
- **Create React App** - React starter
- **Express.js** - Node.js web framework
- **NestJS** - Progressive Node.js framework
- **Fastify** - Fast Node.js framework
- Generic Node.js applications

### Other Languages
- **Go** - Go applications with go.mod
- **Rust** - Rust applications with Cargo.toml
- **PHP** - PHP applications
- **Laravel** - PHP framework
- **WordPress** - CMS platform
- **Ruby/Rails** - Ruby applications

### Special
- **Docker** - Projects with Dockerfile (highest priority)
- **Static Sites** - HTML/CSS/JS (fallback)

## How It Works

### 1. Buildpack Detection

The system uses a buildpack-style detection system inspired by Heroku and Railway:

```python
from apps.deployments.shared.buildpacks import detect_project

# Auto-detect project type
result = detect_project('/path/to/repo')

print(f"Detected: {result.framework}")
print(f"Build: {result.build_command}")
print(f"Start: {result.start_command}")
```

### 2. Priority Order

Buildpacks are checked in this order (most specific first):

1. **Docker** - If `Dockerfile` exists, use it
2. **Django** - More specific than generic Python
3. **Node.js** - Checks `package.json`
4. **Go** - Checks `go.mod`
5. **Rust** - Checks `Cargo.toml`
6. **PHP** - Checks `composer.json` or `*.php` files
7. **Ruby** - Checks `Gemfile`
8. **Python** - Generic Python (FastAPI, Flask, etc.)
9. **Static** - Fallback for HTML/CSS/JS

### 3. Auto-Generated Configuration

For each detected framework, the system automatically configures:

- ✅ **Build Command** - How to build the project
- ✅ **Start Command** - How to run the application
- ✅ **Install Command** - How to install dependencies
- ✅ **Environment Variables** - Required env vars
- ✅ **Port** - Default port for the framework
- ✅ **Package Manager** - npm, yarn, pnpm, pip, poetry, etc.

## Usage Examples

### Example 1: Next.js Application

**Repository:** `https://github.com/user/nextjs-app`

**Auto-Detected Configuration:**
```python
{
    "project_type": "nodejs",
    "framework": "nextjs",
    "build_command": "npm run build",
    "start_command": "npm start",
    "install_command": "npm install",
    "package_manager": "npm",
    "port": 3000,
    "env_vars": {
        "NODE_ENV": "production"
    }
}
```

### Example 2: Django Project

**Repository:** `https://github.com/user/django-blog`

**Auto-Detected Configuration:**
```python
{
    "project_type": "django",
    "framework": "django",
    "build_command": "python manage.py collectstatic --noinput",
    "start_command": "gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT --workers 4",
    "install_command": "pip install -r requirements.txt",
    "package_manager": "pip",
    "port": 8000,
    "env_vars": {
        "DJANGO_SETTINGS_MODULE": "myproject.settings",
        "PYTHONUNBUFFERED": "1"
    }
}
```

### Example 3: FastAPI Application

**Repository:** `https://github.com/user/fastapi-api`

**Auto-Detected Configuration:**
```python
{
    "project_type": "python",
    "framework": "fastapi",
    "build_command": "",
    "start_command": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "install_command": "pip install -r requirements.txt",
    "package_manager": "pip",
    "port": 8000,
    "env_vars": {
        "PYTHONUNBUFFERED": "1"
    }
}
```

### Example 4: Go Application

**Repository:** `https://github.com/user/go-server`

**Auto-Detected Configuration:**
```python
{
    "project_type": "go",
    "framework": "go",
    "build_command": "go build -o app",
    "start_command": "./app",
    "install_command": "go mod download",
    "package_manager": "go",
    "port": 8080,
    "env_vars": {}
}
```

## Deployment Flow

### With Auto-Detection (NEW - Railway Style)

```python
# 1. User provides just the repo URL
deployment = ApplicationDeployment.objects.create(
    name="my-app",
    repo_url="https://github.com/user/my-nextjs-app",
    owner=user
)

# 2. System automatically detects everything
# - Clones repository
# - Runs buildpack detection
# - Configures build/start commands
# - Sets environment variables
# - Allocates port
# - Deploys!

# 3. Result: Fully deployed application!
```

### Manual Override (Still Supported)

```python
# Users can still manually specify project type if needed
deployment = ApplicationDeployment.objects.create(
    name="my-app",
    repo_url="https://github.com/user/my-app",
    project_type="django",  # Manual override
    owner=user
)
```

## Detection Confidence

Each detection includes a confidence score (0.0 to 1.0):

- **1.0** - Explicit (e.g., Dockerfile present)
- **0.95** - Very confident (e.g., Django with manage.py)
- **0.90** - Confident (e.g., Next.js with next dependency)
- **0.70-0.85** - Likely (e.g., generic framework indicators)
- **0.50-0.60** - Fallback (e.g., static HTML files found)

The system always chooses the buildpack with the highest confidence.

## Model Fields

New fields on `ApplicationDeployment`:

```python
class ApplicationDeployment(BaseDeployment):
    # Original fields
    project_type = models.CharField(...)  # Now has more choices
    repo_url = models.URLField(...)
    branch = models.CharField(...)

    # NEW: Auto-detection fields
    auto_detected = models.BooleanField(default=False)
    detected_framework = models.CharField(...)  # e.g., "nextjs", "fastapi"
    detected_version = models.CharField(...)    # e.g., "3.11", "18.x"
    build_command = models.TextField(...)       # Auto-generated
    start_command = models.TextField(...)       # Auto-generated
    install_command = models.TextField(...)     # Auto-generated
    package_manager = models.CharField(...)     # e.g., "npm", "pip"
    detection_confidence = models.FloatField(...)  # 0.0 to 1.0
```

## Framework-Specific Features

### Node.js

**Detected Package Managers:**
- npm (package-lock.json)
- yarn (yarn.lock)
- pnpm (pnpm-lock.yaml)
- bun (bun.lockb)

**Detected Frameworks:**
- Next.js, Nuxt.js, Remix, SvelteKit
- Astro, Vite (React/Vue/Svelte)
- Express, NestJS, Fastify

### Python

**Detected Package Managers:**
- pip (requirements.txt)
- poetry (poetry.lock)
- pipenv (Pipfile.lock)

**Detected Frameworks:**
- Django (with DRF and Channels support)
- FastAPI, Flask, Streamlit

### Go

**Auto-Detects:**
- Module name from go.mod
- Go version from go.mod
- Main package location

### PHP

**Detected Frameworks:**
- Laravel (artisan file)
- WordPress (wp-config.php)
- Generic PHP with Composer

## Benefits

### For Users
✅ **Zero Configuration** - Just paste a GitHub URL
✅ **Instant Deployment** - No manual setup required
✅ **Best Practices** - Auto-configured for each framework
✅ **Smart Defaults** - Optimized build and start commands

### For Developers
✅ **Extensible** - Easy to add new buildpacks
✅ **Testable** - Each buildpack is independent
✅ **Maintainable** - Clean separation of concerns
✅ **Railway-Compatible** - Similar to modern PaaS platforms

## Next Steps

1. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

2. **Try it out:**
   ```python
   from apps.deployments.shared.buildpacks import detect_project

   result = detect_project('/path/to/your/repo')
   print(f"Detected: {result.framework}")
   ```

3. **Deploy automatically:**
   ```python
   deployment = ApplicationDeployment.objects.create(
       name="auto-app",
       repo_url="https://github.com/user/nextjs-app",
       owner=request.user
   )
   # System handles the rest!
   ```

## Contributing

To add a new framework/language:

1. Create a new buildpack in `apps/deployments/shared/buildpacks/`
2. Inherit from `Buildpack` base class
3. Implement the `detect()` method
4. Add to `ALL_BUILDPACKS` list in `__init__.py`
5. Write tests!

## Documentation

- See individual buildpack files for detection logic
- See `base.py` for the buildpack interface
- See `BuildpackResult` dataclass for return format

---

**Made with ❤️ to provide a Railway-like deployment experience!**
