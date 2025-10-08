"""Retry strategy for handling task execution failures.

This module provides configurable retry logic for validation failures
and execution errors.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RetryDecision(Enum):
    """Decision on whether to retry a failed task."""

    RETRY = "retry"  # Retry the task
    FAIL = "fail"  # Mark task as failed
    COMPLETE = "complete"  # Mark task as complete despite issues


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    """Maximum number of retry attempts"""

    retry_on_validation_failure: bool = True
    """Whether to retry when validation fails"""

    retry_on_execution_error: bool = False
    """Whether to retry on execution errors (typically not retryable)"""

    allow_partial_success: bool = False
    """Whether to complete task if some criteria pass"""


class RetryStrategy:
    """Determines retry behavior for task execution failures."""

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize retry strategy.

        Args:
            config: Retry configuration (uses defaults if None)
        """
        self.config = config or RetryConfig()

    def should_retry(
        self,
        current_retry_count: int,
        validation_passed: bool,
        execution_error: Optional[str] = None,
        partial_success: bool = False,
    ) -> RetryDecision:
        """Determine if task should be retried.

        Args:
            current_retry_count: Number of retries so far
            validation_passed: Whether validation passed
            execution_error: Error message if execution failed
            partial_success: Whether some validation criteria passed

        Returns:
            RetryDecision indicating what action to take
        """
        # If validation passed, complete
        if validation_passed:
            return RetryDecision.COMPLETE

        # Check if we've exhausted retries
        if current_retry_count >= self.config.max_retries:
            # Check if partial success is acceptable
            if partial_success and self.config.allow_partial_success:
                return RetryDecision.COMPLETE
            return RetryDecision.FAIL

        # If there was an execution error
        if execution_error:
            if self.config.retry_on_execution_error:
                return RetryDecision.RETRY
            else:
                return RetryDecision.FAIL

        # Validation failure
        if self.config.retry_on_validation_failure:
            return RetryDecision.RETRY
        else:
            return RetryDecision.FAIL

    def get_retry_message(
        self,
        decision: RetryDecision,
        current_retry_count: int,
        reason: Optional[str] = None,
    ) -> str:
        """Get a human-readable message about the retry decision.

        Args:
            decision: Retry decision
            current_retry_count: Current retry count
            reason: Optional reason for the decision

        Returns:
            Message string
        """
        if decision == RetryDecision.RETRY:
            remaining = self.config.max_retries - current_retry_count
            msg = f"Retrying task (attempt {current_retry_count + 1}/{self.config.max_retries + 1})"
            if reason:
                msg += f": {reason}"
            return msg

        elif decision == RetryDecision.FAIL:
            msg = f"Task failed after {current_retry_count} retries"
            if reason:
                msg += f": {reason}"
            return msg

        elif decision == RetryDecision.COMPLETE:
            if current_retry_count > 0:
                msg = f"Task completed after {current_retry_count} retries"
            else:
                msg = "Task completed successfully"
            if reason:
                msg += f" ({reason})"
            return msg

        return "Unknown retry decision"

    def calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate delay before retry (in seconds).

        Uses exponential backoff with jitter.

        Args:
            retry_count: Current retry attempt

        Returns:
            Delay in seconds
        """
        # Exponential backoff: 5s, 10s, 20s, 40s, ...
        base_delay = 5
        delay = base_delay * (2 ** retry_count)

        # Cap at 60 seconds
        return min(delay, 60)


class FailureClassifier:
    """Classifies types of failures to inform retry decisions."""

    @staticmethod
    def classify_validation_failure(
        validation_result: dict,
    ) -> tuple[bool, list[str]]:
        """Classify validation failure and extract fixable issues.

        Args:
            validation_result: Validation result dictionary

        Returns:
            Tuple of (is_retryable, list_of_issues)
        """
        issues = []

        # Check test failures
        if "tests" in validation_result:
            tests = validation_result["tests"]
            if not tests.get("passed", False):
                failed_count = tests.get("failed_tests", 0)
                issues.append(f"{failed_count} test(s) failing")

        # Check quality issues
        if "quality" in validation_result:
            quality = validation_result["quality"]

            if not quality.get("type_check", {}).get("passed", True):
                errors = quality.get("type_check", {}).get("errors", 0)
                issues.append(f"{errors} type error(s)")

            if not quality.get("linting", {}).get("passed", True):
                errors = quality.get("linting", {}).get("errors", 0)
                issues.append(f"{errors} linting error(s)")

        # Check security issues
        if "security" in validation_result:
            security = validation_result["security"]
            if security.get("secrets_found", False):
                issues.append("Secrets detected in code")
            if security.get("vulnerabilities", []):
                vuln_count = len(security["vulnerabilities"])
                issues.append(f"{vuln_count} security vulnerabilities")

        # Determine if retryable
        # Most validation failures are retryable (can be fixed)
        # Exceptions: fundamental architecture issues, missing dependencies
        retryable = len(issues) > 0 and not any(
            "architecture" in issue.lower() or "missing" in issue.lower()
            for issue in issues
        )

        return retryable, issues

    @staticmethod
    def is_transient_error(error_message: str) -> bool:
        """Check if an error is likely transient.

        Args:
            error_message: Error message string

        Returns:
            True if error appears transient
        """
        transient_patterns = [
            "timeout",
            "network",
            "connection",
            "temporary",
            "unavailable",
            "rate limit",
        ]

        error_lower = error_message.lower()
        return any(pattern in error_lower for pattern in transient_patterns)
