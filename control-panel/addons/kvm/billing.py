"""
Billing Integration

Integration with payment processors and billing systems.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models

from .models import VMDeployment, VMUsageRecord, BaseModel

logger = logging.getLogger(__name__)


class Invoice(BaseModel):
    """
    Monthly invoice for VM usage.
    """
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='kvm_invoices'
    )

    invoice_number = models.CharField(max_length=50, unique=True)

    period_start = models.DateField()
    period_end = models.DateField()

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft'
    )

    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)

    # Payment processor details
    payment_method = models.CharField(max_length=50, blank=True)
    payment_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"{self.invoice_number} - {self.user.username} - ${self.total}"


class InvoiceLineItem(BaseModel):
    """
    Individual line item on an invoice.
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='line_items'
    )

    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=4)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Link to VM
    vm_deployment = models.ForeignKey(
        VMDeployment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Invoice Line Item"
        verbose_name_plural = "Invoice Line Items"

    def __str__(self):
        return f"{self.description} - ${self.total}"


class BillingManager:
    """
    Manages billing, invoicing, and payment processing.
    """

    def __init__(self):
        self.tax_rate = Decimal('0.00')  # Configure per jurisdiction

    def generate_monthly_invoice(
        self,
        user,
        year: int,
        month: int,
    ) -> Invoice:
        """
        Generate invoice for a user for a specific month.

        Args:
            user: User to bill
            year: Year
            month: Month (1-12)

        Returns:
            Generated Invoice instance
        """
        from calendar import monthrange

        # Calculate period
        period_start = datetime(year, month, 1).date()
        last_day = monthrange(year, month)[1]
        period_end = datetime(year, month, last_day).date()

        logger.info(f"Generating invoice for {user.username}: {period_start} to {period_end}")

        # Generate invoice number
        invoice_number = self._generate_invoice_number(year, month, user.id)

        # Create invoice
        invoice = Invoice.objects.create(
            user=user,
            invoice_number=invoice_number,
            period_start=period_start,
            period_end=period_end,
            due_date=period_end + timedelta(days=15),  # 15 days to pay
        )

        # Get usage records for period
        usage_records = VMUsageRecord.objects.filter(
            vm_deployment__deployment__user=user,
            timestamp__gte=period_start,
            timestamp__lt=period_end + timedelta(days=1),
        ).select_related('vm_deployment')

        # Group by VM
        vm_usage = {}
        for record in usage_records:
            vm_id = record.vm_deployment.id
            if vm_id not in vm_usage:
                vm_usage[vm_id] = {
                    'vm': record.vm_deployment,
                    'hours': 0,
                    'cost': Decimal('0.00'),
                }
            if record.state == 'running':
                vm_usage[vm_id]['hours'] += Decimal('1.00')
                vm_usage[vm_id]['cost'] += record.cost

        # Create line items
        subtotal = Decimal('0.00')

        for vm_data in vm_usage.values():
            vm = vm_data['vm']
            hours = vm_data['hours']
            cost = vm_data['cost']

            if cost > 0:
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=f"VM: {vm.vm_name} ({vm.vm_plan.display_name})",
                    quantity=hours,
                    unit_price=vm.vm_plan.hourly_price,
                    total=cost,
                    vm_deployment=vm,
                )

                subtotal += cost

        # Calculate tax
        tax = subtotal * self.tax_rate

        # Update invoice totals
        invoice.subtotal = subtotal
        invoice.tax = tax
        invoice.total = subtotal + tax
        invoice.status = 'sent'
        invoice.save()

        logger.info(f"Invoice generated: {invoice_number} - ${invoice.total}")

        return invoice

    def _generate_invoice_number(self, year: int, month: int, user_id: int) -> str:
        """Generate unique invoice number."""
        return f"INV-{year}{month:02d}-{user_id:06d}"

    def process_payment(
        self,
        invoice: Invoice,
        payment_method: str,
        payment_processor_data: Dict[str, Any],
    ) -> bool:
        """
        Process payment for an invoice.

        Args:
            invoice: Invoice to pay
            payment_method: Payment method (stripe, paypal, etc.)
            payment_processor_data: Data from payment processor

        Returns:
            True if payment successful
        """
        try:
            if payment_method == 'stripe':
                return self._process_stripe_payment(invoice, payment_processor_data)
            elif payment_method == 'paypal':
                return self._process_paypal_payment(invoice, payment_processor_data)
            else:
                logger.error(f"Unknown payment method: {payment_method}")
                return False

        except Exception as e:
            logger.error(f"Payment processing failed: {e}", exc_info=True)
            return False

    def _process_stripe_payment(
        self,
        invoice: Invoice,
        payment_data: Dict[str, Any]
    ) -> bool:
        """
        Process payment via Stripe.

        Requires: pip install stripe
        """
        try:
            import stripe
            from django.conf import settings

            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(invoice.total * 100),  # Amount in cents
                currency='usd',
                metadata={
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'user_id': invoice.user.id,
                },
            )

            # Mark invoice as paid
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
            invoice.payment_method = 'stripe'
            invoice.payment_id = intent.id
            invoice.save()

            logger.info(f"Stripe payment processed: {invoice.invoice_number}")
            return True

        except ImportError:
            logger.error("Stripe library not installed")
            return False
        except Exception as e:
            logger.error(f"Stripe payment failed: {e}")
            return False

    def _process_paypal_payment(
        self,
        invoice: Invoice,
        payment_data: Dict[str, Any]
    ) -> bool:
        """Process payment via PayPal."""
        # TODO: Implement PayPal integration
        logger.warning("PayPal integration not yet implemented")
        return False

    def get_user_billing_summary(self, user) -> Dict[str, Any]:
        """
        Get billing summary for a user.

        Returns:
            Dictionary with billing information
        """
        from django.db.models import Sum, Count

        # Current month usage
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        current_usage = VMUsageRecord.objects.filter(
            vm_deployment__deployment__user=user,
            timestamp__gte=month_start,
        ).aggregate(
            total_cost=Sum('cost'),
            record_count=Count('id')
        )

        # Invoice stats
        invoices = Invoice.objects.filter(user=user)
        unpaid_invoices = invoices.filter(status__in=['sent', 'overdue'])

        return {
            'current_month': {
                'cost': float(current_usage['total_cost'] or 0),
                'hours': current_usage['record_count'],
            },
            'invoices': {
                'total': invoices.count(),
                'unpaid': unpaid_invoices.count(),
                'unpaid_total': float(
                    unpaid_invoices.aggregate(Sum('total'))['total__sum'] or 0
                ),
            },
            'active_vms': VMDeployment.objects.filter(
                deployment__user=user,
                deployment__status='running'
            ).count(),
        }


class UsageReporter:
    """
    Generate usage reports for billing.
    """

    def generate_usage_report(
        self,
        user,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Generate detailed usage report.

        Args:
            user: User
            start_date: Report start
            end_date: Report end

        Returns:
            List of usage records
        """
        records = VMUsageRecord.objects.filter(
            vm_deployment__deployment__user=user,
            timestamp__gte=start_date,
            timestamp__lt=end_date,
        ).select_related('vm_deployment').order_by('timestamp')

        report = []
        for record in records:
            report.append({
                'timestamp': record.timestamp.isoformat(),
                'vm_name': record.vm_deployment.vm_name,
                'state': record.state,
                'vcpus': record.vcpus,
                'memory_mb': record.memory_mb,
                'disk_gb': record.disk_gb,
                'hourly_rate': float(record.hourly_rate),
                'cost': float(record.cost),
            })

        return report

    def export_usage_csv(
        self,
        user,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """Export usage report as CSV."""
        import csv
        from io import StringIO

        report = self.generate_usage_report(user, start_date, end_date)

        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=['timestamp', 'vm_name', 'state', 'vcpus',
                       'memory_mb', 'disk_gb', 'hourly_rate', 'cost']
        )

        writer.writeheader()
        writer.writerows(report)

        return output.getvalue()
