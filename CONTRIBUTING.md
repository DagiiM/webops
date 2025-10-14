# Contributing to WebOps

First off, thank you for considering contributing to WebOps! It's people like you that make WebOps such a great tool.

**Project Owner**: Douglas Mutethia ([GitHub](https://github.com/DagiiM))  
**Company**: Eleso Solutions  
**Repository**: [https://github.com/DagiiM/webops](https://github.com/DagiiM/webops)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include screenshots and animated GIFs if possible**
* **Include your environment details** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and explain which behavior you expected to see instead**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Follow the [Python style guide](#python-style-guide)
* Include appropriate test cases
* Update documentation as needed
* End all files with a newline
* Ensure all tests pass before submitting

## Development Process

### Setting Up Your Development Environment

```bash
# Clone the repository
git clone https://github.com/DagiiM/webops.git
cd webops

# Run the setup script
./setup.sh
```

### Running Tests

```bash
# Run all tests
cd control-panel
./venv/bin/python manage.py test

# Run specific app tests
./venv/bin/python manage.py test apps.deployments

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Code Style

#### Python Style Guide

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with strict type checking using **Pyright**:

* **Python Version**: 3.11+
* **Django Version**: 5.0+
* **Type Checking**: Pyright in strict mode
* **Maximum line length**: 100 characters
* **Type hints**: Required for all function signatures
* **Docstrings**: Google-style Python docstrings with type information
* **String formatting**: Use f-strings
* **Import order**: stdlib, third-party, local (separated by blank lines)

**Pyright Configuration** (`pyrightconfig.json`):
```json
{
    "typeCheckingMode": "strict",
    "reportMissingTypeStubs": false,
    "reportUnknownMemberType": false
}
```

Example:
```python
from typing import Optional, Dict, Any, Self
from pathlib import Path

from django.db import models
from celery import shared_task

from apps.core.models import BaseModel


def deploy_application(
    repo_url: str,
    branch: str = "main",
    env_vars: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Deploy application from GitHub repository.

    Args:
        repo_url: GitHub repository URL
        branch: Git branch to deploy
        env_vars: Environment variables for the application

    Returns:
        A dictionary containing deployment result with status and metadata.

    Raises:
        ValueError: If repo_url is invalid.
        ConnectionError: If unable to connect to repository.
    """
    if env_vars is None:
        env_vars = {}

    # Implementation here
    return {"status": "success", "deployment_id": "abc123"}


class DeploymentRepository:
    """A data access layer for deployment operations."""

    def __init__(self: Self, connection: models.Model) -> None:
        """Initialize the repository with a database connection.

        Args:
            connection: An active database connection object.
        """
        self.connection = connection
```
```

#### Frontend Style Guide

* **HTML**: Use semantic HTML5 elements
* **CSS**: Pure CSS3, no frameworks or preprocessors - implement custom CSS design system
* **JavaScript**: Vanilla ES6+, no frameworks or build tools
* **Icons**: Use SVG icons exclusively (no emojis)
* **Styling**: Consistent custom CSS design system with CSS variables for theming

Example:
```javascript
'use strict';

class DeploymentManager {
    constructor() {
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    async deployApp(formData) {
        try {
            const response = await fetch('/api/deployments/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Deployment failed:', error);
            throw error;
        }
    }
}
```

### Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

Example:
```
Add database backup functionality

- Implement pg_dump wrapper for PostgreSQL backups
- Add scheduled backup support via Celery
- Include backup restoration functionality
- Add tests for backup service

Fixes #123
```

### Branch Naming

* `feature/description` - New features
* `fix/description` - Bug fixes
* `docs/description` - Documentation changes
* `refactor/description` - Code refactoring
* `test/description` - Adding tests

## Project Structure

Please familiarize yourself with the project structure outlined in [CLAUDE.md](CLAUDE.md). This document contains essential information about:

* Project architecture
* Technology stack
* Development conventions
* Common tasks

## Testing Requirements

All contributions must include appropriate tests:

* **Unit tests** for individual functions and methods
* **Integration tests** for complete workflows
* **Minimum 80% code coverage** for new code

## Documentation Requirements

* Update relevant documentation in the `docs/` directory
* Add docstrings to all new functions and classes
* Update CHANGELOG.md for user-facing changes
* Update README.md if adding new features

## Review Process

1. **Submit Pull Request**: Create a PR with a clear description
2. **Automated Checks**: CI/CD will run tests and linters
3. **Code Review**: Maintainers will review your code
4. **Address Feedback**: Make requested changes
5. **Merge**: Once approved, your PR will be merged

## Questions?

Don't hesitate to ask! You can:

* Open an issue with your question
* Contact maintainers directly
* Join our community discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to WebOps! 🚀
