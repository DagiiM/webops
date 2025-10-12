"""
Authentication forms for WebOps.

Reference: CLAUDE.md "Django App Structure" section
Modern, forward-facing authentication with enhanced security.
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
import re


class WebOpsLoginForm(AuthenticationForm):
    """Enhanced login form with better styling."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter your username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter your password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox'
        })
    )


class WebOpsRegistrationForm(UserCreationForm):
    """User registration form with email and enhanced validation."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'webops-input',
            'placeholder': 'your.email@example.com'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Choose a username'
        }),
        help_text='Letters, numbers, and @/./+/-/_ only.'
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Create a strong password'
        }),
        help_text='Minimum 8 characters, must include letters and numbers.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Confirm your password'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        """Ensure email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean_username(self):
        """Validate username format."""
        username = self.cleaned_data.get('username')

        # Check for reserved usernames
        reserved = ['admin', 'root', 'webops', 'administrator', 'system', 'api', 'www']
        if username.lower() in reserved:
            raise ValidationError('This username is reserved.')

        # Check length
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters.')

        # Check for valid characters
        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError('Username contains invalid characters.')

        return username

    def clean_password1(self):
        """Enhanced password validation."""
        password = self.cleaned_data.get('password1')

        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters.')

        if not re.search(r'[A-Za-z]', password):
            raise ValidationError('Password must contain at least one letter.')

        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')

        # Check for common passwords
        common_passwords = ['password', '12345678', 'qwerty', 'admin123']
        if password.lower() in common_passwords:
            raise ValidationError('This password is too common.')

        return password


class WebOpsPasswordResetForm(PasswordResetForm):
    """Password reset request form."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter your email address'
        })
    )


class WebOpsSetPasswordForm(SetPasswordForm):
    """Set new password form."""

    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter new password'
        })
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Confirm new password'
        })
    )


class TwoFactorSetupForm(forms.Form):
    """Form for setting up 2FA."""

    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'off'
        }),
        help_text='Enter the 6-digit code from your authenticator app'
    )


class TwoFactorVerifyForm(forms.Form):
    """Form for verifying 2FA code during login."""

    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'off',
            'autofocus': True
        }),
        label='Verification Code'
    )
    backup_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Or enter backup code'
        }),
        label='Backup Code (optional)'
    )
    
    def clean(self):
        """Ensure at least one of code or backup_code is provided."""
        cleaned_data = super().clean()
        code = cleaned_data.get('code')
        backup_code = cleaned_data.get('backup_code')
        
        if not code and not backup_code:
            raise ValidationError('Please enter either a verification code or a backup code.')
        
        if code and backup_code:
            raise ValidationError('Please enter either a verification code OR a backup code, not both.')
        
        return cleaned_data


class BrandingSettingsForm(forms.Form):
    """Form for customizing WebOps branding."""

    site_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'WebOps'
        }),
        help_text='The name displayed in the browser title and header'
    )
    logo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'webops-file-input',
            'accept': 'image/png,image/jpeg,image/svg+xml'
        }),
        help_text='Logo image (recommended: 200x50px, PNG with transparency)'
    )
    favicon = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'webops-file-input',
            'accept': 'image/png,image/x-icon'
        }),
        help_text='Favicon (recommended: 32x32px or 64x64px, PNG/ICO)'
    )
    primary_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'type': 'color',
            'placeholder': '#3b82f6'
        }),
        help_text='Primary brand color'
    )
    secondary_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'type': 'color',
            'placeholder': '#1e40af'
        }),
        help_text='Secondary brand color'
    )
    accent_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'type': 'color',
            'placeholder': '#10b981'
        }),
        help_text='Accent color for success states'
    )
    header_bg_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'type': 'color',
            'placeholder': '#1f2937'
        }),
        help_text='Header background color'
    )

    def clean_logo(self):
        """Validate logo file size and dimensions."""
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check file size (max 2MB)
            if logo.size > 2 * 1024 * 1024:
                raise ValidationError('Logo file size must be under 2MB')
        return logo

    def clean_favicon(self):
        """Validate favicon file size."""
        favicon = self.cleaned_data.get('favicon')
        if favicon:
            # Check file size (max 500KB)
            if favicon.size > 500 * 1024:
                raise ValidationError('Favicon file size must be under 500KB')
        return favicon

    def clean_primary_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('primary_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    def clean_secondary_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('secondary_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    def clean_accent_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('accent_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    def clean_header_bg_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('header_bg_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color


# ==================================
# Webhook and Notification Forms
# ==================================

from apps.core.models import Webhook, NotificationChannel
from apps.deployments.models import Deployment


class WebhookForm(forms.ModelForm):
    """Form for creating and editing webhooks."""

    deployment = forms.ModelChoiceField(
        queryset=Deployment.objects.all(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select webops-input',
        })
    )

    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input',
            'placeholder': 'My Auto-Deploy Webhook',
        })
    )

    trigger_event = forms.ChoiceField(
        choices=Webhook.TriggerEvent.choices,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select webops-input',
        })
    )

    branch_filter = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input',
            'placeholder': 'main (leave empty for all branches)',
        })
    )

    class Meta:
        model = Webhook
        fields = ['name', 'deployment', 'trigger_event', 'branch_filter']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['deployment'].queryset = Deployment.objects.filter(deployed_by=user)


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

        # Validate based on channel type
        if channel_type == NotificationChannel.ChannelType.EMAIL:
            if not email_address:
                raise ValidationError('Email address is required for email notifications.')
        elif channel_type == NotificationChannel.ChannelType.WEBHOOK:
            if not webhook_url:
                raise ValidationError('Webhook URL is required for webhook notifications.')

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

        instance.config = config

        if commit:
            instance.save()

        return instance
