# Task 4: Configuration System

**ID:** `fsd-config-system`
**Priority:** High
**Estimated Duration:** 2 hours
**Status:** Completed

## Description

Implement the configuration system for FSD based on the simplified config schema.

Create a Pydantic configuration model that supports:
- **Agent settings:** max_execution_time, checkpoint_interval, parallel_tasks
- **Claude CLI settings:** command, working_dir, timeout
- **Safety settings:** protected_branches, require_tests, auto_merge, etc.
- **Git settings:** branch_prefix, commit_format, user info
- **Logging settings:** level, format, output_dir, retention
- **Notification settings:** slack, email, cli

Configuration loading should:
- Load from `.fsd/config.yaml` in project root
- Fall back to `~/.config/fsd/config.yaml` for global settings
- Support environment variable substitution (`${VAR_NAME}`)
- Merge project config with global config (project takes precedence)
- Validate all configuration values

Include sensible defaults for all settings so FSD works out of the box.

## Context

- Use Pydantic for config validation and type safety
- Support YAML configuration files
- Environment variable substitution should be secure
- Config should be easily extensible for future features
- Follow the simplified config from `fsd/docs/example-config.yaml`

## Success Criteria

- ✅ Configuration model covers all needed settings
- ✅ Can load config from multiple sources with proper precedence
- ✅ Environment variable substitution works correctly
- ✅ Validation provides clear error messages
- ✅ Default config allows FSD to run without any setup
- ✅ Unit tests cover all config loading scenarios

## Focus Files

- `fsd/config/`
- `fsd/config/models.py`
- `fsd/config/loader.py`
- `tests/test_config.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Configuration system with YAML and environment support"
- **Notify Slack:** No
