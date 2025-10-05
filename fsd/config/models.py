"""Configuration models for FSD."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentConfig(BaseModel):
    """Agent execution configuration."""

    max_execution_time: str = Field(default="8h", description="Maximum execution time")
    checkpoint_interval: str = Field(default="5m", description="Checkpoint interval")
    parallel_tasks: int = Field(default=1, description="Maximum parallel tasks")
    mode: str = Field(default="autonomous", description="Execution mode")

    @field_validator("max_execution_time", "checkpoint_interval")
    @classmethod
    def validate_duration(cls, v: str) -> str:
        """Validate duration format."""
        if not re.match(r"^\d+[hm]$", v):
            raise ValueError("Duration must be in format like '8h' or '30m'")
        return v

    @field_validator("parallel_tasks")
    @classmethod
    def validate_parallel_tasks(cls, v: int) -> int:
        """Validate parallel tasks count."""
        if v < 1:
            raise ValueError("parallel_tasks must be at least 1")
        if v > 10:
            raise ValueError("parallel_tasks cannot exceed 10")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate execution mode."""
        valid_modes = ["interactive", "autonomous", "dry_run"]
        if v not in valid_modes:
            raise ValueError(f"mode must be one of: {', '.join(valid_modes)}")
        return v


class ClaudeConfig(BaseModel):
    """Claude CLI configuration."""

    command: str = Field(
        default="claude --dangerously-skip-permissions", description="Claude command"
    )
    working_dir: str = Field(default=".", description="Working directory")
    timeout: str = Field(default="30m", description="Command timeout")

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: str) -> str:
        """Validate timeout format."""
        if not re.match(r"^\d+[hms]$", v):
            raise ValueError("Timeout must be in format like '30m', '2h', or '300s'")
        return v


class SafetyConfig(BaseModel):
    """Safety and security configuration."""

    protected_branches: List[str] = Field(
        default=["main", "master", "production"], description="Protected git branches"
    )
    require_tests: bool = Field(default=True, description="Require tests to pass")
    require_type_check: bool = Field(default=True, description="Require type checking")
    secret_scan: bool = Field(default=True, description="Scan for secrets")
    auto_merge: bool = Field(default=False, description="Auto-merge PRs")

    max_files_per_commit: int = Field(default=50, description="Max files per commit")
    max_lines_per_file: int = Field(default=5000, description="Max lines per file")
    max_total_changes: int = Field(default=10000, description="Max total line changes")

    @field_validator("max_files_per_commit", "max_lines_per_file", "max_total_changes")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Validate positive integers."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class GitUserConfig(BaseModel):
    """Git user configuration."""

    name: str = Field(default="FSD Agent", description="Git user name")
    email: str = Field(default="fsd-agent@example.com", description="Git user email")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", v):
            raise ValueError("Invalid email format")
        return v


class GitConfig(BaseModel):
    """Git configuration."""

    branch_prefix: str = Field(default="fsd/", description="Branch prefix for tasks")
    commit_format: str = Field(
        default="${type}: ${description}\n\nTask: ${task_id}\nStep: ${step_id}\n\n🤖 FSD Autonomous Agent",
        description="Commit message format",
    )
    sign_commits: bool = Field(default=False, description="Sign commits with GPG")
    user: GitUserConfig = Field(
        default_factory=GitUserConfig, description="Git user config"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format")
    output_dir: str = Field(default=".fsd/logs", description="Log output directory")
    retention_days: int = Field(default=30, description="Log retention in days")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARN", "ERROR"]
        if v.upper() not in valid_levels:
            raise ValueError(f"level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "text"]
        if v not in valid_formats:
            raise ValueError(f"format must be one of: {', '.join(valid_formats)}")
        return v

    @field_validator("retention_days")
    @classmethod
    def validate_retention(cls, v: int) -> int:
        """Validate retention days."""
        if v < 1:
            raise ValueError("retention_days must be at least 1")
        if v > 365:
            raise ValueError("retention_days cannot exceed 365")
        return v


class SlackConfig(BaseModel):
    """Slack notification configuration."""

    enabled: bool = Field(default=False, description="Enable Slack notifications")
    webhook_url: Optional[str] = Field(default=None, description="Slack webhook URL")
    channel: str = Field(default="#dev-fsd", description="Slack channel")
    mention_on_failure: str = Field(
        default="@channel", description="Mention on failure"
    )

    @model_validator(mode="after")
    def validate_slack_config(self) -> "SlackConfig":
        """Validate Slack configuration consistency."""
        if self.enabled and not self.webhook_url:
            raise ValueError("webhook_url is required when Slack is enabled")
        return self


class EmailConfig(BaseModel):
    """Email notification configuration."""

    enabled: bool = Field(default=False, description="Enable email notifications")
    smtp_host: Optional[str] = Field(default=None, description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    from_email: str = Field(default="fsd-agent@example.com", description="From email")
    to_emails: List[str] = Field(default_factory=list, description="Recipient emails")

    @model_validator(mode="after")
    def validate_email_config(self) -> "EmailConfig":
        """Validate email configuration consistency."""
        if self.enabled:
            if not self.smtp_host:
                raise ValueError("smtp_host is required when email is enabled")
            if not self.smtp_user:
                raise ValueError("smtp_user is required when email is enabled")
            if not self.to_emails:
                raise ValueError("to_emails is required when email is enabled")
        return self


class NotificationConfig(BaseModel):
    """Notification configuration."""

    enabled: bool = Field(default=False, description="Enable notifications")
    events: List[str] = Field(
        default=["task_completed", "task_failed", "execution_finished"],
        description="Events to notify on",
    )
    slack: SlackConfig = Field(default_factory=SlackConfig, description="Slack config")
    email: EmailConfig = Field(default_factory=EmailConfig, description="Email config")

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: List[str]) -> List[str]:
        """Validate notification events."""
        valid_events = [
            "task_started",
            "task_completed",
            "task_failed",
            "execution_started",
            "execution_finished",
            "critical_error",
        ]
        for event in v:
            if event not in valid_events:
                raise ValueError(
                    f"Invalid event '{event}'. Valid events: {', '.join(valid_events)}"
                )
        return v


class FSDConfig(BaseModel):
    """Main FSD configuration."""

    agent: AgentConfig = Field(
        default_factory=AgentConfig, description="Agent configuration"
    )
    claude: ClaudeConfig = Field(
        default_factory=ClaudeConfig, description="Claude configuration"
    )
    safety: SafetyConfig = Field(
        default_factory=SafetyConfig, description="Safety configuration"
    )
    git: GitConfig = Field(default_factory=GitConfig, description="Git configuration")
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig, description="Logging configuration"
    )
    notifications: NotificationConfig = Field(
        default_factory=NotificationConfig, description="Notification configuration"
    )

    def resolve_env_vars(self) -> "FSDConfig":
        """Resolve environment variables in configuration values."""
        config_dict = self.model_dump()
        resolved_dict = _resolve_env_vars_recursive(config_dict)
        return FSDConfig(**resolved_dict)

    def get_log_dir(self) -> Path:
        """Get the log directory as a Path object."""
        return Path(self.logging.output_dir).expanduser().resolve()

    def get_working_dir(self) -> Path:
        """Get the Claude working directory as a Path object."""
        return Path(self.claude.working_dir).expanduser().resolve()


def _resolve_env_vars_recursive(obj: Any) -> Any:
    """Recursively resolve environment variables in configuration."""
    if isinstance(obj, dict):
        return {key: _resolve_env_vars_recursive(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars_recursive(item) for item in obj]
    elif isinstance(obj, str):
        return _resolve_env_var_string(obj)
    else:
        return obj


def _resolve_env_var_string(value: str) -> str:
    """Resolve environment variables in a string."""
    # Pattern for ${VAR_NAME} or ${VAR_NAME:default_value}
    pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

    def replace_var(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ""
        return os.getenv(var_name, default_value)

    return re.sub(pattern, replace_var, value)
