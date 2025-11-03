#!/usr/bin/env python
"""
Test script for Railway-style auto-detection system.

This script demonstrates the auto-detection capabilities without needing
actual repositories.
"""

import os
import sys
import django
from pathlib import Path
import json

# Setup Django
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.deployments.shared.buildpacks import detect_project, ALL_BUILDPACKS

def create_test_repo(repo_path: Path, files: dict):
    """Create a test repository structure."""
    repo_path.mkdir(parents=True, exist_ok=True)

    for file_path, content in files.items():
        full_path = repo_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

def test_nextjs_detection():
    """Test Next.js project detection."""
    print("\n" + "="*60)
    print("TEST 1: Next.js Project")
    print("="*60)

    repo_path = Path("/tmp/test-nextjs")
    repo_path.mkdir(parents=True, exist_ok=True)

    package_json = {
        "name": "my-nextjs-app",
        "version": "1.0.0",
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start"
        },
        "dependencies": {
            "next": "^14.0.0",
            "react": "^18.0.0"
        }
    }

    (repo_path / "package.json").write_text(json.dumps(package_json, indent=2))
    (repo_path / "package-lock.json").touch()

    result = detect_project(str(repo_path))

    print(f"✅ Detected: {result.framework}")
    print(f"📊 Confidence: {result.confidence:.0%}")
    print(f"📦 Package Manager: {result.package_manager}")
    print(f"📥 Install: {result.install_command}")
    print(f"🔨 Build: {result.build_command}")
    print(f"🚀 Start: {result.start_command}")
    print(f"🔌 Port: {result.port}")

    assert result.detected, "Detection failed"
    assert result.framework == "nextjs", f"Expected nextjs, got {result.framework}"
    assert result.confidence >= 0.90, f"Low confidence: {result.confidence}"

def test_fastapi_detection():
    """Test FastAPI project detection."""
    print("\n" + "="*60)
    print("TEST 2: FastAPI Project")
    print("="*60)

    repo_path = Path("/tmp/test-fastapi")
    repo_path.mkdir(parents=True, exist_ok=True)

    requirements = """fastapi==0.104.0
uvicorn[standard]==0.24.0
pydantic==2.5.0"""

    main_py = """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
"""

    (repo_path / "requirements.txt").write_text(requirements)
    (repo_path / "main.py").write_text(main_py)

    result = detect_project(str(repo_path))

    print(f"✅ Detected: {result.framework}")
    print(f"📊 Confidence: {result.confidence:.0%}")
    print(f"📦 Package Manager: {result.package_manager}")
    print(f"📥 Install: {result.install_command}")
    print(f"🔨 Build: {result.build_command}")
    print(f"🚀 Start: {result.start_command}")
    print(f"🔌 Port: {result.port}")

    assert result.detected, "Detection failed"
    assert result.framework == "fastapi", f"Expected fastapi, got {result.framework}"
    assert result.confidence >= 0.85, f"Low confidence: {result.confidence}"

def test_go_detection():
    """Test Go project detection."""
    print("\n" + "="*60)
    print("TEST 3: Go Project")
    print("="*60)

    repo_path = Path("/tmp/test-go")
    repo_path.mkdir(parents=True, exist_ok=True)

    go_mod = """module github.com/user/myapp

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
)
"""

    main_go = """package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
"""

    (repo_path / "go.mod").write_text(go_mod)
    (repo_path / "main.go").write_text(main_go)

    result = detect_project(str(repo_path))

    print(f"✅ Detected: {result.framework}")
    print(f"📊 Confidence: {result.confidence:.0%}")
    print(f"📦 Package Manager: {result.package_manager}")
    print(f"📥 Install: {result.install_command}")
    print(f"🔨 Build: {result.build_command}")
    print(f"🚀 Start: {result.start_command}")
    print(f"🔌 Port: {result.port}")

    assert result.detected, "Detection failed"
    assert result.framework == "go", f"Expected go, got {result.framework}"
    assert result.confidence >= 0.90, f"Low confidence: {result.confidence}"

def test_django_detection():
    """Test Django project detection."""
    print("\n" + "="*60)
    print("TEST 4: Django Project")
    print("="*60)

    repo_path = Path("/tmp/test-django")
    repo_path.mkdir(parents=True, exist_ok=True)

    requirements = """Django==5.0.0
gunicorn==21.2.0
psycopg2-binary==2.9.9"""

    manage_py = """#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
"""

    (repo_path / "requirements.txt").write_text(requirements)
    (repo_path / "manage.py").write_text(manage_py)

    result = detect_project(str(repo_path))

    print(f"✅ Detected: {result.framework}")
    print(f"📊 Confidence: {result.confidence:.0%}")
    print(f"📦 Package Manager: {result.package_manager}")
    print(f"📥 Install: {result.install_command}")
    print(f"🔨 Build: {result.build_command}")
    print(f"🚀 Start: {result.start_command}")
    print(f"🔌 Port: {result.port}")

    assert result.detected, "Detection failed"
    assert result.framework == "django", f"Expected django, got {result.framework}"
    assert result.confidence >= 0.90, f"Low confidence: {result.confidence}"

def test_static_site_detection():
    """Test static site detection (fallback)."""
    print("\n" + "="*60)
    print("TEST 5: Static HTML Site (Fallback)")
    print("="*60)

    repo_path = Path("/tmp/test-static")
    repo_path.mkdir(parents=True, exist_ok=True)

    index_html = """<!DOCTYPE html>
<html>
<head>
    <title>My Site</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>"""

    (repo_path / "index.html").write_text(index_html)

    result = detect_project(str(repo_path))

    print(f"✅ Detected: {result.framework}")
    print(f"📊 Confidence: {result.confidence:.0%}")
    print(f"📦 Package Manager: {result.package_manager}")
    print(f"📥 Install: {result.install_command}")
    print(f"🔨 Build: {result.build_command}")
    print(f"🚀 Start: {result.start_command}")
    print(f"🔌 Port: {result.port}")

    assert result.detected, "Detection failed"
    assert result.framework == "static-html", f"Expected static-html, got {result.framework}"

def show_all_buildpacks():
    """Display all available buildpacks."""
    print("\n" + "="*60)
    print("AVAILABLE BUILDPACKS")
    print("="*60)
    print(f"\nTotal buildpacks: {len(ALL_BUILDPACKS)}")
    print("\nPriority order (highest to lowest):")
    for i, buildpack in enumerate(ALL_BUILDPACKS, 1):
        print(f"  {i}. {buildpack.display_name} ({buildpack.name})")

if __name__ == "__main__":
    print("\n" + "🚀 "*30)
    print("   RAILWAY-STYLE AUTO-DETECTION TEST SUITE")
    print("🚀 "*30)

    show_all_buildpacks()

    try:
        test_nextjs_detection()
        print("✅ Test passed!\n")
    except AssertionError as e:
        print(f"❌ Test failed: {e}\n")

    try:
        test_fastapi_detection()
        print("✅ Test passed!\n")
    except AssertionError as e:
        print(f"❌ Test failed: {e}\n")

    try:
        test_go_detection()
        print("✅ Test passed!\n")
    except AssertionError as e:
        print(f"❌ Test failed: {e}\n")

    try:
        test_django_detection()
        print("✅ Test passed!\n")
    except AssertionError as e:
        print(f"❌ Test failed: {e}\n")

    try:
        test_static_site_detection()
        print("✅ Test passed!\n")
    except AssertionError as e:
        print(f"❌ Test failed: {e}\n")

    print("\n" + "🎉 "*30)
    print("   ALL TESTS COMPLETED")
    print("🎉 "*30 + "\n")
