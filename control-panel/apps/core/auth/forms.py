"""
Authentication forms for WebOps.

Contains forms for login, registration, password reset, and 2FA management.
"""

import re
from typing import Dict, Any

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


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

    def clean_email(self) -> str:
        """Ensure email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean_username(self) -> str:
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

    def clean_password1(self) -> str:
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

    def clean(self) -> Dict[str, Any]:
        """Ensure at least one of code or backup_code is provided."""
        cleaned_data = super().clean()
        code = cleaned_data.get('code')
        backup_code = cleaned_data.get('backup_code')

        if not code and not backup_code:
            raise ValidationError('Please enter either a verification code or a backup code.')

        if code and backup_code:
            raise ValidationError('Please enter either a verification code OR a backup code, not both.')

        return cleaned_data
