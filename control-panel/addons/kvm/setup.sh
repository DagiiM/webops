#!/bin/bash
# KVM Addon Setup Script for WebOps

set -e

echo "========================================"
echo "WebOps KVM Addon Setup"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

echo "Step 1: Checking KVM support..."
if grep -E -q '(vmx|svm)' /proc/cpuinfo; then
    echo -e "${GREEN}✓ CPU supports virtualization${NC}"
else
    echo -e "${RED}✗ CPU does not support virtualization${NC}"
    echo "This system cannot run KVM VMs"
    exit 1
fi

echo ""
echo "Step 2: Installing system dependencies..."
apt-get update -qq
apt-get install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    bridge-utils \
    genisoimage \
    libguestfs-tools \
    python3-libvirt \
    > /dev/null 2>&1

echo -e "${GREEN}✓ System packages installed${NC}"

echo ""
echo "Step 3: Enabling libvirt service..."
systemctl enable libvirtd
systemctl start libvirtd
echo -e "${GREEN}✓ Libvirt service started${NC}"

echo ""
echo "Step 4: Creating storage directories..."
mkdir -p /var/lib/webops/vms
mkdir -p /var/lib/webops/templates
chmod 755 /var/lib/webops/vms
chmod 755 /var/lib/webops/templates
echo -e "${GREEN}✓ Storage directories created${NC}"

echo ""
echo "Step 5: Configuring permissions..."
# Add webops user to libvirt group (if exists)
if id "webops" &>/dev/null; then
    usermod -aG libvirt webops
    echo -e "${GREEN}✓ Added webops user to libvirt group${NC}"
else
    echo -e "${YELLOW}! webops user not found, skipping group assignment${NC}"
fi

echo ""
echo "Step 6: Testing libvirt connection..."
if virsh list --all > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Libvirt connection successful${NC}"
else
    echo -e "${RED}✗ Libvirt connection failed${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo -e "${GREEN}KVM Addon System Setup Complete!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Install Python dependencies:"
echo "   pip install -r addons/kvm/requirements.txt"
echo ""
echo "2. Run Django migrations:"
echo "   python manage.py migrate"
echo ""
echo "3. Initialize KVM addon:"
echo "   python manage.py init_kvm --create-defaults"
echo ""
echo "4. Add a compute node:"
echo "   python manage.py add_compute_node localhost --vcpus <N> --memory-mb <N> --disk-gb <N>"
echo ""
echo "5. Download OS templates:"
echo "   cd /var/lib/webops/templates"
echo "   wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
echo ""
echo "See addons/kvm/README.md for full documentation."
