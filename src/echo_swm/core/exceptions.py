class EchoError(Exception):
    """Base domain exception."""


class ConfigurationError(EchoError):
    """Raised when a runtime setting is missing or invalid."""


class LeakageError(EchoError):
    """Raised when a feature was unavailable at prediction time."""


class ReplayError(EchoError):
    """Raised when replay hashes do not match the original run."""


class LLMResponseError(EchoError):
    """Raised when a provider fails or returns invalid structured output."""
