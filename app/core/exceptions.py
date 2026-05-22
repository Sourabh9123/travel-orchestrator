from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    message: str
    code: str = "app_error"
    details: dict[str, Any] | None = None


class NotFoundError(AppError):
    code: str = "not_found"


class ValidationFailure(AppError):
    code: str = "validation_failure"


class WorkflowExecutionError(AppError):
    code: str = "workflow_execution_error"


class ToolExecutionError(AppError):
    code: str = "tool_execution_error"
