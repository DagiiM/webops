"""
Authentication views for WebOps.

Reference: CLAUDE.md "Django App Structure" section
Modern authentication with 2FA support and security logging.
"""

from typing import Optional
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
import pyotp
import qrcode
import io
import base64

from .forms import (
    WebOpsLoginForm,
    WebOpsRegistrationForm,
    WebOpsPasswordResetForm,
    WebOpsSetPasswordForm,
    TwoFactorSetupForm,
    TwoFactorVerifyForm
)
from .models import TwoFactorAuth, SecurityAuditLog
from apps.core.models import BrandingSettings


def get_client_ip(request: HttpRequest) -> str:
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """Enhanced login with 2FA support."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = WebOpsLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me', True)

            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Check if 2FA is enabled
                try:
                    two_factor = TwoFactorAuth.objects.get(user=user, is_enabled=True)
                    # Store user ID in session for 2FA verification
                    request.session['pre_2fa_user_id'] = user.id
                    request.session['remember_me'] = remember_me

                    # Log 2FA required
                    SecurityAuditLog.objects.create(
                        user=user,
                        event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
                        severity=SecurityAuditLog.Severity.INFO,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        description=f'Login successful, 2FA required for {username}'
                    )

                    return redirect('two_factor_verify')

                except TwoFactorAuth.DoesNotExist:
                    # No 2FA, proceed with login
                    login(request, user)

                    # Set session expiry
                    if not remember_me:
                        request.session.set_expiry(0)  # Browser close
                    else:
                        request.session.set_expiry(1209600)  # 2 weeks

                    # Log successful login
                    SecurityAuditLog.objects.create(
                        user=user,
                        event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
                        severity=SecurityAuditLog.Severity.INFO,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        description=f'Login successful for {username}'
                    )

                    messages.success(request, f'Welcome back, {user.username}!')
                    return redirect(request.GET.get('next', 'dashboard'))
            else:
                # Log failed login
                SecurityAuditLog.objects.create(
                    event_type=SecurityAuditLog.EventType.LOGIN_FAILED,
                    severity=SecurityAuditLog.Severity.WARNING,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    description=f'Failed login attempt for username: {username}'
                )
                messages.error(request, 'Invalid username or password.')
    else:
        form = WebOpsLoginForm()

    # Get branding for login page
    branding = BrandingSettings.objects.first()
    return render(request, 'auth/login.html', {'form': form, 'branding': branding})


@never_cache
@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    """User registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = WebOpsRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Log registration
            SecurityAuditLog.objects.create(
                user=user,
                event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
                severity=SecurityAuditLog.Severity.INFO,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                description=f'New user registered: {user.username}'
            )

            # Auto-login after registration
            login(request, user)
            messages.success(request, f'Welcome to WebOps, {user.username}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = WebOpsRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})


@require_http_methods(["GET", "POST"])
def password_reset_request(request: HttpRequest) -> HttpResponse:
    """Request password reset."""
    if request.method == 'POST':
        form = WebOpsPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            users = User.objects.filter(email=email)

            if users.exists():
                for user in users:
                    # Generate token
                    token = default_token_generator.make_token(user)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))

                    # Build reset URL
                    reset_url = request.build_absolute_uri(
                        reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                    )

                    # Send email
                    send_mail(
                        subject='WebOps - Password Reset',
                        message=f'Click the link below to reset your password:\n\n{reset_url}\n\nIf you did not request this, please ignore this email.',
                        from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@webops.local',
                        recipient_list=[email],
                        fail_silently=False,
                    )

                    # Log password reset request
                    SecurityAuditLog.objects.create(
                        user=user,
                        event_type=SecurityAuditLog.EventType.PASSWORD_CHANGE,
                        severity=SecurityAuditLog.Severity.INFO,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        description='Password reset requested'
                    )

            # Always show success message (security best practice)
            messages.success(request, 'If an account exists with that email, password reset instructions have been sent.')
            return redirect('login')
    else:
        form = WebOpsPasswordResetForm()

    return render(request, 'auth/password_reset.html', {'form': form})


@require_http_methods(["GET", "POST"])
def password_reset_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Confirm password reset with token."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = WebOpsSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()

                # Log password change
                SecurityAuditLog.objects.create(
                    user=user,
                    event_type=SecurityAuditLog.EventType.PASSWORD_CHANGE,
                    severity=SecurityAuditLog.Severity.INFO,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    description='Password changed successfully'
                )

                messages.success(request, 'Your password has been reset successfully. You can now log in.')
                return redirect('login')
        else:
            form = WebOpsSetPasswordForm(user)

        return render(request, 'auth/password_reset_confirm.html', {'form': form})
    else:
        messages.error(request, 'Invalid or expired password reset link.')
        return redirect('password_reset')


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_setup(request: HttpRequest) -> HttpResponse:
    """Setup 2FA for user account."""
    user = request.user

    # Check if already enabled
    try:
        two_factor = TwoFactorAuth.objects.get(user=user)
        if two_factor.is_enabled:
            messages.info(request, '2FA is already enabled on your account.')
            return redirect('dashboard')
    except TwoFactorAuth.DoesNotExist:
        # Generate new secret
        secret = pyotp.random_base32()
        two_factor = TwoFactorAuth.objects.create(user=user, secret=secret)

    if request.method == 'POST':
        form = TwoFactorSetupForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['verification_code']

            # Verify the code
            totp = pyotp.TOTP(two_factor.secret)
            if totp.verify(code, valid_window=1):
                # Generate backup codes
                backup_codes = [pyotp.random_base32()[:8] for _ in range(10)]
                two_factor.backup_codes = backup_codes
                two_factor.is_enabled = True
                two_factor.save()

                # Log 2FA enabled
                SecurityAuditLog.objects.create(
                    user=user,
                    event_type=SecurityAuditLog.EventType.TFA_ENABLED,
                    severity=SecurityAuditLog.Severity.INFO,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    description='2FA enabled successfully'
                )

                messages.success(request, '2FA has been enabled successfully!')
                return render(request, 'auth/two_factor_backup_codes.html', {
                    'backup_codes': backup_codes
                })
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
    else:
        form = TwoFactorSetupForm()

    # Generate QR code
    totp = pyotp.TOTP(two_factor.secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.username,
        issuer_name='WebOps'
    )

    # Create QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'auth/two_factor_setup.html', {
        'form': form,
        'qr_code': qr_code_base64,
        'secret': two_factor.secret,
        'provisioning_uri': provisioning_uri
    })


@never_cache
@require_http_methods(["GET", "POST"])
def two_factor_verify(request: HttpRequest) -> HttpResponse:
    """Verify 2FA code during login."""
    # Get user from session
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please log in again.')
        return redirect('login')

    try:
        user = User.objects.get(pk=user_id)
        two_factor = TwoFactorAuth.objects.get(user=user, is_enabled=True)
    except (User.DoesNotExist, TwoFactorAuth.DoesNotExist):
        messages.error(request, 'Invalid session. Please log in again.')
        return redirect('login')

    if request.method == 'POST':
        form = TwoFactorVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('code')
            backup_code = form.cleaned_data.get('backup_code')

            verified = False

            # Check TOTP code
            if code:
                totp = pyotp.TOTP(two_factor.secret)
                if totp.verify(code, valid_window=1):
                    verified = True

            # Check backup code
            elif backup_code:
                if backup_code in two_factor.backup_codes:
                    # Remove used backup code
                    two_factor.backup_codes.remove(backup_code)
                    two_factor.save()
                    verified = True
                    messages.warning(request, 'You used a backup code. Please generate new backup codes.')

            if verified:
                # Login user
                login(request, user)

                # Set session expiry
                remember_me = request.session.get('remember_me', True)
                if not remember_me:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)

                # Update last used
                from django.utils import timezone
                two_factor.last_used = timezone.now()
                two_factor.save()

                # Clean up session
                del request.session['pre_2fa_user_id']
                if 'remember_me' in request.session:
                    del request.session['remember_me']

                # Log successful 2FA
                SecurityAuditLog.objects.create(
                    user=user,
                    event_type=SecurityAuditLog.EventType.TFA_SUCCESS,
                    severity=SecurityAuditLog.Severity.INFO,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    description='2FA verification successful'
                )

                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('dashboard')
            else:
                # Log failed 2FA
                SecurityAuditLog.objects.create(
                    user=user,
                    event_type=SecurityAuditLog.EventType.TFA_FAILED,
                    severity=SecurityAuditLog.Severity.WARNING,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    description='2FA verification failed'
                )
                messages.error(request, 'Invalid verification code.')
    else:
        form = TwoFactorVerifyForm()

    return render(request, 'auth/two_factor_verify.html', {'form': form})


@login_required
def two_factor_disable(request: HttpRequest) -> HttpResponse:
    """Disable 2FA for user account."""
    if request.method == 'POST':
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user)
            two_factor.is_enabled = False
            two_factor.save()

            # Log 2FA disabled
            SecurityAuditLog.objects.create(
                user=request.user,
                event_type=SecurityAuditLog.EventType.TFA_DISABLED,
                severity=SecurityAuditLog.Severity.WARNING,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                description='2FA disabled'
            )

            messages.success(request, '2FA has been disabled.')
        except TwoFactorAuth.DoesNotExist:
            messages.error(request, '2FA is not enabled on your account.')

        return redirect('dashboard')

    return render(request, 'auth/two_factor_disable_confirm.html')


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    """Enhanced logout with security logging."""
    user = request.user

    # Log logout
    SecurityAuditLog.objects.create(
        user=user,
        event_type=SecurityAuditLog.EventType.LOGOUT,
        severity=SecurityAuditLog.Severity.INFO,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        description=f'User {user.username} logged out'
    )

    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')
