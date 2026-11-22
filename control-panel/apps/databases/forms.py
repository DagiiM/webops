"""
Forms for Databases app.
"""

from django import forms
import re
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .models import Database
from .adapters.base import DatabaseType
from apps.addons.models import Addon

# Strict reusable validators, including boundary checks for direct API callers.
# Django validators return None for valid input and raise ValidationError otherwise.
def _validate_sql_identifier(value, kind):
    if not isinstance(value, str) or len(value) < 1 or len(value) > 63 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValidationError(f"{kind} must start with a letter, use only letters, digits and underscores, and be at most 63 characters.")
    return None

def identifier_validator(value):
    return _validate_sql_identifier(value, "Identifier")

def database_name_validator(value):
    return _validate_sql_identifier(value, "Database name")

def username_validator(value):
    return _validate_sql_identifier(value, "Username")

# Define a validator for connection URIs to prevent injection
connection_uri_validator = RegexValidator(
    regex=r'^(mongodb|mysql|postgresql|sqlite)://[a-zA-Z0-9_\-\.@:/]+[a-zA-Z0-9_\-\.@:/]*$',
    message='Invalid connection URI format.',
    code='invalid_connection_uri'
)


class DatabaseForm(forms.ModelForm):
    """Form for creating and editing databases with dynamic validation."""

    # Override the name field to add validation
    name = forms.CharField(
        max_length=63,  # PostgreSQL identifier limit
        validators=[identifier_validator],
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter database name'
        })
    )
    
    # Override the username field to add validation
    username = forms.CharField(
        max_length=63,  # PostgreSQL identifier limit
        required=False,
        validators=[identifier_validator],
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Username'
        })
    )

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
            'host': forms.TextInput(attrs={
                'class': 'webops-input',
                'placeholder': 'localhost'
            }),
            'port': forms.NumberInput(attrs={
                'class': 'webops-input',
                'placeholder': '5432'
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

    def clean_database_name(self):
        """Custom validation for database name."""
        database_name = self.cleaned_data.get('database_name')
        if database_name and self.cleaned_data.get('db_type') != DatabaseType.SQLITE.value:
            database_name_validator(database_name)
        elif database_name and self.cleaned_data.get('db_type') == DatabaseType.SQLITE.value:
            # SQLite uses filesystem paths, not SQL identifiers.
            if '..' in database_name or not re.fullmatch(r'[A-Za-z0-9_./-]+',database_name):
                raise ValidationError("Invalid SQLite database path")
        
        # Additional length validation
        if database_name and len(database_name) > 63:
            raise ValidationError("Database name too long (max 63 characters)")
            
        return database_name
    
    def clean_name(self):
        """Custom validation for database name."""
        name = self.cleaned_data.get('name')
        if name:
            identifier_validator(name)
        
        # Additional length validation
        if name and len(name) > 63:
            raise ValidationError("Database name too long (max 63 characters)")
            
        return name
    
    def clean_username(self):
        """Custom validation for username."""
        username = self.cleaned_data.get('username')
        if username:
            username_validator(username)
        
        # Additional length validation
        if username and len(username) > 63:
            raise ValidationError("Username too long (max 63 characters)")
            
        return username
    
    def clean_host(self):
        """Custom validation for host."""
        host = self.cleaned_data.get('host')
        if host:
            # Basic host validation to prevent injection
            if not re.match(r'^[a-zA-Z0-9\.\-]+$', host):
                raise ValidationError("Invalid host format")
            
            # Length validation
            if len(host) > 253:  # Max hostname length
                raise ValidationError("Host too long (max 253 characters)")
            
        return host
    
    def clean_port(self):
        """Custom validation for port."""
        port = self.cleaned_data.get('port')
        if port:
            try:
                port_int = int(port)
                if not (1 <= port_int <= 65535):
                    raise ValidationError("Port must be between 1 and 65535")
            except (ValueError, TypeError):
                raise ValidationError("Invalid port number")
        return port
    
    def clean_connection_uri(self):
        """Custom validation for connection URI."""
        connection_uri = self.cleaned_data.get('connection_uri')
        if connection_uri:
            # Basic URI validation to prevent injection
            if not re.fullmatch(r'(?:mongodb|mysql|postgresql|sqlite)://[A-Za-z0-9_./:@%-]+', connection_uri):
                raise ValidationError("Invalid connection URI format")
        return connection_uri
    
    def clean(self):
        """Apply provider-specific field validation and sensible default ports."""
        data=super().clean()
        db_type=data.get('db_type')
        if not db_type:
            self.add_error('db_type','Database type is required')
            return data
        kind=DatabaseType(db_type)
        defaults={DatabaseType.POSTGRESQL:5432,DatabaseType.MYSQL:3306,
                  DatabaseType.MONGODB:27017,DatabaseType.REDIS:6379}
        if kind in (DatabaseType.POSTGRESQL,DatabaseType.MYSQL):
            if not data.get('host'):self.add_error('host','Host is required')
            if not data.get('username'):self.add_error('username','Username is required')
            if not data.get('port') and data.get('host') and data.get('username'):
                data['port']=defaults[kind]
            if not data.get('port') and (not data.get('host') or not data.get('username')):
                self.add_error('port','Port is required when connection settings are incomplete')
            data['database_name']=data.get('database_name') or data.get('name')
        elif kind==DatabaseType.MONGODB:
            if not data.get('connection_uri'):
                if not data.get('host'):
                    self.add_error('host','Host is required without a MongoDB URI')
                    self.add_error('connection_uri','Provide a URI or a host')
                if data.get('host') and not data.get('port'):
                    data['port']=defaults[kind]
            data['database_name']=data.get('database_name') or data.get('name')
        elif kind==DatabaseType.SQLITE:
            if not data.get('database_name'):self.add_error('database_name','SQLite path required')
        elif kind==DatabaseType.PINECONE:
            if not data.get('api_key'):self.add_error('api_key','Pinecone API key required')
            if not data.get('environment'):self.add_error('environment','Pinecone environment required')
        elif kind==DatabaseType.REDIS:
            if not data.get('host'):
                self.add_error('host','Redis host required')
                if not data.get('port'):
                    self.add_error('port','Redis port required')
            if data.get('host') and not data.get('port'):data['port']=defaults[kind]
        return data

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

    def save(self, commit=True):
        """Save the form instance."""
        instance = super().save(commit=False)

        # Encrypt secrets before storage; never persist plaintext credentials.
        from apps.core.utils import encrypt_password, decrypt_password
        if instance.password:
            try:
                decrypt_password(instance.password)
            except Exception:
                instance.password = encrypt_password(instance.password)
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