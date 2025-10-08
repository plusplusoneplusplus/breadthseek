# Task 2: Task Definition Schema and Validation

**ID:** `fsd-task-schema`
**Priority:** High
**Estimated Duration:** 2 hours
**Status:** Completed

## Description

Implement the task definition schema and validation system for FSD.

Create a Pydantic model for task definitions that supports:
- **Required fields:** id, description, priority, estimated_duration
- **Optional fields:** context, focus_files, success_criteria, on_completion
- **Priority enum:** low, medium, high, critical
- **Duration parsing:** (e.g., "2h", "30m", "1h30m")

Add validation logic:
- Ensure task IDs are unique and follow naming conventions
- Validate duration format
- Check that focus_files patterns are valid
- Validate completion actions

Create utility functions:
- `load_task_from_yaml()` to parse YAML task files
- `validate_task()` to check task definitions
- `save_task()` to write tasks back to YAML

Include comprehensive error messages for validation failures.

## Context

- Use Pydantic v2 for schema definition and validation
- Support both single task files and multi-task YAML files
- Follow the simplified schema from `fsd/docs/task-schema.yaml`
- Make sure to handle YAML parsing errors gracefully

## Success Criteria

- ✅ TaskDefinition Pydantic model is complete
- ✅ Can load and validate task YAML files
- ✅ Clear error messages for invalid tasks
- ✅ All validation edge cases are handled
- ✅ Unit tests cover all validation scenarios

## Focus Files

- `fsd/core/task_schema.py`
- `tests/test_task_schema.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Task definition schema and validation system"
- **Notify Slack:** No
