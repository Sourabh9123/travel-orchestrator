from typing import Any, ClassVar


class AppError(Exception):
    """Base application exception with stable API error metadata."""

    code: ClassVar[str] = "app_error"
    status_code: ClassVar[int] = 400

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        """Create an application exception with optional error metadata overrides."""

        super().__init__(message)
        self.message = message
        self.code = code or type(self).code
        self.details = details
        self.status_code = status_code or type(self).status_code


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    code: str = "not_found"
    status_code: int = 404


class ValidationFailure(AppError):
    """Raised when user input or workflow state fails validation."""

    code: str = "validation_failure"
    status_code: int = 422


class WorkflowExecutionError(AppError):
    """Raised when orchestration cannot complete a workflow safely."""

    code: str = "workflow_execution_error"
    status_code: int = 500


class AgentExecutionError(AppError):
    """Raised when an agent fails to produce a valid output."""

    code: str = "agent_execution_error"
    status_code: int = 500


class ToolExecutionError(AppError):
    """Raised when a provider tool fails, times out, or is rate-limited."""

    code: str = "tool_execution_error"
    status_code: int = 502


class MemoryStateError(AppError):
    """Raised when shared workflow memory is missing or inconsistent."""

    code: str = "memory_state_error"
    status_code: int = 409


class BookingError(AppError):
    """Raised when a booking provider operation cannot be completed."""

    code: str = "booking_error"
    status_code: int = 502


class ExternalServiceError(AppError):
    """Raised when an external dependency returns an unusable result."""

    code: str = "external_service_error"
    status_code: int = 502
