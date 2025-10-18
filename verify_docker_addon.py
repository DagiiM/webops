#!/usr/bin/env python
"""
Quick verification script to check if Docker addon will be discovered.

Run this from the control-panel directory:
    python ../verify_docker_addon.py
"""

import os
import sys
from pathlib import Path

# Setup Django environment
sys.path.insert(0, str(Path(__file__).parent / 'control-panel'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.addons.loader import discover_addons, DEFAULT_ADDONS_PATH
from apps.addons.models import Addon
from apps.addons.registry import hook_registry

def main():
    print("=" * 70)
    print("Docker Addon Verification Script")
    print("=" * 70)
    print()

    # 1. Check addons directory
    print("1. Checking addons directory...")
    addons_path = DEFAULT_ADDONS_PATH
    print(f"   ADDONS_PATH: {addons_path}")

    if os.path.isdir(addons_path):
        print(f"   ✓ Directory exists")

        docker_addon_path = os.path.join(addons_path, 'docker')
        if os.path.isdir(docker_addon_path):
            print(f"   ✓ Docker addon directory exists")

            # Check for YAML manifest
            yaml_files = [f for f in os.listdir(docker_addon_path) if f.endswith(('.yaml', '.yml'))]
            if yaml_files:
                print(f"   ✓ Found YAML manifest(s): {', '.join(yaml_files)}")
            else:
                print(f"   ✗ No YAML manifest found!")
                print(f"     Expected: addon.yaml or addon.yml")
                return False

            # Check for hooks.py
            hooks_file = os.path.join(docker_addon_path, 'hooks.py')
            if os.path.isfile(hooks_file):
                print(f"   ✓ hooks.py exists")
            else:
                print(f"   ✗ hooks.py not found!")
                return False
        else:
            print(f"   ✗ Docker addon directory not found at {docker_addon_path}")
            return False
    else:
        print(f"   ✗ Addons directory not found!")
        return False

    print()

    # 2. Test discovery
    print("2. Testing addon discovery...")
    try:
        discovered = discover_addons(addons_path)
        print(f"   Discovered {len(discovered)} addon(s)")

        docker_found = False
        for addon in discovered:
            addon_name = addon['metadata'].get('name')
            print(f"   - {addon_name} v{addon['metadata'].get('version')}")
            if addon_name == 'docker':
                docker_found = True
                print(f"     Description: {addon['metadata'].get('description')}")
                print(f"     Hooks: {', '.join(addon['hooks'].keys())}")

        if not docker_found:
            print(f"   ✗ Docker addon not discovered!")
            return False
        else:
            print(f"   ✓ Docker addon discovered successfully!")
    except Exception as e:
        print(f"   ✗ Error during discovery: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # 3. Check database
    print("3. Checking database for Docker addon...")
    try:
        docker_addon = Addon.objects.filter(name='docker').first()
        if docker_addon:
            print(f"   ✓ Docker addon found in database")
            print(f"     Name: {docker_addon.name}")
            print(f"     Version: {docker_addon.version}")
            print(f"     Enabled: {docker_addon.enabled}")
            print(f"     Created: {docker_addon.created_at}")
        else:
            print(f"   ⚠ Docker addon not in database yet")
            print(f"     This is normal if WebOps hasn't been restarted since addon creation")
            print(f"     It will be created on next startup")
    except Exception as e:
        print(f"   ⚠ Error checking database: {e}")

    print()

    # 4. Check hook registry
    print("4. Checking hook registry...")
    try:
        all_hooks = ['pre_deployment', 'post_deployment', 'service_health_check']
        docker_hooks_found = []

        for event in all_hooks:
            hooks = hook_registry.get_hooks(event)
            docker_event_hooks = [h for h in hooks if h.addon_name == 'docker']
            if docker_event_hooks:
                docker_hooks_found.append(event)
                print(f"   ✓ {event}: {len(docker_event_hooks)} Docker hook(s) registered")

        if not docker_hooks_found:
            print(f"   ⚠ No Docker hooks in registry yet")
            print(f"     This is normal if WebOps hasn't been restarted since addon creation")
            print(f"     Hooks will be registered on next startup")
        else:
            print(f"   ✓ Docker hooks are registered!")
    except Exception as e:
        print(f"   ⚠ Error checking registry: {e}")

    print()
    print("=" * 70)
    print("Verification Summary")
    print("=" * 70)
    print()
    print("✓ Docker addon files are in place")
    print("✓ Addon manifest is properly formatted (YAML)")
    print("✓ Addon can be discovered by WebOps")
    print()
    print("Next steps:")
    print("1. Restart WebOps to trigger addon discovery:")
    print("   - Development: Restart `python manage.py runserver`")
    print("   - Production: `sudo systemctl restart webops-control-panel`")
    print()
    print("2. Verify addon appears in WebOps admin or logs:")
    print("   - Check logs for: 'Addons discovered and hooks registered'")
    print("   - Or run: python manage.py shell")
    print("     >>> from apps.addons.models import Addon")
    print("     >>> Addon.objects.get(name='docker')")
    print()
    print("3. Create a deployment with Docker enabled!")
    print()

    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
