# 🚀 Railway-Style Auto-Deployment - Complete Implementation

## Overview

WebOps now features a **complete Railway-style auto-deployment system**! Just provide a GitHub URL, and the system automatically detects the project type, configures everything, and deploys. **Zero configuration needed!**

## ✅ What's Been Implemented

### 1. **Buildpack Detection System** (9 Buildpacks)

Located in: `apps/deployments/shared/buildpacks/`

| Buildpack | Detects | Confidence | Example |
|-----------|---------|------------|---------|
| **Docker** | Dockerfile | 100% | Any project with Dockerfile |
| **Django** | manage.py + Django deps | 95% | Django projects |
| **Node.js** | package.json | 90-95% | Next.js, React, Express, etc. |
| **Python** | requirements.txt | 90% | FastAPI, Flask, Streamlit |
| **Go** | go.mod | 95% | Go applications |
| **Rust** | Cargo.toml | 95% | Rust applications |
| **PHP** | composer.json | 85% | Laravel, WordPress |
| **Ruby** | Gemfile | 90% | Rails applications |
| **Static** | index.html | 50% | Fallback for HTML/CSS/JS |

### 2. **Enhanced ApplicationDeployment Model**

New fields added:
```python
auto_detected = BooleanField()           # Was it auto-detected?
detected_framework = CharField()         # e.g., "nextjs", "fastapi"
detected_version = CharField()           # e.g., "3.11", "18.x"
build_command = TextField()              # Auto-generated build command
start_command = TextField()              # Auto-generated start command
install_command = TextField()            # Auto-generated install command
package_manager = CharField()            # e.g., "npm", "pip"
detection_confidence = FloatField()      # 0.0 to 1.0
```

New project types:
- Next.js, React, Vue.js (JavaScript)
- FastAPI, Flask (Python)
- Go, Rust, Ruby (Compiled languages)
- Laravel, WordPress (PHP)

### 3. **Integrated with DeploymentService**

The deployment service now:
1. ✅ Clones repository
2. ✅ **Auto-detects project type using buildpacks**
3. ✅ **Generates install/build/start commands**
4. ✅ Runs install command
5. ✅ Runs build command (if needed)
6. ✅ Configures systemd with auto-detected start command
7. ✅ Deploys!

### 4. **Framework-Specific Detection**

#### Node.js Frameworks
- **Next.js** - Detects `next` in dependencies → `npm run build`, `next start`
- **Nuxt.js** - Detects `nuxt` → Nuxt-specific commands
- **Remix** - Detects `@remix-run/react`
- **SvelteKit** - Detects `@sveltejs/kit`
- **Astro** - Detects `astro`
- **Vite** - Detects `vite` with React/Vue/Svelte
- **Express** - Detects `express`
- **NestJS** - Detects `@nestjs/core`

#### Package Manager Detection
- **npm** (package-lock.json)
- **yarn** (yarn.lock)
- **pnpm** (pnpm-lock.yaml)
- **bun** (bun.lockb)

#### Python Frameworks
- **Django** - With DRF and Channels support
- **FastAPI** - Auto-configures Uvicorn
- **Flask** - Auto-configures Gunicorn
- **Streamlit** - Auto-configures Streamlit server

### 5. **Automatic Command Generation**

Examples of auto-generated configurations:

**Next.js:**
```
Install: npm install
Build: npm run build
Start: npm start
Port: 3000
```

**FastAPI:**
```
Install: pip install -r requirements.txt
Build: (none)
Start: uvicorn main:app --host 0.0.0.0 --port $PORT
Port: 8000
```

**Go:**
```
Install: go mod download
Build: go build -o app
Start: ./app
Port: 8080
```

**Django:**
```
Install: pip install -r requirements.txt
Build: python manage.py collectstatic --noinput
Start: gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT
Port: 8000
```

## 📊 Test Results

All tests passing! ✅

```bash
./venv/bin/python test_auto_detection.py
```

Results:
- ✅ Next.js detection (95% confidence)
- ✅ FastAPI detection (90% confidence)
- ✅ Go detection (95% confidence)
- ✅ Django detection (95% confidence)
- ✅ Static site fallback (50% confidence)

## 🎯 Usage

### Simple Deployment (Railway-style)

```python
from apps.deployments.models import ApplicationDeployment

# Just provide the repo URL!
deployment = ApplicationDeployment.objects.create(
    name="my-nextjs-app",
    repo_url="https://github.com/user/nextjs-app",
    owner=request.user
)

# System automatically:
# 1. Clones repo
# 2. Detects Next.js (95% confidence)
# 3. Generates: npm install, npm run build, npm start
# 4. Allocates port 3000
# 5. Configures systemd service
# 6. Deploys! 🚀
```

### Manual Override (Still Supported)

```python
# You can still manually override if needed
deployment = ApplicationDeployment.objects.create(
    name="my-app",
    repo_url="https://github.com/user/app",
    project_type="django",  # Manual override
    build_command="custom build cmd",  # Custom command
    owner=request.user
)
```

### Detection API

```python
from apps.deployments.shared.buildpacks import detect_project

result = detect_project('/path/to/repo')

print(f"Framework: {result.framework}")
print(f"Build: {result.build_command}")
print(f"Start: {result.start_command}")
print(f"Confidence: {result.confidence}")
```

## 📁 File Structure

```
apps/deployments/
├── shared/
│   └── buildpacks/
│       ├── __init__.py          # Main detection function
│       ├── base.py              # Base classes
│       ├── nodejs.py            # Node.js buildpack
│       ├── django.py            # Django buildpack
│       ├── python.py            # Python buildpack
│       ├── go.py                # Go buildpack
│       ├── rust.py              # Rust buildpack
│       ├── php.py               # PHP buildpack
│       ├── ruby.py              # Ruby buildpack
│       ├── static.py            # Static buildpack
│       └── docker.py            # Docker buildpack
├── models/
│   └── application.py           # Enhanced model with auto-detection fields
├── services/
│   └── application.py           # Updated with buildpack integration
├── migrations/
│   └── 0009_add_auto_detection_fields.py  # Migration
├── AUTO_DETECTION_GUIDE.md      # Detailed guide
└── RAILWAY_STYLE_AUTO_DEPLOYMENT.md  # This file

control-panel/
└── test_auto_detection.py       # Test suite
```

## 🔧 How It Works Internally

### Detection Flow

1. **Repository Cloned** → `DeploymentService.clone_repository()`
2. **Buildpack Detection** → `DeploymentService.detect_with_buildpacks()`
   - Iterates through buildpacks in priority order
   - Each buildpack returns detection result with confidence
   - Highest confidence wins
3. **Configuration Stored** → Updates ApplicationDeployment model
4. **Dependencies Installed** → `DeploymentService._run_install_command()`
5. **Project Built** → `DeploymentService._run_build_command()`
6. **Service Configured** → `DeploymentService.render_systemd_service()`
   - Uses auto-detected start_command
7. **Deployed** → Service starts running!

### Buildpack Priority

Order matters! More specific buildpacks are checked first:

1. **Docker** (explicit Dockerfile)
2. **Django** (more specific than Python)
3. **Node.js** (package.json)
4. **Go** (go.mod)
5. **Rust** (Cargo.toml)
6. **PHP** (composer.json)
7. **Ruby** (Gemfile)
8. **Python** (generic Python)
9. **Static** (fallback)

### Confidence Scoring

- **1.0** - Explicit indicator (Dockerfile)
- **0.95** - Strong indicators (manage.py + Django deps)
- **0.90** - Framework-specific (Next.js dependency)
- **0.85** - Generic framework (Express)
- **0.70** - Loose indicators (React dep)
- **0.50** - Fallback (HTML files found)

## 🚦 Supported Deployment Scenarios

### ✅ Fully Supported (Auto-Deploy)

- **Next.js apps** - Full SSR/SSG support
- **React apps** (CRA, Vite) - Auto-detected and configured
- **Django projects** - Migrations, static files, ASGI/WSGI
- **FastAPI** - Auto-configures Uvicorn
- **Express.js** - Node backend apps
- **Go applications** - Compiled Go binaries
- **Static sites** - HTML/CSS/JS

### ⚠️ Partially Supported (Requires Manual Config)

- **Monorepos** - Can detect but may need path hints
- **Docker Compose** - Detects but uses Dockerfile only
- **Custom build scripts** - May need manual override

### 🔜 Coming Soon

- **.NET/C#** buildpack
- **Java/Spring** buildpack
- **Elixir/Phoenix** buildpack
- **Monorepo** smart detection
- **Multi-service** deployments

## 🎨 Example Logs

When deploying a Next.js app, you'll see:

```
🔍 Auto-detecting project type using buildpacks...
✅ Detected: nextjs (confidence: 95%)
📦 Package Manager: npm
📥 Install: npm install
🔨 Build: npm run build
🚀 Start: npm start
🔌 Port: 3000
Installing dependencies: npm install
Dependencies installed successfully
Building project: npm run build
Project built successfully
Using auto-detected start command: npm start
Deployment prepared successfully
```

## 📈 Benefits

### For Users
- ✅ **Zero Configuration** - Just paste GitHub URL
- ✅ **Instant Deployment** - No manual setup
- ✅ **Best Practices** - Framework-optimized commands
- ✅ **Smart Defaults** - Port, build, start all auto-configured

### For Developers
- ✅ **Extensible** - Easy to add new buildpacks
- ✅ **Testable** - Each buildpack isolated
- ✅ **Maintainable** - Clean separation
- ✅ **Railway-Compatible** - Modern PaaS experience

## 🧪 Testing

### Run Full Test Suite

```bash
cd control-panel
./venv/bin/python test_auto_detection.py
```

### Test Individual Buildpack

```python
from apps.deployments.shared.buildpacks.nodejs import NodeJSBuildpack
from pathlib import Path

buildpack = NodeJSBuildpack()
result = buildpack.detect(Path("/path/to/nextjs-repo"))

print(f"Detected: {result.detected}")
print(f"Framework: {result.framework}")
```

### Manual Deployment Test

```python
# In Django shell
from apps.deployments.models import ApplicationDeployment
from django.contrib.auth.models import User

user = User.objects.first()

deployment = ApplicationDeployment.objects.create(
    name="test-nextjs",
    repo_url="https://github.com/vercel/next.js/tree/canary/examples/hello-world",
    owner=user
)

# Check auto-detection
print(f"Auto-detected: {deployment.auto_detected}")
print(f"Framework: {deployment.detected_framework}")
print(f"Build: {deployment.build_command}")
print(f"Start: {deployment.start_command}")
```

## 🛠️ Extending the System

### Adding a New Buildpack

1. Create `apps/deployments/shared/buildpacks/your_framework.py`:

```python
from pathlib import Path
from .base import Buildpack, BuildpackResult

class YourFrameworkBuildpack(Buildpack):
    name = 'your_framework'
    display_name = 'Your Framework'

    def detect(self, repo_path: Path) -> BuildpackResult:
        # Check for framework-specific files
        if not (repo_path / 'framework.config').exists():
            return BuildpackResult(detected=False, ...)

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='your_framework',
            confidence=0.95,
            framework='your_framework',
            build_command='your-build-cmd',
            start_command='your-start-cmd',
            install_command='your-install-cmd',
            ...
        )
```

2. Add to `__init__.py`:

```python
from .your_framework import YourFrameworkBuildpack

ALL_BUILDPACKS = [
    DockerBuildpack(),
    YourFrameworkBuildpack(),  # Add here
    DjangoBuildpack(),
    # ... rest
]
```

3. Add project type to model choices in `models/application.py`

4. Test it!

## 📚 Documentation

- **Full Guide**: `AUTO_DETECTION_GUIDE.md`
- **Test Suite**: `test_auto_detection.py`
- **Buildpack Docs**: See individual buildpack files

## 🎯 Comparison with Railway

| Feature | WebOps | Railway |
|---------|--------|---------|
| Auto-detection | ✅ | ✅ |
| Buildpacks | ✅ 9 buildpacks | ✅ Similar |
| Zero-config | ✅ | ✅ |
| Manual override | ✅ | ✅ |
| Self-hosted | ✅ | ❌ |
| Open source | ✅ | ❌ |
| Custom buildpacks | ✅ Easy to add | ⚠️ Limited |

## 🚀 Getting Started

1. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

2. **Test the system:**
   ```bash
   python test_auto_detection.py
   ```

3. **Deploy something:**
   ```python
   deployment = ApplicationDeployment.objects.create(
       name="my-app",
       repo_url="https://github.com/user/nextjs-app",
       owner=request.user
   )
   ```

4. **Watch the magic happen!** 🪄

---

**Built with ❤️ to provide a Railway-like deployment experience!**

*WebOps - Zero-configuration deployments for everyone.*
