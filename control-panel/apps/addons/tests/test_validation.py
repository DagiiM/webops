"""
Tests for input validation functionality.

Tests JSON schema validation, sanitization, and request validation including:
- Schema validation
- String sanitization
- Addon name validation
- Configuration validation
- Request body validation
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.http import JsonResponse
import json

from apps.addons.validation import (
    validate_json_schema,
    validate_addon_config,
    sanitize_string,
    sanitize_addon_name,
    ValidationError,
    AddonSchemas,
    validate_request_json,
    validate_addon_name_param,
    validate_pagination_params,
    config_validator,
)

User = get_user_model()


class TestJSONSchemaValidation(TestCase):
    """Tests for JSON schema validation."""

    def test_validate_simple_object(self):
        """Test validating a simple object."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }

        data = {"name": "John", "age": 30}
        errors = validate_json_schema(data, schema)

        self.assertEqual(len(errors), 0)

    def test_validate_type_mismatch(self):
        """Test validation fails on type mismatch."""
        schema = {"type": "integer"}
        data = "not an integer"

        errors = validate_json_schema(data, schema)

        self.assertGreater(len(errors), 0)
        self.assertIn("Expected integer", errors[0])

    def test_validate_required_properties(self):
        """Test validation enforces required properties."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"}
            }
        }

        data = {}
        errors = validate_json_schema(data, schema)

        self.assertGreater(len(errors), 0)
        self.assertIn("Missing required property: name", errors[0])

    def test_validate_additional_properties_forbidden(self):
        """Test validation rejects additional properties when forbidden."""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"}
            }
        }

        data = {"name": "John", "extra": "field"}
        errors = validate_json_schema(data, schema)

        self.assertGreater(len(errors), 0)
        self.assertIn("Additional properties not allowed", errors[0])

    def test_validate_integer_minimum(self):
        """Test integer minimum validation."""
        schema = {
            "type": "integer",
            "minimum": 10
        }

        errors = validate_json_schema(5, schema)

        self.assertGreater(len(errors), 0)
        self.assertIn("less than minimum", errors[0])

    def test_validate_integer_maximum(self):
        """Test integer maximum validation."""
        schema = {
            "type": "integer",
            "maximum": 100
        }

        errors = validate_json_schema(150, schema)

        self.assertGreater(len(errors), 0)
        self.assertIn("greater than maximum", errors[0])

    def test_validate_string_pattern(self):
        """Test string pattern validation."""
        schema = {
            "type": "string",
            "pattern": r"^\d{3}-\d{3}-\d{4}$"
        }

        # Valid phone number
        errors1 = validate_json_schema("123-456-7890", schema)
        self.assertEqual(len(errors1), 0)

        # Invalid format
        errors2 = validate_json_schema("invalid", schema)
        self.assertGreater(len(errors2), 0)


class TestAddonConfigValidation(TestCase):
    """Tests for addon configuration validation."""

    def test_validate_valid_config(self):
        """Test validation passes for valid config."""
        config = {
            "port": 5432,
            "max_connections": 100
        }

        errors = validate_addon_config(config)

        self.assertEqual(len(errors), 0)

    def test_validate_invalid_port(self):
        """Test validation fails for invalid port."""
        config = {"port": 70000}  # > 65535

        errors = validate_addon_config(config)

        self.assertGreater(len(errors), 0)

    def test_validate_reserved_port(self):
        """Test validation fails for reserved ports."""
        for port in [22, 80, 443]:
            config = {"port": port}
            errors = validate_addon_config(config)

            self.assertGreater(len(errors), 0)
            self.assertIn("reserved", errors[0])

    def test_validate_non_dict_config(self):
        """Test validation fails for non-dict config."""
        errors = validate_addon_config("not a dict")

        self.assertGreater(len(errors), 0)
        self.assertIn("must be a JSON object", errors[0])


class TestStringSanitization(TestCase):
    """Tests for string sanitization."""

    def test_sanitize_normal_string(self):
        """Test sanitizing a normal string."""
        result = sanitize_string("  hello world  ")

        self.assertEqual(result, "hello world")

    def test_sanitize_removes_control_characters(self):
        """Test that control characters are removed."""
        # ASCII control character (bell)
        result = sanitize_string("hello\x07world")

        self.assertNotIn('\x07', result)

    def test_sanitize_limits_length(self):
        """Test that length is limited."""
        long_string = "a" * 1000
        result = sanitize_string(long_string, max_length=100)

        self.assertEqual(len(result), 100)

    def test_sanitize_preserves_newlines(self):
        """Test that newlines are preserved."""
        result = sanitize_string("line1\nline2")

        self.assertIn('\n', result)


class TestAddonNameValidation(TestCase):
    """Tests for addon name validation."""

    def test_validate_valid_addon_name(self):
        """Test validation passes for valid addon names."""
        valid_names = ['postgresql', 'my-addon', 'addon_123', 'redis-cache']

        for name in valid_names:
            result = sanitize_addon_name(name)
            self.assertEqual(result, name)

    def test_validate_invalid_addon_name(self):
        """Test validation fails for invalid addon names."""
        invalid_names = ['My Addon', 'addon@123', 'addon!', 'UPPERCASE']

        for name in invalid_names:
            with self.assertRaises(ValidationError):
                sanitize_addon_name(name)

    def test_sanitize_addon_name_strips_whitespace(self):
        """Test that whitespace is stripped from addon names."""
        result = sanitize_addon_name("  postgresql  ")

        self.assertEqual(result, "postgresql")


class TestRequestValidationDecorators(TestCase):
    """Tests for request validation decorators."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_validate_request_json_valid(self):
        """Test decorator allows valid JSON."""
        @validate_request_json(AddonSchemas.INSTALL_REQUEST_SCHEMA)
        def test_view(request):
            return JsonResponse({'success': True})

        request_data = {"config": {"port": 5432}}
        request = self.factory.post(
            '/api/test/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        request.user = self.user

        response = test_view(request)

        self.assertEqual(response.status_code, 200)

    def test_validate_request_json_invalid(self):
        """Test decorator rejects invalid JSON schema."""
        @validate_request_json(AddonSchemas.CONFIGURE_REQUEST_SCHEMA)
        def test_view(request):
            return JsonResponse({'success': True})

        # Missing required 'config' field
        request_data = {}
        request = self.factory.post(
            '/api/test/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        request.user = self.user

        response = test_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('Validation failed', data['error'])

    def test_validate_request_json_malformed(self):
        """Test decorator rejects malformed JSON."""
        @validate_request_json(AddonSchemas.INSTALL_REQUEST_SCHEMA)
        def test_view(request):
            return JsonResponse({'success': True})

        request = self.factory.post(
            '/api/test/',
            data='not valid json',
            content_type='application/json'
        )
        request.user = self.user

        response = test_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Invalid JSON', data['error'])

    def test_validate_addon_name_param_valid(self):
        """Test decorator allows valid addon names."""
        @validate_addon_name_param
        def test_view(request, name):
            return JsonResponse({'name': name})

        request = self.factory.get('/api/test/')
        request.user = self.user

        response = test_view(request, name='postgresql')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['name'], 'postgresql')

    def test_validate_addon_name_param_invalid(self):
        """Test decorator rejects invalid addon names."""
        @validate_addon_name_param
        def test_view(request, name):
            return JsonResponse({'name': name})

        request = self.factory.get('/api/test/')
        request.user = self.user

        response = test_view(request, name='Invalid Name!')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Invalid addon name', data['error'])


class TestPaginationValidation(TestCase):
    """Tests for pagination parameter validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_validate_pagination_defaults(self):
        """Test pagination defaults."""
        request = self.factory.get('/api/test/')

        params = validate_pagination_params(request)

        self.assertEqual(params['page'], 1)
        self.assertEqual(params['per_page'], 20)

    def test_validate_pagination_custom(self):
        """Test custom pagination parameters."""
        request = self.factory.get('/api/test/?page=2&per_page=50')

        params = validate_pagination_params(request)

        self.assertEqual(params['page'], 2)
        self.assertEqual(params['per_page'], 50)

    def test_validate_pagination_invalid_page(self):
        """Test validation fails for invalid page number."""
        request = self.factory.get('/api/test/?page=0')

        with self.assertRaises(ValidationError):
            validate_pagination_params(request)

    def test_validate_pagination_too_large_per_page(self):
        """Test validation fails for too large per_page."""
        request = self.factory.get('/api/test/?per_page=1000')

        with self.assertRaises(ValidationError):
            validate_pagination_params(request)

    def test_validate_pagination_non_integer(self):
        """Test validation fails for non-integer values."""
        request = self.factory.get('/api/test/?page=abc')

        with self.assertRaises(ValidationError):
            validate_pagination_params(request)


class TestConfigValidator(TestCase):
    """Tests for type-specific config validation."""

    def test_database_config_validation(self):
        """Test database-specific config validation."""
        # Valid config
        valid_config = {"max_connections": 100}
        errors = config_validator.validate('database', valid_config)
        self.assertEqual(len(errors), 0)

        # Invalid config - too few connections
        invalid_config = {"max_connections": 5}
        errors = config_validator.validate('database', invalid_config)
        self.assertGreater(len(errors), 0)

    def test_cache_config_validation(self):
        """Test cache-specific config validation."""
        # Valid config
        valid_config = {"memory_limit": "256MB"}
        errors = config_validator.validate('cache', valid_config)
        self.assertEqual(len(errors), 0)

        # Invalid config - wrong format
        invalid_config = {"memory_limit": "256"}
        errors = config_validator.validate('cache', invalid_config)
        self.assertGreater(len(errors), 0)
