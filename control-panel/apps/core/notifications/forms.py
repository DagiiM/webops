"""
Notification forms for WebOps.

"Django App Structure" section
Modern, forward-facing notification configuration with enhanced validation.
"""

from django import forms
from django.core.exceptions import ValidationError
from apps.core.notifications.models import NotificationChannel


class NotificationChannelForm(forms.ModelForm):
    """Form for creating and editing notification channels."""

    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input',
            'placeholder': 'My Email Notifications',
        })
    )

    channel_type = forms.ChoiceField(
        choices=NotificationChannel.ChannelType.choices,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select webops-input',
            'id': 'id_channel_type',
        })
    )

    # Email configuration
    email_address = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input webops-input channel-config email-config',
            'placeholder': 'your.email@example.com',
        })
    )

    # Webhook configuration
    webhook_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-input webops-input channel-config webhook-config',
            'placeholder': 'https://your-webhook-endpoint.com/webhook',
        })
    )

    # SMTP configuration
    smtp_host = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input channel-config smtp-config',
            'placeholder': 'smtp.example.com',
        })
    )
    smtp_port = forms.IntegerField(
        min_value=1,
        max_value=65535,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-input webops-input channel-config smtp-config',
            'placeholder': '587',
        })
    )
    smtp_username = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input channel-config smtp-config',
            'placeholder': 'username',
        })
    )
    smtp_password = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input webops-input channel-config smtp-config',
            'placeholder': 'password',
        })
    )
    smtp_from_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input webops-input channel-config smtp-config',
            'placeholder': 'noreply@example.com',
        })
    )
    smtp_to_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input webops-input channel-config smtp-config',
            'placeholder': 'recipient@example.com',
        })
    )

    # Event filters
    notify_on_deploy_success = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_deploy_failure = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_deploy_start = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_health_check_fail = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_resource_warning = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    class Meta:
        model = NotificationChannel
        fields = [
            'name',
            'channel_type',
            'notify_on_deploy_success',
            'notify_on_deploy_failure',
            'notify_on_deploy_start',
            'notify_on_health_check_fail',
            'notify_on_resource_warning',
        ]

    def clean(self):
        cleaned_data = super().clean()
        channel_type = cleaned_data.get('channel_type')
        email_address = cleaned_data.get('email_address')
        webhook_url = cleaned_data.get('webhook_url')
        smtp_host = cleaned_data.get('smtp_host')
        smtp_username = cleaned_data.get('smtp_username')
        smtp_password = cleaned_data.get('smtp_password')
        smtp_from_email = cleaned_data.get('smtp_from_email')
        smtp_to_email = cleaned_data.get('smtp_to_email')

        # Validate based on channel type
        if channel_type == NotificationChannel.ChannelType.EMAIL:
            if not email_address:
                raise ValidationError('Email address is required for email notifications.')
        elif channel_type == NotificationChannel.ChannelType.WEBHOOK:
            if not webhook_url:
                raise ValidationError('Webhook URL is required for webhook notifications.')
        elif channel_type == NotificationChannel.ChannelType.SMTP:
            required_fields = {
                'SMTP Host': smtp_host,
                'SMTP Username': smtp_username,
                'SMTP Password': smtp_password,
                'From Email': smtp_from_email,
                'To Email': smtp_to_email,
            }
            missing_fields = [name for name, value in required_fields.items() if not value]
            if missing_fields:
                raise ValidationError(f'SMTP configuration requires: {", ".join(missing_fields)}')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Build config based on channel type
        channel_type = self.cleaned_data.get('channel_type')
        config = {}

        if channel_type == NotificationChannel.ChannelType.EMAIL:
            config['email'] = self.cleaned_data.get('email_address')
        elif channel_type == NotificationChannel.ChannelType.WEBHOOK:
            config['webhook_url'] = self.cleaned_data.get('webhook_url')
        elif channel_type == NotificationChannel.ChannelType.SMTP:
            config = {
                'host': self.cleaned_data.get('smtp_host'),
                'port': self.cleaned_data.get('smtp_port', 587),
                'username': self.cleaned_data.get('smtp_username'),
                'password': self.cleaned_data.get('smtp_password'),
                'from_email': self.cleaned_data.get('smtp_from_email'),
                'to_email': self.cleaned_data.get('smtp_to_email'),
            }

        instance.config = config

        if commit:
            instance.save()

        return instance