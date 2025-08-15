"""
Custom exceptions for IBAutomater
"""


class IBAutomaterError(Exception):
    """Base exception for IBAutomater errors"""
    
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class ProcessError(IBAutomaterError):
    """Exception raised when process management fails"""
    pass


class AuthenticationError(IBAutomaterError):
    """Exception raised when authentication fails"""
    pass


class UIError(IBAutomaterError):
    """Exception raised when UI automation fails"""
    pass


class ConfigurationError(IBAutomaterError):
    """Exception raised when configuration is invalid"""
    pass


class TimeoutError(IBAutomaterError):
    """Exception raised when operations timeout"""
    pass


class TwoFactorError(AuthenticationError):
    """Exception raised when 2FA fails"""
    pass

