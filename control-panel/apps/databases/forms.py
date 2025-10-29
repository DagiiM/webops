"""
Forms for Databases app.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .models import Database
from .adapters.base import DatabaseType
from apps.addons.models import Addon

# Define a validator for database identifiers (names, usernames)
identifier_validator = RegexValidator(
    regex=r'^[a-zA-Z][a-zA-Z0-9_]*$',
    message='Identifier must start with a letter, and contain only letters, numbers, and underscores.',
    code='invalid_identifier'
)

# Define a validator for database names with length restrictions
database_name_validator = RegexValidator(
    regex=r'^[a-zA-Z][a-zA-Z0-9_]*$',
    message='Database name must start with a letter, and contain only letters, numbers, and underscores (max 63 characters).',
    code='invalid_database_name'
)

# Define a validator for usernames with length restrictions
username_validator = RegexValidator(
    regex=r'^[a-zA-Z][a-zA-Z0-9_]*$',
    message='Username must start with a letter, and contain only letters, numbers, and underscores (max 63 characters).',
    code='invalid_username'
)

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
        if database_name and not database_name_validator(database_name):
            raise ValidationError("Invalid database name format")
        
        # Additional length validation
        if database_name and len(database_name) > 63:
            raise ValidationError("Database name too long (max 63 characters)")
            
        return database_name
    
    def clean_name(self):
        """Custom validation for database name."""
        name = self.cleaned_data.get('name')
        if name and not identifier_validator(name):
            raise ValidationError("Invalid database name format")
        
        # Additional length validation
        if name and len(name) > 63:
            raise ValidationError("Database name too long (max 63 characters)")
            
        return name
    
    def clean_username(self):
        """Custom validation for username."""
        username = self.cleaned_data.get('username')
        if username and not identifier_validator(username):
            raise ValidationError("Invalid username format")
        
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
            if not re.match(r'^[a-zA-Z0-9+://[a-zA-Z0-9\.\-@:/]+[a-zA-Z0-9\.\-@:/]*$', connection_uri):
                raise ValidationError("Invalid connection URI format")
        return connection_uri
    
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