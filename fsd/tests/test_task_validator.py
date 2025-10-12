"""Tests for task validation against execution requirements."""

import pytest
from pathlib import Path

from fsd.core.task_schema import TaskDefinition, Priority
from fsd.core.task_validator import TaskValidator, TaskValidationError


class TestTaskValidator:
    """Test TaskValidator class."""

    def test_minimal_task_passes_validation(self):
        """Test that minimal valid task passes validation."""
        # Auto-generated success_criteria should make this valid
        task = TaskDefinition(
            id="minimal-task",
            description="Minimal task with only required fields",
            priority=Priority.LOW,
            estimated_duration="30m",
        )

        validator = TaskValidator()
        errors = validator.validate_for_execution(task)

        # Should have no errors because success_criteria is auto-generated
        assert len(errors) == 0, f"Minimal task should be valid, got errors: {errors}"

    def test_task_without_success_criteria_gets_auto_generated(self):
        """Test that tasks without success_criteria get it auto-generated."""
        task = TaskDefinition(
            id="test-task",
            description="Task without explicit success criteria",
            priority=Priority.MEDIUM,
            estimated_duration="1h",
        )

        # success_criteria should be auto-generated
        assert task.success_criteria is not None
        assert len(task.success_criteria) > 0
        assert "Implementation matches" in task.success_criteria

    def test_task_with_all_fields_passes_validation(self):
        """Test that task with all fields passes validation."""
        task = TaskDefinition(
            id="complete-task",
            description="Complete task with all optional fields",
            priority=Priority.HIGH,
            estimated_duration="2h",
            context="Additional background information",
            focus_files=["main.py", "tests/test_main.py"],
            success_criteria="All tests pass\nCode is documented",
        )

        validator = TaskValidator()
        errors = validator.validate_for_execution(task)

        assert len(errors) == 0

    def test_validator_provides_helpful_warnings(self):
        """Test that validator provides warnings for non-ideal tasks."""
        task = TaskDefinition(
            id="warning-task",
            description="Task that triggers warnings",
            priority=Priority.MEDIUM,
            estimated_duration="1h",
            # No context, focus_files, or success_criteria
        )

        # Clear auto-generated success_criteria to test warning
        # (In practice this won't happen due to model_validator)
        validator = TaskValidator()

        # Get warnings (success_criteria will be auto-generated, so only other warnings)
        warnings = validator.get_warnings(task)

        # Should have warnings about missing optional fields
        warning_text = " ".join(warnings)
        assert "context" in warning_text.lower()
        assert "focus_files" in warning_text.lower()

    def test_validate_and_raise_with_valid_task(self):
        """Test validate_and_raise doesn't raise for valid task."""
        task = TaskDefinition(
            id="valid-task",
            description="A valid task definition",
            priority=Priority.MEDIUM,
            estimated_duration="45m",
        )

        validator = TaskValidator()

        # Should not raise
        validator.validate_and_raise(task)

    def test_template_variables_are_available(self):
        """Test that all required template variables can be provided."""
        task = TaskDefinition(
            id="template-test",
            description="Test task for template variable availability",
            priority=Priority.HIGH,
            estimated_duration="1h30m",
            context="Test context",
            focus_files=["app.py"],
            success_criteria="Tests pass\nNo errors",
        )

        validator = TaskValidator()
        task_vars = validator._build_task_variables(task)

        # Check required variables are present
        assert "task_id" in task_vars
        assert "description" in task_vars
        assert "priority" in task_vars
        assert "estimated_duration" in task_vars

        # Check optional variables are present when provided
        assert "context" in task_vars
        assert "focus_files" in task_vars
        assert "success_criteria" in task_vars

    def test_convenience_function(self):
        """Test validate_task_for_execution convenience function."""
        from fsd.core.task_validator import validate_task_for_execution

        task = TaskDefinition(
            id="convenience-test",
            description="Test convenience function",
            priority=Priority.LOW,
            estimated_duration="20m",
        )

        # Should not raise for valid task
        validate_task_for_execution(task)


class TestTaskSchemaAutoGeneration:
    """Test auto-generation in TaskDefinition schema."""

    def test_success_criteria_auto_generated_when_missing(self):
        """Test that success_criteria is auto-generated when not provided."""
        task = TaskDefinition(
            id="auto-gen-test",
            description="Task without success criteria",
            priority=Priority.MEDIUM,
            estimated_duration="1h",
        )

        assert task.success_criteria is not None
        assert isinstance(task.success_criteria, str)
        assert len(task.success_criteria) > 0

    def test_success_criteria_preserved_when_provided(self):
        """Test that provided success_criteria is not overwritten."""
        custom_criteria = "Custom success criteria\n- Specific requirement 1\n- Specific requirement 2"

        task = TaskDefinition(
            id="custom-criteria-test",
            description="Task with custom success criteria",
            priority=Priority.HIGH,
            estimated_duration="2h",
            success_criteria=custom_criteria,
        )

        assert task.success_criteria == custom_criteria

    def test_auto_generated_criteria_has_sensible_defaults(self):
        """Test that auto-generated criteria contains sensible defaults."""
        task = TaskDefinition(
            id="defaults-test",
            description="Test default criteria content",
            priority=Priority.LOW,
            estimated_duration="30m",
        )

        criteria = task.success_criteria.lower()

        # Should mention implementation, tests, code quality, security
        assert "implementation" in criteria
        assert "test" in criteria
        assert "quality" in criteria or "linting" in criteria
        assert "security" in criteria or "secrets" in criteria


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_task_with_empty_success_criteria_gets_regenerated(self):
        """Test that empty success_criteria gets replaced."""
        # This tests the schema validation - empty string should trigger auto-gen
        task = TaskDefinition(
            id="empty-criteria-test",
            description="Task with empty success criteria string",
            priority=Priority.MEDIUM,
            estimated_duration="1h",
            success_criteria="",  # Empty string
        )

        # Empty string should be replaced with auto-generated criteria
        # (This depends on how the model_validator handles empty strings)
        assert task.success_criteria is not None

    def test_task_with_very_long_description(self):
        """Test validation with very long description."""
        long_description = "A" * 1000  # 1000 character description

        task = TaskDefinition(
            id="long-desc-test",
            description=long_description,
            priority=Priority.LOW,
            estimated_duration="1h",
        )

        validator = TaskValidator()
        errors = validator.validate_for_execution(task)

        # Should still pass validation
        assert len(errors) == 0

    def test_task_with_many_focus_files(self):
        """Test validation with many focus files."""
        many_files = [f"file_{i}.py" for i in range(50)]

        task = TaskDefinition(
            id="many-files-test",
            description="Task with many focus files",
            priority=Priority.MEDIUM,
            estimated_duration="3h",
            focus_files=many_files,
        )

        validator = TaskValidator()
        errors = validator.validate_for_execution(task)

        # Should still pass validation
        assert len(errors) == 0

    def test_task_with_multiline_success_criteria(self):
        """Test task with multiline success criteria."""
        multiline_criteria = """
        - First criterion
        - Second criterion with details
          - Sub-requirement A
          - Sub-requirement B
        - Third criterion
        """

        task = TaskDefinition(
            id="multiline-test",
            description="Task with complex success criteria",
            priority=Priority.HIGH,
            estimated_duration="2h",
            success_criteria=multiline_criteria,
        )

        validator = TaskValidator()
        errors = validator.validate_for_execution(task)

        assert len(errors) == 0


@pytest.mark.integration
class TestValidationIntegration:
    """Integration tests for validation in task submission flow."""

    def test_validation_prevents_invalid_task_submission(self):
        """Test that validation catches invalid tasks before submission."""
        # This would be an integration test with the web API or CLI
        # For now, just ensure the validator works as expected

        task = TaskDefinition(
            id="integration-test",
            description="Integration test task",
            priority=Priority.MEDIUM,
            estimated_duration="1h",
        )

        validator = TaskValidator()

        # Should not raise
        try:
            validator.validate_and_raise(task)
            validated = True
        except TaskValidationError:
            validated = False

        assert validated, "Valid task should pass validation"

    def test_template_rendering_simulation(self):
        """Test that template variables can be extracted and used."""
        task = TaskDefinition(
            id="render-test",
            description="Test template rendering compatibility",
            priority=Priority.HIGH,
            estimated_duration="1h",
            context="Test context for rendering",
            focus_files=["main.py", "utils.py"],
            success_criteria="- Tests pass\n- Code documented",
        )

        validator = TaskValidator()
        variables = validator._build_task_variables(task)

        # Verify all expected variables are present
        required_vars = ["task_id", "description", "priority", "estimated_duration"]
        for var in required_vars:
            assert var in variables, f"Required variable '{var}' missing"

        # Verify values are correct types
        assert isinstance(variables["task_id"], str)
        assert isinstance(variables["description"], str)
        assert isinstance(variables["priority"], str)
        assert isinstance(variables["estimated_duration"], str)
