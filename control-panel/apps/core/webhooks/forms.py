"""
Webhook forms for WebOps.

"Django App Structure" section
Modern, forward-facing webhook configuration with enhanced validation.
"""

from django import forms
from django.contrib.auth.models import User
from apps.core.webhooks.models import Webhook


class WebhookForm(forms.ModelForm):
    """Form for creating and editing webhooks."""

    deployment = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
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
            self.fields['deployment'].queryset = ApplicationDeployment.objects.filter(deployed_by=user)