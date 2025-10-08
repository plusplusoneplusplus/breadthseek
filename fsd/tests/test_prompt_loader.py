"""Tests for prompt template loader."""

import tempfile
from pathlib import Path

import pytest

from fsd.core.prompt_loader import (
    PromptLoadError,
    PromptLoader,
    PromptRenderError,
    PromptTemplate,
    load_prompt,
)


class TestPromptTemplate:
    """Test PromptTemplate model and rendering."""

    def test_template_creation(self):
        """Test creating a template."""
        template = PromptTemplate(
            name="test",
            content="Hello {name}!",
            required_variables=["name"],
            optional_variables=[],
        )

        assert template.name == "test"
        assert template.content == "Hello {name}!"
        assert template.required_variables == ["name"]

    def test_simple_render(self):
        """Test rendering with simple variable substitution."""
        template = PromptTemplate(
            name="test",
            content="Hello {name}! You are {age} years old.",
            required_variables=["name", "age"],
        )

        result = template.render({"name": "Alice", "age": 30})
        assert result == "Hello Alice! You are 30 years old."

    def test_missing_required_variable(self):
        """Test that missing required variables raise error."""
        template = PromptTemplate(
            name="test",
            content="Hello {name}!",
            required_variables=["name"],
        )

        with pytest.raises(PromptRenderError, match="Missing required variables"):
            template.render({})

    def test_optional_variables(self):
        """Test that optional variables can be omitted."""
        template = PromptTemplate(
            name="test",
            content="Task: {task_id}\n{context_section}",
            required_variables=["task_id"],
            optional_variables=["context_section"],
        )

        # Without optional variable - section placeholder removed
        result = template.render({"task_id": "test-123"})
        assert "test-123" in result
        assert "{context_section}" not in result

    def test_optional_section_formatting(self):
        """Test that optional sections are formatted correctly."""
        template = PromptTemplate(
            name="test",
            content="Task: {task_id}\n{context_section}",
            required_variables=["task_id"],
            optional_variables=["context_section", "context"],
        )

        result = template.render({
            "task_id": "test-123",
            "context": "This is additional context",
        })

        assert "test-123" in result
        assert "Additional Context" in result
        assert "This is additional context" in result

    def test_focus_files_section(self):
        """Test formatting of focus_files section."""
        template = PromptTemplate(
            name="test",
            content="{focus_files_section}",
            required_variables=[],
            optional_variables=["focus_files_section", "focus_files"],
        )

        result = template.render({
            "focus_files": ["src/main.py", "tests/test_main.py"],
        })

        assert "Focus Files" in result
        assert "src/main.py" in result
        assert "tests/test_main.py" in result

    def test_none_values(self):
        """Test handling of None values."""
        template = PromptTemplate(
            name="test",
            content="Value: {value}",
            required_variables=["value"],
        )

        result = template.render({"value": None})
        assert result == "Value: "

    def test_multiline_content(self):
        """Test rendering multiline templates."""
        template = PromptTemplate(
            name="test",
            content="""# Task {task_id}

Description: {description}

Priority: {priority}""",
            required_variables=["task_id", "description", "priority"],
        )

        result = template.render({
            "task_id": "test-123",
            "description": "Test task",
            "priority": "high",
        })

        assert "# Task test-123" in result
        assert "Description: Test task" in result
        assert "Priority: high" in result


class TestPromptLoader:
    """Test PromptLoader functionality."""

    def test_loader_initialization_default(self):
        """Test loader initializes with default directory."""
        loader = PromptLoader()
        assert loader.prompts_dir.exists()
        assert loader.prompts_dir.name == "prompts"

    def test_loader_initialization_custom(self, tmp_path):
        """Test loader with custom directory."""
        custom_dir = tmp_path / "custom_prompts"
        custom_dir.mkdir()

        loader = PromptLoader(prompts_dir=custom_dir)
        assert loader.prompts_dir == custom_dir

    def test_loader_nonexistent_directory(self, tmp_path):
        """Test loader raises error for nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(PromptLoadError, match="not found"):
            PromptLoader(prompts_dir=nonexistent)

    def test_load_template_real(self):
        """Test loading a real template (planning.md)."""
        loader = PromptLoader()
        template = loader.load_template("planning")

        assert template.name == "planning"
        assert "Planning Phase" in template.content
        assert "task_id" in template.required_variables
        assert "description" in template.required_variables

    def test_load_template_cache(self):
        """Test that templates are cached."""
        loader = PromptLoader()

        template1 = loader.load_template("planning")
        template2 = loader.load_template("planning")

        # Should be the same object (from cache)
        assert template1 is template2

    def test_load_nonexistent_template(self, tmp_path):
        """Test loading nonexistent template raises error."""
        loader = PromptLoader(prompts_dir=tmp_path)

        with pytest.raises(PromptLoadError, match="not found"):
            loader.load_template("nonexistent")

    def test_render_template(self, tmp_path):
        """Test rendering template directly."""
        # Create a test template
        template_file = tmp_path / "test.md"
        template_file.write_text("Hello {name}!")

        loader = PromptLoader(prompts_dir=tmp_path)
        result = loader.render_template("test", {"name": "World"})

        assert result == "Hello World!"

    def test_list_templates(self, tmp_path):
        """Test listing available templates."""
        # Create some templates
        (tmp_path / "template1.md").write_text("Content 1")
        (tmp_path / "template2.md").write_text("Content 2")
        (tmp_path / "not_a_template.txt").write_text("Not a template")

        loader = PromptLoader(prompts_dir=tmp_path)
        templates = loader.list_templates()

        assert "template1" in templates
        assert "template2" in templates
        assert "not_a_template" not in templates

    def test_clear_cache(self):
        """Test clearing template cache."""
        loader = PromptLoader()

        # Load a template
        template1 = loader.load_template("planning")
        assert "planning" in loader._templates

        # Clear cache
        loader.clear_cache()
        assert "planning" not in loader._templates

        # Load again - should be different object
        template2 = loader.load_template("planning")
        assert template1 is not template2


class TestLoadPromptFunction:
    """Test convenience load_prompt function."""

    def test_load_prompt_simple(self, tmp_path):
        """Test load_prompt with simple template."""
        template_file = tmp_path / "greeting.md"
        template_file.write_text("Hello {name}!")

        result = load_prompt(
            "greeting",
            prompts_dir=tmp_path,
            name="Alice"
        )

        assert result == "Hello Alice!"

    def test_load_prompt_missing_variable(self, tmp_path):
        """Test load_prompt raises error for missing variable."""
        template_file = tmp_path / "greeting.md"
        template_file.write_text("Hello {name}!")

        with pytest.raises(PromptRenderError):
            load_prompt("greeting", prompts_dir=tmp_path)

    def test_load_prompt_real_planning(self):
        """Test loading real planning template."""
        result = load_prompt(
            "planning",
            task_id="test-task",
            description="Test description",
            priority="high",
            estimated_duration="2h",
        )

        assert "test-task" in result
        assert "Test description" in result
        assert "high" in result

    def test_load_prompt_with_optional_context(self):
        """Test loading template with optional context."""
        result = load_prompt(
            "planning",
            task_id="test-task",
            description="Test description",
            priority="high",
            estimated_duration="2h",
            context="Additional task context here",
        )

        assert "Additional Context" in result
        assert "Additional task context" in result


class TestRealTemplates:
    """Integration tests with real prompt templates."""

    def test_planning_template_minimal(self):
        """Test planning template with minimal variables."""
        result = load_prompt(
            "planning",
            task_id="test-123",
            description="Implement feature X",
            priority="high",
            estimated_duration="3h",
        )

        assert "test-123" in result
        assert "Implement feature X" in result
        assert "Planning Phase" in result
        assert "JSON" in result  # Should mention JSON format

    def test_planning_template_complete(self):
        """Test planning template with all variables."""
        result = load_prompt(
            "planning",
            task_id="test-123",
            description="Implement feature X",
            priority="high",
            estimated_duration="3h",
            context="This is a complex feature requiring database changes",
            focus_files=["src/db/schema.py", "src/api/endpoints.py"],
            success_criteria="All tests pass\nNo type errors\nCoverage >80%",
        )

        assert "test-123" in result
        assert "complex feature" in result
        assert "src/db/schema.py" in result
        assert "Coverage >80%" in result

    def test_execution_template(self):
        """Test execution template rendering."""
        result = load_prompt(
            "execution",
            task_id="test-123",
            description="Add authentication",
            step_number=1,
            total_steps=3,
            step_description="Create auth middleware",
            step_duration="45m",
            step_files="src/middleware/auth.py",
            step_validation="Tests pass",
            step_checkpoint=True,
            plan_summary="3-step plan to add authentication",
        )

        assert "Step 1" in result
        assert "Create auth middleware" in result
        assert "45m" in result

    def test_validation_template(self):
        """Test validation template rendering."""
        result = load_prompt(
            "validation",
            task_id="test-123",
            description="Add authentication",
            priority="high",
            execution_summary="Completed all 3 steps successfully",
        )

        assert "test-123" in result
        assert "Validation Phase" in result
        assert "tests pass" in result.lower()

    def test_recovery_template(self):
        """Test recovery template rendering."""
        result = load_prompt(
            "recovery",
            task_id="test-123",
            description="Add authentication",
            retry_count=1,
            max_retries=3,
            validation_failure_summary="Tests failing: 2/10 tests failed",
            failed_checks_list="- test_auth_token\n- test_token_expiry",
        )

        assert "test-123" in result
        assert "Recovery Phase" in result
        assert "retry" in result.lower()
        assert "1" in result  # retry count


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_template(self, tmp_path):
        """Test rendering empty template."""
        template_file = tmp_path / "empty.md"
        template_file.write_text("")

        result = load_prompt("empty", prompts_dir=tmp_path)
        assert result == ""

    def test_template_with_no_variables(self, tmp_path):
        """Test template with no variables."""
        template_file = tmp_path / "static.md"
        template_file.write_text("This is static content with no variables.")

        result = load_prompt("static", prompts_dir=tmp_path)
        assert result == "This is static content with no variables."

    def test_template_with_special_characters(self, tmp_path):
        """Test template with special characters."""
        template_file = tmp_path / "special.md"
        template_file.write_text("Name: {name}\n$pecial: {value}")

        result = load_prompt(
            "special",
            prompts_dir=tmp_path,
            name="Test",
            value="$100"
        )

        assert "Test" in result
        assert "$100" in result

    def test_template_with_nested_braces(self, tmp_path):
        """Test template with nested braces (JSON examples)."""
        template_file = tmp_path / "json.md"
        template_file.write_text("""```json
{{
  "name": "{name}",
  "value": 123
}}
```""")

        result = load_prompt(
            "json",
            prompts_dir=tmp_path,
            name="test"
        )

        # Double braces should be preserved, single braces substituted
        assert '"name": "test"' in result
        assert '"value": 123' in result
