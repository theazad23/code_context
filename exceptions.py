class CodeContextError(Exception):
    """Base exception for code context related errors."""
    pass

class FileProcessingError(CodeContextError):
    """Raised when there's an error processing a file."""
    pass

class ConfigurationError(CodeContextError):
    """Raised when there's an invalid configuration."""
    pass