"""
Custom exceptions for OmniModal.
"""

class OmniModalError(Exception):
    """Base exception for all OmniModal errors."""
    pass

class ProviderError(OmniModalError):
    """Raised when a provider fails."""
    pass

class RateLimitError(OmniModalError):
    """Raised when rate limit is exceeded."""
    pass

class AuthenticationError(OmniModalError):
    """Raised when authentication fails."""
    pass

class ConfigurationError(OmniModalError):
    """Raised when configuration is invalid."""
    pass

class CacheError(OmniModalError):
    """Raised when cache operation fails."""
    pass
