"""
Environment configuration parser and wizard for WebOps deployments.

Parses .env.example files and helps users configure environment variables.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class EnvVariable:
    """Represents an environment variable from .env.example."""
    key: str
    default_value: str
    comment: str = ""
    required: bool = True
    category: str = "general"

    def is_secret(self) -> bool:
        """Check if this variable likely contains sensitive data."""
        sensitive_keywords = [
            'key', 'secret', 'password', 'token', 'credential',
            'api_key', 'private', 'auth'
        ]
        return any(keyword in self.key.lower() for keyword in sensitive_keywords)

    def suggest_value(self) -> str:
        """Suggest a value based on the variable name."""
        if self.is_secret():
            if 'secret_key' in self.key.lower():
                return '<generate-random-key>'
            return '<set-your-secret-here>'

        if 'debug' in self.key.lower():
            return 'False'

        if 'allowed_hosts' in self.key.lower():
            return '*'

        if 'database_url' in self.key.lower():
            return 'postgresql://user:password@localhost/dbname'

        return self.default_value or ''


class EnvFileParser:
    """Parser for .env.example files."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def parse_env_example(self) -> Tuple[bool, List[EnvVariable], str]:
        """
        Parse .env.example file.

        Returns:
            Tuple of (found, variables_list, error_message)
        """
        env_example_path = self.repo_path / ".env.example"

        if not env_example_path.exists():
            return False, [], "No .env.example file found"

        try:
            content = env_example_path.read_text()
            variables = self._parse_content(content)
            return True, variables, ""
        except Exception as e:
            return False, [], f"Error parsing .env.example: {str(e)}"

    def _parse_content(self, content: str) -> List[EnvVariable]:
        """
        Parse .env file content into structured variables.

        Args:
            content: Content of .env file

        Returns:
            List of EnvVariable objects
        """
        variables = []
        current_comment = ""
        current_category = "general"

        lines = content.splitlines()

        for i, line in enumerate(lines):
            line = line.strip()

            # Skip empty lines
            if not line:
                current_comment = ""
                continue

            # Check for category comments (# Database Configuration)
            if line.startswith('#'):
                comment_text = line[1:].strip()

                # Category detection
                if any(keyword in comment_text.lower() for keyword in ['configuration', 'settings', 'setup']):
                    current_category = comment_text.replace('Configuration', '').replace('Settings', '').strip()

                current_comment = comment_text
                continue

            # Parse KEY=value
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Determine if required
                required = not (
                    'optional' in current_comment.lower() or
                    'leave empty' in current_comment.lower() or
                    value  # Has default value
                )

                variable = EnvVariable(
                    key=key,
                    default_value=value,
                    comment=current_comment,
                    required=required,
                    category=current_category
                )

                variables.append(variable)
                current_comment = ""

        return variables

    def categorize_variables(self, variables: List[EnvVariable]) -> Dict[str, List[EnvVariable]]:
        """
        Group variables by category.

        Args:
            variables: List of EnvVariable objects

        Returns:
            Dictionary mapping category names to variables
        """
        categories = {}

        for var in variables:
            category = var.category or 'General'

            if category not in categories:
                categories[category] = []

            categories[category].append(var)

        return categories

    def generate_env_dict(self, variables: List[EnvVariable], user_values: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Generate environment dictionary from variables.

        Args:
            variables: List of EnvVariable objects
            user_values: Optional dictionary of user-provided values

        Returns:
            Dictionary of environment variables
        """
        env_dict = {}
        user_values = user_values or {}

        for var in variables:
            if var.key in user_values:
                env_dict[var.key] = user_values[var.key]
            elif var.default_value:
                env_dict[var.key] = var.default_value
            else:
                env_dict[var.key] = var.suggest_value()

        return env_dict

    def validate_required_vars(self, variables: List[EnvVariable], provided_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate that all required variables are provided.

        Args:
            variables: List of EnvVariable objects
            provided_vars: Dictionary of provided values

        Returns:
            Tuple of (all_valid, missing_variables)
        """
        missing = []

        for var in variables:
            if var.required and var.key not in provided_vars:
                missing.append(var.key)
            elif var.required and not provided_vars.get(var.key):
                missing.append(var.key)

        return len(missing) == 0, missing


class EnvWizard:
    """Interactive environment variable configuration wizard."""

    def __init__(self, repo_path: Path):
        self.parser = EnvFileParser(repo_path)

    def get_wizard_data(self) -> Dict[str, any]:
        """
        Get all data needed for the .env wizard.

        Returns:
            Dictionary with wizard data
        """
        found, variables, error = self.parser.parse_env_example()

        if not found:
            return {
                'available': False,
                'error': error,
                'variables': [],
                'categories': {}
            }

        categorized = self.parser.categorize_variables(variables)

        return {
            'available': True,
            'error': '',
            'variables': [
                {
                    'key': var.key,
                    'default_value': var.default_value,
                    'comment': var.comment,
                    'required': var.required,
                    'is_secret': var.is_secret(),
                    'suggested_value': var.suggest_value(),
                    'category': var.category
                }
                for var in variables
            ],
            'categories': {
                category: [
                    {
                        'key': var.key,
                        'default_value': var.default_value,
                        'comment': var.comment,
                        'required': var.required,
                        'is_secret': var.is_secret(),
                        'suggested_value': var.suggest_value()
                    }
                    for var in vars_list
                ]
                for category, vars_list in categorized.items()
            }
        }

    def apply_values(self, variables: List[EnvVariable], user_values: Dict[str, str]) -> Dict[str, str]:
        """
        Apply user values and generate final env dictionary.

        Args:
            variables: List of EnvVariable objects
            user_values: User-provided values

        Returns:
            Final environment dictionary
        """
        return self.parser.generate_env_dict(variables, user_values)


def parse_env_example(repo_path: Path) -> Tuple[bool, List[EnvVariable], str]:
    """
    Parse .env.example file from repository.

    Args:
        repo_path: Path to repository

    Returns:
        Tuple of (found, variables, error_message)
    """
    parser = EnvFileParser(repo_path)
    return parser.parse_env_example()
