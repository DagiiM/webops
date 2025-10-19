from django.test import TestCase

from apps.core.utils import sanitize_deployment_name


class SanitizeDeploymentNameTests(TestCase):
    def test_simple_name_sanitizes_spaces_to_hyphen(self):
        self.assertEqual(sanitize_deployment_name("My App"), "my-app")

    def test_preserve_underscores_and_strip_trailing_hyphens(self):
        self.assertEqual(sanitize_deployment_name("My___App!!!"), "my___app")

    def test_trim_non_alphanumeric_edges(self):
        self.assertEqual(sanitize_deployment_name("----App==="), "app")

    def test_prefix_when_starting_with_non_alphanumeric(self):
        self.assertEqual(sanitize_deployment_name("__app"), "app-__app")

    def test_suffix_when_ending_with_non_alphanumeric(self):
        self.assertEqual(sanitize_deployment_name("app__"), "app__-app")

    def test_empty_or_whitespace_raises(self):
        with self.assertRaises(ValueError):
            sanitize_deployment_name("")
        with self.assertRaises(ValueError):
            sanitize_deployment_name("   ")

    def test_all_invalid_chars_raises(self):
        with self.assertRaises(ValueError):
            sanitize_deployment_name("!!!")

    def test_max_length_validation_raises(self):
        long_name = "a" * 101
        with self.assertRaises(ValueError):
            sanitize_deployment_name(long_name)

    def test_valid_name_unchanged(self):
        self.assertEqual(sanitize_deployment_name("my-app"), "my-app")

    def test_collapses_consecutive_hyphens(self):
        self.assertEqual(sanitize_deployment_name("My--App"), "my-app")

    def test_strip_leading_trailing_hyphens(self):
        self.assertEqual(sanitize_deployment_name("-My App-"), "my-app")

    def test_mixed_symbols_sanitizes_correctly(self):
        self.assertEqual(sanitize_deployment_name("App@@Name!!"), "app-name")
