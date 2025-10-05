"""Configuration loading and management."""

import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from pydantic import ValidationError

from fsd.config.models import FSDConfig
from fsd.core.exceptions import ConfigurationError


def load_config(
    project_config_path: Optional[Path] = None,
    global_config_path: Optional[Path] = None,
) -> FSDConfig:
    """Load FSD configuration from multiple sources.

    Configuration is loaded in the following order (later sources override earlier ones):
    1. Default configuration (built into the models)
    2. Global configuration (~/.config/fsd/config.yaml)
    3. Project configuration (.fsd/config.yaml)
    4. Explicit paths provided as arguments

    Args:
        project_config_path: Explicit path to project config file
        global_config_path: Explicit path to global config file

    Returns:
        Merged and validated FSD configuration

    Raises:
        ConfigurationError: If configuration is invalid or cannot be loaded
    """
    try:
        # Start with default configuration
        config_data = {}

        # Load global configuration
        global_path = global_config_path or _get_global_config_path()
        if global_path and global_path.exists():
            global_data = _load_yaml_file(global_path)
            config_data = _merge_config(config_data, global_data)

        # Load project configuration
        project_path = project_config_path or _get_project_config_path()
        if project_path and project_path.exists():
            project_data = _load_yaml_file(project_path)
            config_data = _merge_config(config_data, project_data)

        # Create and validate configuration
        config = FSDConfig(**config_data)

        # Resolve environment variables
        config = config.resolve_env_vars()

        return config

    except ValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}") from e


def save_config(config: FSDConfig, config_path: Path) -> None:
    """Save configuration to a YAML file.

    Args:
        config: FSD configuration to save
        config_path: Path to save the configuration file

    Raises:
        ConfigurationError: If configuration cannot be saved
    """
    try:
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and save as YAML
        config_dict = config.model_dump(exclude_none=True, mode="json")

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config_dict,
                f,
                default_flow_style=False,
                sort_keys=False,
                indent=2,
                allow_unicode=True,
            )

    except Exception as e:
        raise ConfigurationError(
            f"Failed to save configuration to {config_path}: {e}"
        ) from e


def create_default_config() -> FSDConfig:
    """Create a default FSD configuration.

    Returns:
        Default FSD configuration with all default values
    """
    return FSDConfig()


def validate_config_file(config_path: Path) -> Dict[str, Any]:
    """Validate a configuration file without loading it fully.

    Args:
        config_path: Path to configuration file to validate

    Returns:
        Dictionary containing validation results

    Raises:
        ConfigurationError: If file cannot be read or parsed
    """
    try:
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        # Load and parse YAML
        config_data = _load_yaml_file(config_path)

        # Validate against schema
        try:
            config = FSDConfig(**config_data)
            return {
                "valid": True,
                "errors": [],
                "warnings": [],
                "config": config.model_dump(),
            }
        except ValidationError as e:
            return {
                "valid": False,
                "errors": [str(error) for error in e.errors()],
                "warnings": [],
                "config": None,
            }

    except Exception as e:
        raise ConfigurationError(f"Failed to validate configuration file: {e}") from e


def get_config_paths() -> Dict[str, Optional[Path]]:
    """Get all possible configuration file paths.

    Returns:
        Dictionary with 'global' and 'project' config paths
    """
    return {"global": _get_global_config_path(), "project": _get_project_config_path()}


def _get_global_config_path() -> Optional[Path]:
    """Get the global configuration file path."""
    # Try XDG config directory first
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "fsd" / "config.yaml"

    # Fall back to ~/.config
    home = Path.home()
    return home / ".config" / "fsd" / "config.yaml"


def _get_project_config_path() -> Optional[Path]:
    """Get the project configuration file path."""
    # Look for .fsd directory in current directory and parents
    current = Path.cwd()

    for path in [current] + list(current.parents):
        fsd_dir = path / ".fsd"
        if fsd_dir.exists() and fsd_dir.is_dir():
            return fsd_dir / "config.yaml"

    return None


def _load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a YAML file.

    Args:
        file_path: Path to YAML file

    Returns:
        Parsed YAML data as dictionary

    Raises:
        ConfigurationError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}

        if not isinstance(data, dict):
            raise ConfigurationError(
                f"Configuration file must contain a YAML object, got {type(data)}"
            )

        return data

    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {file_path}: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Failed to read {file_path}: {e}") from e


def _merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries recursively.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _merge_config(result[key], value)
        else:
            # Override value
            result[key] = value

    return result
