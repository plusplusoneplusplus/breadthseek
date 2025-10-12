"""Task validation against execution requirements.

This module provides validation to ensure tasks can be executed through
all phases (planning, execution, validation) with the available templates.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import TaskValidationError
from .prompt_loader import PromptLoader
from .task_schema import TaskDefinition


class TaskValidator:
    """Validates tasks can be executed with available templates.

    This validator performs "fail-fast" validation by checking that:
    1. All required template variables can be provided from task data
    2. Tasks have sufficient information for all execution phases
    3. No template rendering will fail during execution

    Example:
        >>> validator = TaskValidator()
        >>> errors = validator.validate_for_execution(task)
        >>> if errors:
        ...     raise TaskValidationError(f"Task invalid: {errors}")
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize task validator.

        Args:
            prompts_dir: Optional custom prompts directory
        """
        self.prompt_loader = PromptLoader(prompts_dir=prompts_dir)

    def validate_for_execution(self, task: TaskDefinition) -> List[str]:
        """Validate task has all fields needed for execution phases.

        This performs a dry-run validation against all templates that will be
        used during task execution, ensuring no template rendering failures
        will occur.

        Args:
            task: Task definition to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Load all templates that will be used during execution
        templates_to_check = ["planning", "execution", "validation"]

        for template_name in templates_to_check:
            try:
                template = self.prompt_loader.load_template(template_name)
            except Exception as e:
                errors.append(f"Failed to load {template_name} template: {e}")
                continue

            # Build variable dict from task
            task_vars = self._build_task_variables(task)

            # Check for missing required variables
            missing_required = set(template.required_variables) - set(task_vars.keys())

            if missing_required:
                # Filter out variables that can be auto-generated or provided at execution time
                execution_time_vars = {
                    # Variables provided after execution
                    "execution_summary",
                    "validation_failure_summary",
                    "failed_checks_list",
                    # Variables from planning phase (used in execution template)
                    "step_number",
                    "total_steps",
                    "next_step_number",
                    "plan_summary",
                    "step_description",
                    "step_duration",
                    "step_files",
                    "step_validation",
                    "step_checkpoint",
                    "previous_steps_section",
                }

                actual_missing = missing_required - execution_time_vars

                if actual_missing:
                    errors.append(
                        f"Task missing required fields for {template_name} phase: "
                        f"{sorted(actual_missing)}"
                    )

        return errors

    def validate_and_raise(self, task: TaskDefinition) -> None:
        """Validate task and raise exception if invalid.

        Args:
            task: Task definition to validate

        Raises:
            TaskValidationError: If validation fails with detailed error messages
        """
        errors = self.validate_for_execution(task)

        if errors:
            error_msg = f"Task '{task.id}' cannot be executed:\n"
            error_msg += "\n".join(f"  ✗ {error}" for error in errors)
            error_msg += "\n\nPlease provide the missing fields when creating the task."
            raise TaskValidationError(error_msg)

    def get_warnings(self, task: TaskDefinition) -> List[str]:
        """Get warnings for task that may impact execution quality.

        These are not errors - the task can execute - but the results may
        not be optimal without these fields.

        Args:
            task: Task definition to check

        Returns:
            List of warning messages
        """
        warnings = []

        # Check for recommended but optional fields
        if not task.success_criteria:
            warnings.append(
                "No success_criteria provided. Validation will use generic checks only. "
                "Providing specific success criteria improves validation accuracy."
            )

        if not task.context:
            warnings.append(
                "No context provided. Consider adding context to help the AI "
                "understand the task better (e.g., background, constraints, related work)."
            )

        if not task.focus_files:
            warnings.append(
                "No focus_files provided. Specifying files to focus on can "
                "improve execution efficiency and accuracy."
            )

        return warnings

    def _build_task_variables(self, task: TaskDefinition) -> Dict[str, Any]:
        """Build variable dictionary from task definition.

        Args:
            task: Task definition

        Returns:
            Dictionary of variables that can be used in templates
        """
        # Required variables always present
        variables = {
            "task_id": task.id,
            "description": task.description,
            "priority": task.priority.value,
            "estimated_duration": task.estimated_duration,
        }

        # Add optional fields if present
        if task.context:
            variables["context"] = task.context
            variables["context_section"] = True  # Section will be included

        if task.focus_files:
            variables["focus_files"] = task.focus_files
            variables["focus_files_section"] = True  # Section will be included

        if task.success_criteria:
            variables["success_criteria"] = task.success_criteria
            variables["success_criteria_section"] = True  # Section will be included
            # success_criteria_checklist will be auto-generated by prompt_loader

        return variables


def validate_task_for_execution(
    task: TaskDefinition, prompts_dir: Optional[Path] = None
) -> None:
    """Convenience function to validate a task and raise on error.

    Args:
        task: Task definition to validate
        prompts_dir: Optional custom prompts directory

    Raises:
        TaskValidationError: If task cannot be executed
    """
    validator = TaskValidator(prompts_dir=prompts_dir)
    validator.validate_and_raise(task)
