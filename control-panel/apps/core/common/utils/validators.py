"""
Validation utilities for WebOps.

"Input Validation" section
"""

import re
from typing import Optional
from urllib.parse import urlparse


def validate_repo_url(url: str) -> bool:
    """
    Validate GitHub repository URL.

    Args:
        url: Repository URL to validate

    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False

    # Support both HTTPS and SSH GitHub URLs
    patterns = [
        r'^https://github\.com/[\w-]+/[\w.-]+(?:\.git)?$',
        r'^git@github\.com:[\w-]+/[\w.-]+(?:\.git)?$',
    ]

    return any(re.match(pattern, url) for pattern in patterns)


def validate_domain(domain: str) -> bool:
    """
    Validate domain name format.

    Args:
        domain: Domain name to validate

    Returns:
        True if valid, False otherwise
    """
    if not domain:
        return False

    # Basic domain validation pattern
    pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain))


def validate_app_name(name: str) -> bool:
    """
    Validate application name (alphanumeric, hyphens, underscores).

    Args:
        name: Application name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or len(name) > 100:
        return False

    pattern = r'^[a-z0-9][a-z0-9-_]*[a-z0-9]$'
    return bool(re.match(pattern, name))


def sanitize_deployment_name(name: str) -> str:
    """
    Sanitize deployment name by converting to lowercase and replacing invalid characters.

    Args:
        name: Raw deployment name to sanitize

    Returns:
        Sanitized deployment name

    Raises:
        ValueError: If the name cannot be sanitized to a valid format
    """
    if not name or not name.strip():
        raise ValueError("Deployment name cannot be empty")
    
    # Convert to lowercase and strip whitespace
    sanitized = name.strip().lower()
    
    # Replace spaces and special characters with hyphens
    sanitized = re.sub(r'[^a-z0-9-_]', '-', sanitized)
    
    # Remove consecutive hyphens
    sanitized = re.sub(r'-+', '-', sanitized)
    
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    
    # Ensure it starts and ends with alphanumeric
    if not sanitized:
        raise ValueError("Deployment name must contain at least one alphanumeric character")
    
    if not re.match(r'^[a-z0-9]', sanitized):
        sanitized = 'app-' + sanitized
    
    if not re.search(r'[a-z0-9]$', sanitized):
        sanitized = sanitized + '-app'
    
    # Validate final result
    if not validate_app_name(sanitized):
        raise ValueError(f"Invalid deployment name format: '{name}'")
    
    return sanitized

_GH_OWNER = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$')
_GH_REPO = re.compile(r'^[\w.-]{1,100}$')
_GH_BRANCH = re.compile(r'^[\w./-]{1,200}$')
_GH_SUBPAGES = {'tree', 'blob', 'commits', 'commit', 'releases', 'issues', 'pull', 'pulls', 'actions', 'wiki', 'tags'}


def parse_github_repo(raw: str):
    """Parse the many ways people write a GitHub repository.

    Accepts https://github.com/o/r, with or without a trailing slash, ``.git``, ``www.``, a
    ``/tree/<branch>`` (or other sub-page) suffix, a query string, no scheme (``github.com/o/r``),
    a bare ``owner/repo``, and the SSH form ``git@github.com:o/r.git``.

    Returns ``{'owner', 'repo', 'branch', 'ssh', 'url'}`` or ``None``. ``url`` is canonical
    (``https://github.com/o/r``) except for SSH input, which is returned unchanged so existing SSH
    deployments keep working. ``branch`` is set only for ``/tree/<branch>`` URLs.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or len(text) > 400 or any(ch.isspace() for ch in text):
        return None
    m = re.match(r'^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$', text, re.I)
    if m:
        owner, repo = m.group(1), m.group(2)
        if _GH_OWNER.match(owner) and _GH_REPO.match(repo) and repo not in ('.', '..'):
            return {'owner': owner, 'repo': repo, 'branch': None, 'ssh': True, 'url': text}
        return None
    text = re.sub(r'[?#].*$', '', text)
    text = re.sub(r'^https?://', '', text, flags=re.I)
    text = re.sub(r'^www\.', '', text, flags=re.I)
    if text.lower().startswith('github.com/'):
        text = text[len('github.com/'):]
    elif '.' in text.split('/')[0]:
        return None  # some other host
    parts = [p for p in text.strip('/').split('/') if p != '']
    if len(parts) < 2:
        return None
    owner, repo = parts[0], re.sub(r'\.git$', '', parts[1], flags=re.I)
    if not _GH_OWNER.match(owner) or not _GH_REPO.match(repo) or repo in ('.', '..'):
        return None
    rest = parts[2:]
    branch = None
    if rest:
        if rest[0].lower() not in _GH_SUBPAGES:
            return None  # e.g. owner/repo/extra: not a repository reference
        if rest[0].lower() == 'tree' and len(rest) > 1:
            candidate = '/'.join(rest[1:])
            if _GH_BRANCH.match(candidate) and '..' not in candidate:
                branch = candidate
    return {'owner': owner, 'repo': repo, 'branch': branch, 'ssh': False,
            'url': f'https://github.com/{owner}/{repo}'}


def normalize_github_repo_url(raw: str):
    """Canonical repository URL for any accepted spelling, or None."""
    parsed = parse_github_repo(raw)
    return parsed['url'] if parsed else None
