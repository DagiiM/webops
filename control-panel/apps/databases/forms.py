"""
Forms for Databases app.
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Database
from .adapters.base import DatabaseType
from apps.addons.models import Addon


class DatabaseForm(forms.ModelForm):
    """Form for creating and editing databases with dynamic validation."""

    class Meta:
        model = Database
        fields = [
            'name', 'db_type', 'host', 'port', 'username', 'password',
            'database_name', 'api_key', 'environment', 'connection_uri',
            'ssl_enabled', 'connection_timeout', 'pool_size', 'required_addons'
        ]
        widgets = {
            'password': forms.PasswordInput(render_value=True),
            'api_key': forms.PasswordInput(render_value=True),
            'db_type': forms.Select(attrs={
                'class': 'webops-select',
                'id': 'db_type'
            }),
            'name': forms.TextInput(attrs={
                'class': 'webops-input',
                'placeholder': 'Enter database name'
            }),
            'host': forms.TextInput(attrs={
                'class': 'webops-input',
                'placeholder': 'localhost'
            }),
            'port': forms.NumberInput(attrs={
                'class': 'webops-input',
                'placeholder': '5432'
            }),
            'username': forms.TextInput(attrs={
                'class': 'webops-input',
                'placeholder': 'Username'
            }),
            'database_name': forms.TextInput(attrs={
                'class': 'webops-input',
                'placeholder': 'Database name'
            }),
            'environment': forms.TextInput(attrs={
                'class': 'webops-input',
                'placeholder': 'us-west1-gcp'
            }),
            'connection_uri': forms.Textarea(attrs={
                'class': 'webops-input',
                'rows': 2,
                'placeholder': 'mongodb://username:password@host:port/database'
            }),
            'connection_timeout': forms.NumberInput(attrs={
                'class': 'webops-input'
            }),
            'pool_size': forms.NumberInput(attrs={
                'class': 'webops-input'
            }),
            'required_addons': forms.CheckboxSelectMultiple(attrs={
                'class': 'webops-checkbox-group'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make fields not required initially
        for field_name in self.fields:
            self.fields[field_name].required = False
        
        # Only name and db_type are always required
        self.fields['name'].required = True
        self.fields['db_type'].required = True
        
        # Filter addons to only show database-related ones
        self.fields['required_addons'].queryset = Addon.objects.filter(
            capabilities__contains=['database']
        )

    def clean(self):
        """Clean and validate form data based on database type."""
        cleaned_data = super().clean()
        db_type = cleaned_data.get('db_type')
        
        if not db_type:
            raise ValidationError("Database type is required")
        
        db_type_enum = DatabaseType(db_type)
        
        # Validate required fields based on database type
        if db_type_enum == DatabaseType.POSTGRESQL:
            self._validate_relational_db(cleaned_data, "PostgreSQL")
            # Set default port if not provided
            if not cleaned_data.get('port'):
                cleaned_data['port'] = 5432
                
        elif db_type_enum == DatabaseType.MYSQL:
            self._validate_relational_db(cleaned_data, "MySQL")
            # Set default port if not provided
            if not cleaned_data.get('port'):
                cleaned_data['port'] = 3306
                
        elif db_type_enum == DatabaseType.MONGODB:
            self._validate_mongodb(cleaned_data)
            # Set default port if not provided
            if not cleaned_data.get('port'):
                cleaned_data['port'] = 27017
                
        elif db_type_enum == DatabaseType.SQLITE:
            if not cleaned_data.get('database_name'):
                raise ValidationError("Database file path is required for SQLite")
                
        elif db_type_enum == DatabaseType.PINECONE:
            if not cleaned_data.get('api_key'):
                raise ValidationError("API key is required for Pinecone")
            if not cleaned_data.get('environment'):
                raise ValidationError("Environment is required for Pinecone")
                
        elif db_type_enum == DatabaseType.REDIS:
            if not cleaned_data.get('host'):
                raise ValidationError("Host is required for Redis")
            if not cleaned_data.get('port'):
                cleaned_data['port'] = 6379  # Default Redis port
        
        return cleaned_data

    def _validate_relational_db(self, cleaned_data, db_name):
        """Validate fields for relational databases (PostgreSQL, MySQL)."""
        # Password is optional (will be auto-generated if not provided)
        # database_name is optional (will default to 'name' field if not provided)
        required_fields = ['host', 'port', 'username']
        for field in required_fields:
            if not cleaned_data.get(field):
                raise ValidationError(f"{field.replace('_', ' ').title()} is required for {db_name}")

        # Set database_name to name if not provided
        if not cleaned_data.get('database_name'):
            cleaned_data['database_name'] = cleaned_data.get('name')

    def _validate_mongodb(self, cleaned_data):
        """Validate fields for MongoDB."""
        if not cleaned_data.get('connection_uri'):
            # If no URI, require host and port
            required_fields = ['host', 'port']
            for field in required_fields:
                if not cleaned_data.get(field):
                    raise ValidationError(f"{field.replace('_', ' ').title()} is required for MongoDB when not using connection URI")

            # Set database_name to name if not provided
            if not cleaned_data.get('database_name'):
                cleaned_data['database_name'] = cleaned_data.get('name')
        else:
            # If URI is provided, username/password are optional
            pass

    def _post_clean(self):
        """Override to skip model validation since form already validated."""
        # We skip calling super()._post_clean() which would call instance.clean()
        # This prevents duplicate validation errors since we've already validated
        # everything in the form's clean() method
        pass

    def save(self, commit=True):
        """Save the form instance."""
        instance = super().save(commit=False)

        # Set default values if not provided
        if not instance.connection_timeout:
            instance.connection_timeout = 30
        if not instance.pool_size:
            instance.pool_size = 5

        if commit:
            instance.save()
        return instance


class DatabaseTestForm(forms.Form):
    """Form for testing database connections."""
    
    test_query = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'webops-input',
            'rows': 3,
            'placeholder': 'Enter test query (e.g., SELECT 1)'
        }),
        required=False,
        initial="SELECT 1",
        help_text="Query to test database connection"
    )