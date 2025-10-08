"""FSD exception classes."""


class FSDError(Exception):
    """Base exception for all FSD errors."""

    pass


class TaskValidationError(FSDError):
    """Raised when task validation fails."""

    pass


class ConfigurationError(FSDError):
    """Raised when configuration is invalid."""

    pass


class ExecutionError(FSDError):
    """Raised when task execution fails."""

    pass


class ActivityTrackingError(FSDError):
    """Raised when activity tracking fails."""

    pass


class GitOperationError(FSDError):
    """Raised when git operations fail."""

    pass


class ClaudeExecutionError(ExecutionError):
    """Raised when Claude CLI execution fails."""

    pass


class ClaudeTimeoutError(ClaudeExecutionError):
    """Raised when Claude CLI execution times out."""

    pass


class ClaudeOutputParseError(ClaudeExecutionError):
    """Raised when Claude output cannot be parsed."""

    pass
