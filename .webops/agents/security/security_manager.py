"""
Security Manager

Provides comprehensive security features for the AI Agent System.
"""

import hashlib
import hmac
import secrets
import base64
import json
import re
import time
import jwt
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
import asyncio
from urllib.parse import urlparse
import bleach


class SecurityLevel(Enum):
    """Security levels."""
    
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TokenType(Enum):
    """Types of security tokens."""
    
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    VERIFY = "verify"
    API = "api"


class Permission(Enum):
    """Permission types."""
    
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    MANAGE = "manage"


@dataclass
class SecurityContext:
    """Security context for operations."""
    
    user_id: Optional[str] = None
    permissions: List[Permission] = field(default_factory=list)
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessRule:
    """Access control rule."""
    
    id: str
    name: str
    pattern: str  # URL pattern or resource pattern
    permissions: List[Permission]
    conditions: Dict[str, Any] = field(default_factory=dict)
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    rate_limit: Optional[Dict[str, Any]] = None
    
    def matches(self, resource: str) -> bool:
        """Check if rule matches resource."""
        import fnmatch
        return fnmatch.fnmatch(resource, self.pattern)


@dataclass
class AuditEntry:
    """Security audit log entry."""
    
    id: str
    timestamp: datetime
    event_type: str
    user_id: Optional[str]
    action: str
    resource: str
    result: str  # success, failure, denied
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0


class EncryptionManager:
    """Handles encryption and decryption operations."""
    
    def __init__(self, master_key: Optional[str] = None):
        """Initialize encryption manager."""
        self.master_key = master_key or secrets.token_urlsafe(32)
        self.logger = logging.getLogger("encryption")
        
        # Derive encryption key from master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'webops_agent_salt_2023',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        self.fernet = Fernet(key)
    
    def encrypt(self, data: Union[str, bytes], use_fernet: bool = True) -> str:
        """Encrypt data."""
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if use_fernet:
                encrypted = self.fernet.encrypt(data)
                return base64.urlsafe_b64encode(encrypted).decode('utf-8')
            else:
                # Simple base64 encoding for non-sensitive data
                return base64.b64encode(data).decode('utf-8')
                
        except Exception as e:
            self.logger.error(f"Encryption error: {e}")
            raise SecurityError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: str, use_fernet: bool = True) -> str:
        """Decrypt data."""
        try:
            if use_fernet:
                encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
                decrypted = self.fernet.decrypt(encrypted_bytes)
                return decrypted.decode('utf-8')
            else:
                # Simple base64 decoding
                decrypted = base64.b64decode(encrypted_data.encode())
                return decrypted.decode('utf-8')
                
        except Exception as e:
            self.logger.error(f"Decryption error: {e}")
            raise SecurityError(f"Failed to decrypt data: {e}")
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Dict[str, str]:
        """Hash password using secure algorithm."""
        if salt is None:
            salt = secrets.token_bytes(32)
        
        # Use PBKDF2 with SHA256
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        
        return {
            'password_hash': base64.b64encode(pwdhash).decode('utf-8'),
            'salt': base64.b64encode(salt).decode('utf-8')
        }
    
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash."""
        try:
            salt_bytes = base64.b64decode(salt.encode('utf-8'))
            pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000)
            provided_hash = base64.b64decode(password_hash.encode('utf-8'))
            
            return hmac.compare_digest(pwdhash, provided_hash)
            
        except Exception as e:
            self.logger.error(f"Password verification error: {e}")
            return False
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(length)
    
    def generate_jwt_token(self, payload: Dict[str, Any], secret: Optional[str] = None, 
                          expires_in: int = 3600) -> str:
        """Generate JWT token."""
        secret = secret or self.master_key
        
        payload.update({
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        })
        
        return jwt.encode(payload, secret, algorithm='HS256')
    
    def verify_jwt_token(self, token: str, secret: Optional[str] = None) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        secret = secret or self.master_key
        
        try:
            return jwt.decode(token, secret, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise SecurityError("Token has expired")
        except jwt.InvalidTokenError:
            raise SecurityError("Invalid token")


class SecurityValidator:
    """Validates various security aspects."""
    
    def __init__(self):
        """Initialize security validator."""
        self.logger = logging.getLogger("security_validator")
        
        # Common dangerous patterns
        self.dangerous_patterns = [
            r'<script.*?>.*?</script>',  # XSS
            r'javascript:',  # JavaScript injection
            r'on\w+\s*=',  # Event handlers
            r'eval\s*\(',  # Eval functions
            r'exec\s*\(',  # Exec functions
            r'import\s+os',  # OS imports
            r'__import__',  # Dynamic imports
            r'subprocess',  # Subprocess calls
            r'file\s*=\s*open',  # File operations
            r'\.\./',  # Path traversal
        ]
        
        # SQL injection patterns
        self.sql_patterns = [
            r'(\bor\b|\band\b)\s+[\'"]?\w+[\'"]?\s*=\s*[\'"]?\w+[\'"]?',  # Basic injection
            r'[\'"];\s*--',  # Comment injection
            r'union\s+select',  # Union injection
            r'drop\s+table',  # Drop table
            r'insert\s+into',  # Insert injection
        ]
    
    def sanitize_input(self, input_str: str, allowed_tags: List[str] = None) -> str:
        """Sanitize user input to prevent XSS."""
        # Remove dangerous HTML tags and attributes
        allowed_tags = allowed_tags or ['p', 'br', 'strong', 'em', 'u']
        
        return bleach.clean(
            input_str,
            tags=allowed_tags,
            attributes={},
            protocols=['http', 'https', 'mailto'],
            strip=True
        )
    
    def validate_url(self, url: str, allowed_schemes: List[str] = None) -> bool:
        """Validate URL for security."""
        try:
            parsed = urlparse(url)
            allowed_schemes = allowed_schemes or ['http', 'https']
            
            if parsed.scheme not in allowed_schemes:
                return False
            
            # Block localhost and private IPs in production
            if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"URL validation error: {e}")
            return False
    
    def check_xss(self, input_str: str) -> bool:
        """Check for XSS patterns."""
        for pattern in self.dangerous_patterns[:4]:  # XSS specific patterns
            if re.search(pattern, input_str, re.IGNORECASE):
                return True
        return False
    
    def check_sql_injection(self, input_str: str) -> bool:
        """Check for SQL injection patterns."""
        for pattern in self.sql_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return True
        return False
    
    def check_path_traversal(self, input_str: str) -> bool:
        """Check for path traversal attacks."""
        dangerous_patterns = [
            r'\.\./',
            r'\.\.\\',
            r'%2e%2e%2f',
            r'%2e%2e%5c',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return True
        return False
    
    def validate_input(self, input_str: str, checks: List[str] = None) -> Dict[str, Any]:
        """Comprehensive input validation."""
        checks = checks or ['xss', 'sql', 'path_traversal']
        
        results = {
            'valid': True,
            'sanitized': input_str,
            'issues': []
        }
        
        # Check for XSS
        if 'xss' in checks and self.check_xss(input_str):
            results['issues'].append('XSS pattern detected')
            results['valid'] = False
        
        # Check for SQL injection
        if 'sql' in checks and self.check_sql_injection(input_str):
            results['issues'].append('SQL injection pattern detected')
            results['valid'] = False
        
        # Check for path traversal
        if 'path_traversal' in checks and self.check_path_traversal(input_str):
            results['issues'].append('Path traversal pattern detected')
            results['valid'] = False
        
        # Sanitize if needed
        if results['issues']:
            results['sanitized'] = self.sanitize_input(input_str)
        
        return results
    
    def validate_file_upload(self, filename: str, content_type: str, 
                           allowed_extensions: List[str] = None,
                           max_size: int = 10 * 1024 * 1024) -> Dict[str, Any]:
        """Validate file upload."""
        results = {
            'valid': True,
            'errors': []
        }
        
        # Check extension
        allowed_extensions = allowed_extensions or ['.txt', '.pdf', '.doc', '.docx', '.jpg', '.png']
        file_ext = '.' + filename.split('.')[-1].lower()
        
        if file_ext not in allowed_extensions:
            results['valid'] = False
            results['errors'].append(f'File extension {file_ext} not allowed')
        
        # Check for dangerous filenames
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in filename for char in dangerous_chars):
            results['valid'] = False
            results['errors'].append('Dangerous characters in filename')
        
        return results


class AccessControl:
    """Handles access control and permissions."""
    
    def __init__(self):
        """Initialize access control."""
        self.rules: List[AccessRule] = []
        self.logger = logging.getLogger("access_control")
    
    def add_rule(self, rule: AccessRule) -> None:
        """Add access control rule."""
        self.rules.append(rule)
        self.logger.info(f"Added access rule: {rule.name}")
    
    def check_access(self, context: SecurityContext, resource: str, 
                    operation: str) -> bool:
        """Check if access is allowed."""
        # Find matching rules
        matching_rules = [rule for rule in self.rules if rule.matches(resource)]
        
        if not matching_rules:
            # Default deny
            return False
        
        # Check each rule
        for rule in matching_rules:
            # Check permissions
            required_permission = Permission(operation.upper())
            if required_permission in rule.permissions:
                # Check conditions
                if self._check_conditions(rule.conditions, context):
                    # Check rate limits
                    if not self._check_rate_limit(rule, context):
                        self.logger.warning(f"Rate limit exceeded for {context.user_id}")
                        return False
                    
                    return True
        
        return False
    
    def get_required_permissions(self, resource: str, operation: str) -> List[Permission]:
        """Get required permissions for resource and operation."""
        matching_rules = [rule for rule in self.rules if rule.matches(resource)]
        
        permissions = set()
        for rule in matching_rules:
            required_permission = Permission(operation.upper())
            if required_permission in rule.permissions:
                permissions.add(required_permission)
        
        return list(permissions)
    
    def _check_conditions(self, conditions: Dict[str, Any], 
                         context: SecurityContext) -> bool:
        """Check if conditions are satisfied."""
        for key, expected_value in conditions.items():
            actual_value = getattr(context, key, None)
            
            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            else:
                if actual_value != expected_value:
                    return False
        
        return True
    
    def _check_rate_limit(self, rule: AccessRule, context: SecurityContext) -> bool:
        """Check rate limits."""
        if not rule.rate_limit:
            return True
        
        # This is a simplified implementation
        # In practice, you'd want to track requests per user/IP
        return True


class SecurityAudit:
    """Security audit logging."""
    
    def __init__(self, max_entries: int = 10000):
        """Initialize security audit."""
        self.entries: List[AuditEntry] = []
        self.max_entries = max_entries
        self.logger = logging.getLogger("security_audit")
    
    def log_event(self, event_type: str, action: str, resource: str,
                  context: SecurityContext, result: str = "success",
                  details: Dict[str, Any] = None) -> None:
        """Log security event."""
        entry = AuditEntry(
            id=secrets.token_hex(16),
            timestamp=datetime.now(),
            event_type=event_type,
            user_id=context.user_id,
            action=action,
            resource=resource,
            result=result,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            details=details or {}
        )
        
        # Calculate risk score
        entry.risk_score = self._calculate_risk_score(entry)
        
        self.entries.append(entry)
        
        # Trim old entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        
        # Log to regular logger
        log_level = logging.WARNING if entry.risk_score > 0.7 else logging.INFO
        self.logger.log(log_level, f"Security event: {entry.event_type} - {entry.result}")
    
    def get_recent_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit entries."""
        recent_entries = self.entries[-limit:]
        return [asdict(entry) for entry in recent_entries]
    
    def get_entries_by_user(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit entries for specific user."""
        user_entries = [entry for entry in self.entries if entry.user_id == user_id]
        return [asdict(entry) for entry in user_entries[-limit:]]
    
    def get_entries_by_type(self, event_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit entries by type."""
        type_entries = [entry for entry in self.entries if entry.event_type == event_type]
        return [asdict(entry) for entry in type_entries[-limit:]]
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security audit summary."""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        recent_entries = [entry for entry in self.entries if entry.timestamp >= last_24h]
        weekly_entries = [entry for entry in self.entries if entry.timestamp >= last_7d]
        
        summary = {
            'total_events': len(self.entries),
            'events_last_24h': len(recent_entries),
            'events_last_7d': len(weekly_entries),
            'failed_events': len([e for e in self.entries if e.result == 'failure']),
            'high_risk_events': len([e for e in self.entries if e.risk_score > 0.7]),
            'unique_users': len(set(entry.user_id for entry in self.entries if entry.user_id)),
            'top_actions': {},
            'security_level_distribution': {},
            'risk_score_average': 0.0
        }
        
        # Top actions
        action_counts = {}
        for entry in self.entries:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1
        
        summary['top_actions'] = dict(sorted(action_counts.items(), 
                                           key=lambda x: x[1], reverse=True)[:10])
        
        # Risk score average
        if self.entries:
            summary['risk_score_average'] = sum(entry.risk_score for entry in self.entries) / len(self.entries)
        
        return summary
    
    def _calculate_risk_score(self, entry: AuditEntry) -> float:
        """Calculate risk score for audit entry."""
        score = 0.0
        
        # Failed events have higher risk
        if entry.result == 'failure':
            score += 0.3
        
        # Certain actions are higher risk
        high_risk_actions = ['delete', 'admin', 'execute', 'system_access']
        if entry.action in high_risk_actions:
            score += 0.4
        
        # Missing user ID increases risk
        if not entry.user_id:
            score += 0.2
        
        # Time-based risk (after hours)
        hour = entry.timestamp.hour
        if hour < 6 or hour > 22:  # Outside normal hours
            score += 0.1
        
        return min(1.0, score)


class SecurityError(Exception):
    """Security-related exception."""
    pass


class SecurityManager:
    """Main security manager orchestrating all security components."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize security manager."""
        self.config = config or {}
        self.logger = logging.getLogger("security_manager")
        
        # Initialize components
        self.encryption = EncryptionManager(self.config.get('master_key'))
        self.validator = SecurityValidator()
        self.access_control = AccessControl()
        self.audit = SecurityAudit(self.config.get('max_audit_entries', 10000))
        
        # Security settings
        self.default_security_level = SecurityLevel.MEDIUM
        self.enable_rate_limiting = self.config.get('enable_rate_limiting', True)
        self.enable_audit_logging = self.config.get('enable_audit_logging', True)
        
        # Rate limiting storage
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        
        # Load default security rules
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default security rules."""
        # Admin access
        self.access_control.add_rule(AccessRule(
            id="admin_access",
            name="Admin Access",
            pattern="admin/*",
            permissions=[Permission.ADMIN, Permission.MANAGE],
            security_level=SecurityLevel.HIGH
        ))
        
        # API access
        self.access_control.add_rule(AccessRule(
            id="api_access",
            name="API Access",
            pattern="api/*",
            permissions=[Permission.READ, Permission.WRITE],
            security_level=SecurityLevel.MEDIUM,
            rate_limit={'requests': 1000, 'window': 3600}  # 1000 req/hour
        ))
        
        # Public access
        self.access_control.add_rule(AccessRule(
            id="public_access",
            name="Public Access",
            pattern="public/*",
            permissions=[Permission.READ],
            security_level=SecurityLevel.LOW
        ))
    
    async def authenticate_user(self, username: str, password: str, 
                              ip_address: str = None) -> Optional[str]:
        """Authenticate user credentials."""
        # This is a simplified implementation
        # In practice, you'd verify against a user database
        context = SecurityContext(
            user_id=username,
            ip_address=ip_address
        )
        
        # Log authentication attempt
        if self.enable_audit_logging:
            self.audit.log_event(
                "authentication", "login", "user", context, 
                result="success" if password == "valid" else "failure"
            )
        
        # Simple authentication (replace with proper implementation)
        if password == "valid":
            # Generate session token
            session_token = self.encryption.generate_jwt_token({
                'user_id': username,
                'permissions': ['read', 'write']
            })
            return session_token
        
        return None
    
    async def validate_session(self, token: str) -> Optional[SecurityContext]:
        """Validate session token."""
        try:
            payload = self.encryption.verify_jwt_token(token)
            
            return SecurityContext(
                user_id=payload.get('user_id'),
                permissions=[Permission(p) for p in payload.get('permissions', [])],
                session_id=token,
                security_level=SecurityLevel.MEDIUM
            )
            
        except SecurityError as e:
            self.logger.warning(f"Invalid session token: {e}")
            return None
    
    async def authorize_action(self, context: SecurityContext, resource: str, 
                             action: str) -> bool:
        """Authorize an action."""
        authorized = self.access_control.check_access(context, resource, action)
        
        if self.enable_audit_logging:
            self.audit.log_event(
                "authorization", action, resource, context,
                result="success" if authorized else "denied"
            )
        
        return authorized
    
    async def validate_and_sanitize_input(self, input_str: str, 
                                         security_level: SecurityLevel = None) -> str:
        """Validate and sanitize input."""
        security_level = security_level or self.default_security_level
        
        # Determine validation checks based on security level
        checks = ['xss', 'sql']
        if security_level.value >= SecurityLevel.HIGH.value:
            checks.append('path_traversal')
        
        # Validate input
        result = self.validator.validate_input(input_str, checks)
        
        if not result['valid']:
            if self.enable_audit_logging:
                context = SecurityContext()  # Anonymous context
                self.audit.log_event(
                    "input_validation", "validate", "input", context,
                    result="failure", details={'issues': result['issues']}
                )
            
            raise SecurityError(f"Input validation failed: {result['issues']}")
        
        return result['sanitized']
    
    async def encrypt_sensitive_data(self, data: str, context: SecurityContext = None) -> str:
        """Encrypt sensitive data."""
        # Log encryption operation
        if self.enable_audit_logging and context:
            self.audit.log_event(
                "encryption", "encrypt", "sensitive_data", context, result="success"
            )
        
        return self.encryption.encrypt(data)
    
    async def decrypt_sensitive_data(self, encrypted_data: str, 
                                    context: SecurityContext = None) -> str:
        """Decrypt sensitive data."""
        # Log decryption operation
        if self.enable_audit_logging and context:
            self.audit.log_event(
                "decryption", "decrypt", "sensitive_data", context, result="success"
            )
        
        return self.encryption.decrypt(encrypted_data)
    
    def create_secure_token(self, token_type: TokenType, user_id: str, 
                          expires_in: int = 3600) -> str:
        """Create secure token."""
        payload = {
            'token_type': token_type.value,
            'user_id': user_id,
        }
        
        return self.encryption.generate_jwt_token(payload, expires_in=expires_in)
    
    def verify_secure_token(self, token: str, token_type: TokenType) -> Optional[Dict[str, Any]]:
        """Verify secure token."""
        try:
            payload = self.encryption.verify_jwt_token(token)
            
            if payload.get('token_type') != token_type.value:
                return None
            
            return payload
            
        except SecurityError:
            return None
    
    async def check_rate_limit(self, identifier: str, operation: str, 
                             limit: int = 100, window: int = 3600) -> bool:
        """Check rate limiting."""
        if not self.enable_rate_limiting:
            return True
        
        now = time.time()
        key = f"{identifier}:{operation}"
        
        if key not in self._rate_limits:
            self._rate_limits[key] = {'count': 0, 'reset_time': now + window}
        
        # Reset if window has passed
        if now > self._rate_limits[key]['reset_time']:
            self._rate_limits[key] = {'count': 0, 'reset_time': now + window}
        
        # Check limit
        if self._rate_limits[key]['count'] >= limit:
            return False
        
        self._rate_limits[key]['count'] += 1
        return True
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get comprehensive security summary."""
        return {
            'audit_summary': self.audit.get_security_summary(),
            'encryption_status': {
                'key_rotation_needed': False,  # Placeholder
                'encryption_enabled': True
            },
            'access_control': {
                'total_rules': len(self.access_control.rules),
                'default_security_level': self.default_security_level.value
            },
            'rate_limiting': {
                'enabled': self.enable_rate_limiting,
                'active_limits': len(self._rate_limits)
            }
        }


# Global security manager instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


async def setup_security(config: Dict[str, Any] = None) -> SecurityManager:
    """Setup security manager with configuration."""
    manager = get_security_manager()
    if config:
        # Update configuration
        manager.config.update(config)
    
    return manager


# Convenience functions
async def authenticate(username: str, password: str, ip_address: str = None) -> Optional[str]:
    """Convenience function for authentication."""
    manager = get_security_manager()
    return await manager.authenticate_user(username, password, ip_address)


async def authorize(context: SecurityContext, resource: str, action: str) -> bool:
    """Convenience function for authorization."""
    manager = get_security_manager()
    return await manager.authorize_action(context, resource, action)


async def validate_input(input_str: str, security_level: SecurityLevel = None) -> str:
    """Convenience function for input validation."""
    manager = get_security_manager()
    return await manager.validate_and_sanitize_input(input_str, security_level)


if __name__ == "__main__":
    async def main():
        """Example usage of security manager."""
        # Setup security
        manager = await setup_security({
            'enable_audit_logging': True,
            'enable_rate_limiting': True,
            'max_audit_entries': 1000
        })
        
        # Test authentication
        token = await manager.authenticate_user("testuser", "valid")
        if token:
            print(f"Authentication successful: {token[:20]}...")
            
            # Validate session
            context = await manager.validate_session(token)
            if context:
                print(f"Session valid for user: {context.user_id}")
                
                # Test authorization
                authorized = await manager.authorize_action(context, "api/data", "read")
                print(f"Authorization result: {authorized}")
                
                # Test input validation
                try:
                    sanitized = await manager.validate_and_sanitize_input("<script>alert('xss')</script>Hello")
                    print(f"Sanitized input: {sanitized}")
                except SecurityError as e:
                    print(f"Input validation failed: {e}")
                
                # Test encryption
                encrypted = await manager.encrypt_sensitive_data("sensitive data", context)
                decrypted = await manager.decrypt_sensitive_data(encrypted, context)
                print(f"Encryption test: {decrypted}")
        
        # Get security summary
        summary = manager.get_security_summary()
        print(f"Security Summary: {json.dumps(summary, indent=2, default=str)}")
    
    asyncio.run(main())