"""
KVM Addon Models

Extends WebOps with virtual machine deployment capabilities.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
from decimal import Decimal

User = get_user_model()


class ComputeNode(BaseModel):
    """
    Represents a physical bare metal server capable of running VMs.
    """
    hostname = models.CharField(
        max_length=255,
        unique=True,
        help_text="Hostname or IP address of the compute node"
    )
    total_vcpus = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total physical CPU cores"
    )
    total_memory_mb = models.IntegerField(
        validators=[MinValueValidator(512)],
        help_text="Total RAM in megabytes"
    )
    total_disk_gb = models.IntegerField(
        validators=[MinValueValidator(10)],
        help_text="Total disk space in gigabytes"
    )

    # Overcommit ratios
    cpu_overcommit_ratio = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(10.0)],
        help_text="CPU overcommit ratio (2.0 = 2:1)"
    )
    memory_overcommit_ratio = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(2.0)],
        help_text="Memory overcommit ratio (1.0 = no overcommit)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this node is available for new deployments"
    )

    # Connection details
    libvirt_uri = models.CharField(
        max_length=255,
        default="qemu:///system",
        help_text="Libvirt connection URI"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Compute Node"
        verbose_name_plural = "Compute Nodes"

    def __str__(self):
        return f"{self.hostname} ({'active' if self.is_active else 'inactive'})"

    def available_vcpus(self) -> int:
        """Calculate available vCPUs considering overcommit."""
        from django.db.models import Sum
        allocated = VMDeployment.objects.filter(
            compute_node=self,
            deployment__status__in=['running', 'deploying']
        ).aggregate(Sum('vcpus'))['vcpus__sum'] or 0

        max_vcpus = int(self.total_vcpus * self.cpu_overcommit_ratio)
        return max(0, max_vcpus - allocated)

    def available_memory_mb(self) -> int:
        """Calculate available memory considering overcommit."""
        from django.db.models import Sum
        allocated = VMDeployment.objects.filter(
            compute_node=self,
            deployment__status__in=['running', 'deploying']
        ).aggregate(Sum('memory_mb'))['memory_mb__sum'] or 0

        max_memory = int(self.total_memory_mb * self.memory_overcommit_ratio)
        return max(0, max_memory - allocated)

    def available_disk_gb(self) -> int:
        """Calculate available disk space."""
        from django.db.models import Sum
        allocated = VMDeployment.objects.filter(
            compute_node=self,
            deployment__status__in=['running', 'deploying', 'stopped']
        ).aggregate(Sum('disk_gb'))['disk_gb__sum'] or 0

        return max(0, self.total_disk_gb - allocated)

    def can_fit_plan(self, plan: 'VMPlan') -> bool:
        """Check if this node has resources for a VM plan."""
        return (
            self.available_vcpus() >= plan.vcpus and
            self.available_memory_mb() >= plan.memory_mb and
            self.available_disk_gb() >= plan.disk_gb
        )


class VMPlan(BaseModel):
    """
    Pre-defined VM resource plans (similar to AWS EC2 instance types).
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Plan identifier (e.g., 'small', 'medium', 'large')"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable name"
    )
    description = models.TextField(
        blank=True,
        help_text="Plan description for users"
    )

    # Resources
    vcpus = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(64)],
        help_text="Number of virtual CPUs"
    )
    memory_mb = models.IntegerField(
        validators=[MinValueValidator(512)],
        help_text="RAM in megabytes"
    )
    disk_gb = models.IntegerField(
        validators=[MinValueValidator(10)],
        help_text="Disk space in gigabytes"
    )

    # Pricing
    hourly_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Price per hour in USD"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is available for new VMs"
    )

    # Display order
    sort_order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers first)"
    )

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = "VM Plan"
        verbose_name_plural = "VM Plans"

    def __str__(self):
        return f"{self.display_name} ({self.vcpus}vCPU, {self.memory_mb}MB RAM, {self.disk_gb}GB disk)"

    @property
    def memory_gb(self) -> float:
        """Memory in GB for display."""
        return self.memory_mb / 1024


class OSTemplate(BaseModel):
    """
    Operating system templates for VM provisioning.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Template identifier (e.g., 'ubuntu-22.04')"
    )
    display_name = models.CharField(
        max_length=150,
        help_text="Human-readable name (e.g., 'Ubuntu 22.04 LTS')"
    )
    description = models.TextField(
        blank=True,
        help_text="Template description"
    )

    os_family = models.CharField(
        max_length=50,
        choices=[
            ('ubuntu', 'Ubuntu'),
            ('debian', 'Debian'),
            ('centos', 'CentOS'),
            ('rocky', 'Rocky Linux'),
            ('fedora', 'Fedora'),
            ('arch', 'Arch Linux'),
        ],
        help_text="Operating system family"
    )

    os_version = models.CharField(
        max_length=50,
        help_text="OS version (e.g., '22.04', '12')"
    )

    # Storage
    image_path = models.CharField(
        max_length=500,
        help_text="Path to the qcow2 template image"
    )
    image_size_gb = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Template image size in GB"
    )

    # Cloud-init support
    supports_cloud_init = models.BooleanField(
        default=True,
        help_text="Whether this template supports cloud-init"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is available for use"
    )

    sort_order = models.IntegerField(
        default=0,
        help_text="Display order"
    )

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = "OS Template"
        verbose_name_plural = "OS Templates"

    def __str__(self):
        return self.display_name


class VMDeployment(BaseModel):
    """
    Virtual machine deployment details.
    Links a Deployment record to KVM-specific configuration.
    """
    deployment = models.OneToOneField(
        'deployments.Deployment',
        on_delete=models.CASCADE,
        related_name='kvm_deployment'
    )

    compute_node = models.ForeignKey(
        ComputeNode,
        on_delete=models.PROTECT,
        related_name='vm_deployments'
    )

    vm_plan = models.ForeignKey(
        VMPlan,
        on_delete=models.PROTECT,
        related_name='deployments'
    )

    os_template = models.ForeignKey(
        OSTemplate,
        on_delete=models.PROTECT,
        related_name='deployments'
    )

    # VM identifiers
    vm_uuid = models.CharField(
        max_length=36,
        unique=True,
        null=True,
        blank=True,
        help_text="Libvirt domain UUID"
    )
    vm_name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Libvirt domain name (e.g., 'webops-vm-123')"
    )

    # Resources (copied from plan at creation time)
    vcpus = models.IntegerField()
    memory_mb = models.IntegerField()
    disk_gb = models.IntegerField()

    # Networking
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="VM's internal IP address"
    )
    mac_address = models.CharField(
        max_length=17,
        null=True,
        blank=True,
        help_text="VM's MAC address"
    )
    ssh_port = models.IntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="External SSH port (NAT forwarding)"
    )
    vnc_port = models.IntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="VNC port for console access"
    )

    # Storage
    disk_path = models.CharField(
        max_length=500,
        help_text="Path to VM disk image"
    )

    # Access credentials
    root_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="Encrypted root/admin password"
    )
    ssh_public_keys = models.JSONField(
        default=list,
        help_text="List of authorized SSH public keys"
    )

    # State
    libvirt_state = models.CharField(
        max_length=20,
        default='undefined',
        help_text="Current libvirt domain state"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "VM Deployment"
        verbose_name_plural = "VM Deployments"

    def __str__(self):
        return f"{self.vm_name} on {self.compute_node.hostname}"

    def get_ssh_command(self) -> str:
        """Generate SSH command for user."""
        if self.ssh_port:
            return f"ssh -p {self.ssh_port} root@{self.compute_node.hostname}"
        return f"ssh root@{self.ip_address or 'pending'}"


class VMSnapshot(BaseModel):
    """
    VM disk snapshots for backups and rollbacks.
    """
    vm_deployment = models.ForeignKey(
        VMDeployment,
        on_delete=models.CASCADE,
        related_name='snapshots'
    )

    name = models.CharField(
        max_length=100,
        help_text="Snapshot name"
    )
    description = models.TextField(
        blank=True,
        help_text="Snapshot description"
    )

    # Libvirt snapshot metadata
    snapshot_xml = models.TextField(
        help_text="Libvirt snapshot XML definition"
    )

    disk_size_mb = models.IntegerField(
        help_text="Snapshot size in megabytes"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this snapshot is available for restoration"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "VM Snapshot"
        verbose_name_plural = "VM Snapshots"
        unique_together = [['vm_deployment', 'name']]

    def __str__(self):
        return f"{self.vm_deployment.vm_name} - {self.name}"


class VMUsageRecord(BaseModel):
    """
    Hourly VM usage tracking for billing and metering.
    """
    vm_deployment = models.ForeignKey(
        VMDeployment,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )

    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Record timestamp"
    )

    # Resource snapshot
    vcpus = models.IntegerField()
    memory_mb = models.IntegerField()
    disk_gb = models.IntegerField()

    # State
    state = models.CharField(
        max_length=20,
        help_text="VM state during this period"
    )
    uptime_seconds = models.IntegerField(
        default=3600,
        help_text="Uptime during this hour"
    )

    # Billing
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Hourly rate applied"
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Cost for this period"
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "VM Usage Record"
        verbose_name_plural = "VM Usage Records"
        indexes = [
            models.Index(fields=['vm_deployment', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.vm_deployment.vm_name} - {self.timestamp} ({self.state})"


class VMQuota(BaseModel):
    """
    Per-user resource quotas for VM deployments.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='vm_quota'
    )

    # VM limits
    max_vms = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Maximum number of VMs"
    )

    # Resource limits
    max_vcpus = models.IntegerField(
        default=16,
        validators=[MinValueValidator(0)],
        help_text="Maximum total vCPUs across all VMs"
    )
    max_memory_mb = models.IntegerField(
        default=32768,  # 32GB
        validators=[MinValueValidator(0)],
        help_text="Maximum total RAM in megabytes"
    )
    max_disk_gb = models.IntegerField(
        default=500,
        validators=[MinValueValidator(0)],
        help_text="Maximum total disk space in gigabytes"
    )

    class Meta:
        verbose_name = "VM Quota"
        verbose_name_plural = "VM Quotas"

    def __str__(self):
        return f"Quota for {self.user.username}"

    def check_can_create(self, plan: VMPlan) -> tuple[bool, str]:
        """Check if user can create a VM with given plan."""
        from django.db.models import Sum, Count

        user_vms = VMDeployment.objects.filter(
            deployment__user=self.user,
            deployment__status__in=['running', 'deploying', 'stopped']
        )

        # Count VMs
        vm_count = user_vms.count()
        if vm_count >= self.max_vms:
            return False, f"VM limit reached ({self.max_vms} VMs)"

        # Check vCPUs
        total_vcpus = user_vms.aggregate(Sum('vcpus'))['vcpus__sum'] or 0
        if total_vcpus + plan.vcpus > self.max_vcpus:
            return False, f"vCPU limit exceeded ({self.max_vcpus} max)"

        # Check memory
        total_memory = user_vms.aggregate(Sum('memory_mb'))['memory_mb__sum'] or 0
        if total_memory + plan.memory_mb > self.max_memory_mb:
            return False, f"Memory limit exceeded ({self.max_memory_mb}MB max)"

        # Check disk
        total_disk = user_vms.aggregate(Sum('disk_gb'))['disk_gb__sum'] or 0
        if total_disk + plan.disk_gb > self.max_disk_gb:
            return False, f"Disk limit exceeded ({self.max_disk_gb}GB max)"

        return True, "OK"
