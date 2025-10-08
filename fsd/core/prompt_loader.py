"""Prompt template loader with variable substitution.

This module provides functionality to load and render prompt templates
for different phases of task execution (planning, execution, validation, recovery).
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PromptLoadError(Exception):
    """Raised when prompt template cannot be loaded."""

    pass


class PromptRenderError(Exception):
    """Raised when prompt template cannot be rendered."""

    pass


class PromptTemplate(BaseModel):
    """Represents a loaded prompt template."""

    name: str = Field(description="Template name (e.g., 'planning', 'execution')")
    content: str = Field(description="Raw template content")
    required_variables: list[str] = Field(
        default_factory=list, description="List of required variable names"
    )
    optional_variables: list[str] = Field(
        default_factory=list, description="List of optional variable names"
    )

    def render(self, variables: Dict[str, Any]) -> str:
        """Render the template with provided variables.

        Args:
            variables: Dictionary of variable names to values

        Returns:
            Rendered template string

        Raises:
            PromptRenderError: If required variables are missing or rendering fails
        """
        # Check required variables
        missing = set(self.required_variables) - set(variables.keys())
        if missing:
            raise PromptRenderError(
                f"Missing required variables for template '{self.name}': {missing}"
            )

        # Build complete variable set with optional variables
        all_vars = {**variables}

        # Handle optional sections (sections that should be removed if variables are missing)
        rendered = self.content

        # Process optional sections like {context_section}, {focus_files_section}
        # These are conditional blocks that should be included only if the variable exists
        for opt_var in self.optional_variables:
            if opt_var.endswith("_section"):
                # If the corresponding data variable doesn't exist, remove the section
                data_var = opt_var.replace("_section", "")
                if data_var not in variables or not variables[data_var]:
                    # Remove the section placeholder
                    rendered = rendered.replace(f"{{{opt_var}}}", "")
                else:
                    # Replace with formatted section
                    section_content = self._format_section(data_var, variables[data_var])
                    all_vars[opt_var] = section_content

        # Perform variable substitution
        try:
            # Replace all {variable_name} patterns
            def replace_var(match):
                var_name = match.group(1)
                if var_name in all_vars:
                    value = all_vars[var_name]
                    # Convert to string, handle None
                    return str(value) if value is not None else ""
                # Leave unreplaced if not in variables (will be caught below)
                return match.group(0)

            rendered = re.sub(r"\{([^}]+)\}", replace_var, rendered)

            # Check for any remaining unsubstituted variables
            remaining = re.findall(r"\{([^}]+)\}", rendered)
            if remaining:
                raise PromptRenderError(
                    f"Template '{self.name}' has unsubstituted variables: {remaining}"
                )

            return rendered

        except Exception as e:
            if isinstance(e, PromptRenderError):
                raise
            raise PromptRenderError(
                f"Failed to render template '{self.name}': {e}"
            ) from e

    def _format_section(self, section_name: str, value: Any) -> str:
        """Format optional sections based on their type.

        Args:
            section_name: Name of the section (e.g., 'context', 'focus_files')
            value: Value to format

        Returns:
            Formatted section content
        """
        if section_name == "context" and value:
            return f"\n## Additional Context\n\n{value}\n"

        if section_name == "focus_files" and value:
            if isinstance(value, list):
                files_list = "\n".join(f"- {f}" for f in value)
                return f"\n## Focus Files\n\nPay special attention to these files:\n{files_list}\n"
            return f"\n## Focus Files\n\n{value}\n"

        if section_name == "success_criteria" and value:
            return f"\n## Success Criteria\n\n{value}\n"

        if section_name == "success_criteria_checklist" and value:
            # Format as checklist items
            if isinstance(value, list):
                items = "\n".join(f"- [ ] {criterion}" for criterion in value)
            else:
                # Split by newlines if string
                criteria = str(value).split("\n")
                items = "\n".join(f"- [ ] {c.strip()}" for c in criteria if c.strip())
            return items

        if section_name == "previous_steps" and value:
            if isinstance(value, list):
                steps = "\n".join(f"{i+1}. {step}" for i, step in enumerate(value))
                return f"\n## Previous Steps Completed\n\n{steps}\n"

        # Default formatting
        return f"\n## {section_name.replace('_', ' ').title()}\n\n{value}\n"


class PromptLoader:
    """Loads and manages prompt templates."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt templates.
                        Defaults to fsd/prompts/ in the project root.
        """
        if prompts_dir is None:
            # Default to fsd/prompts/ relative to this file
            # This file is in fsd/core/, so go up one level and into prompts/
            prompts_dir = Path(__file__).parent.parent / "prompts"

        self.prompts_dir = Path(prompts_dir)
        if not self.prompts_dir.exists():
            raise PromptLoadError(
                f"Prompts directory not found: {self.prompts_dir}"
            )

        self._templates: Dict[str, PromptTemplate] = {}

    def load_template(self, name: str) -> PromptTemplate:
        """Load a prompt template by name.

        Args:
            name: Template name (e.g., 'planning', 'execution', 'validation', 'recovery')

        Returns:
            Loaded PromptTemplate

        Raises:
            PromptLoadError: If template file not found or invalid
        """
        # Check cache
        if name in self._templates:
            return self._templates[name]

        # Load from file
        template_file = self.prompts_dir / f"{name}.md"
        if not template_file.exists():
            raise PromptLoadError(
                f"Template file not found: {template_file}"
            )

        try:
            content = template_file.read_text(encoding="utf-8")
        except Exception as e:
            raise PromptLoadError(
                f"Failed to read template '{name}': {e}"
            ) from e

        # Extract variables from template
        variables = re.findall(r"\{([^}]+)\}", content)

        # Categorize variables
        required_vars = []
        optional_vars = []

        for var in set(variables):
            # Variables ending in _section are optional
            # Common optional variables
            if var.endswith("_section") or var in [
                "context",
                "focus_files",
                "success_criteria",
                "previous_steps_section",
                "execution_summary",
                "validation_failure_summary",
                "failed_checks_list",
            ]:
                optional_vars.append(var)
            else:
                required_vars.append(var)

        template = PromptTemplate(
            name=name,
            content=content,
            required_variables=required_vars,
            optional_variables=optional_vars,
        )

        # Cache the template
        self._templates[name] = template

        return template

    def render_template(
        self, name: str, variables: Dict[str, Any]
    ) -> str:
        """Load and render a template in one step.

        Args:
            name: Template name
            variables: Variables to substitute

        Returns:
            Rendered template string

        Raises:
            PromptLoadError: If template cannot be loaded
            PromptRenderError: If template cannot be rendered
        """
        template = self.load_template(name)
        return template.render(variables)

    def list_templates(self) -> list[str]:
        """List available template names.

        Returns:
            List of template names (without .md extension)
        """
        if not self.prompts_dir.exists():
            return []

        return [
            f.stem
            for f in self.prompts_dir.glob("*.md")
            if f.is_file()
        ]

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._templates.clear()


# Convenience function
def load_prompt(
    name: str, prompts_dir: Optional[Path] = None, **variables
) -> str:
    """Load and render a prompt template in one step.

    Args:
        name: Template name (e.g., 'planning', 'execution')
        prompts_dir: Optional custom prompts directory
        **variables: Variables to substitute into template

    Returns:
        Rendered prompt string

    Example:
        >>> prompt = load_prompt(
        ...     "planning",
        ...     task_id="my-task",
        ...     description="Add authentication",
        ...     priority="high",
        ...     estimated_duration="3h"
        ... )
    """
    loader = PromptLoader(prompts_dir=prompts_dir)
    return loader.render_template(name, variables)
