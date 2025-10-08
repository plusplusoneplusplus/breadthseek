# Prompt Template System

The FSD prompt template system provides a simple, maintainable way to guide Claude Code CLI through different phases of task execution.

## Overview

Instead of building custom agents, FSD uses **prompt engineering** to leverage Claude Code's existing capabilities. Well-crafted prompts guide Claude through:
- **Planning** - Analyzing tasks and creating execution plans
- **Execution** - Implementing code changes step by step
- **Validation** - Running tests and quality checks
- **Recovery** - Fixing issues when validation fails

## Architecture

```
fsd/
├── prompts/              # Prompt templates (version controlled)
│   ├── planning.md
│   ├── execution.md
│   ├── validation.md
│   └── recovery.md
├── core/
│   └── prompt_loader.py  # Template loading and rendering
└── tests/
    └── test_prompt_loader.py
```

## Template Format

Templates are markdown files with variable substitution:

```markdown
# Planning Phase Prompt

You are helping with task **{task_id}**.

## Task Details
- **Description:** {description}
- **Priority:** {priority}

{context_section}

Now create your execution plan...
```

### Variable Syntax

- **Required variables:** `{variable_name}` - Must be provided
- **Optional sections:** `{section_name_section}` - Removed if not provided
- **Double braces:** `{{` and `}}` - Preserved as single braces (for JSON examples)

## Using Prompts

### Basic Usage

```python
from fsd.core.prompt_loader import load_prompt

# Load and render a prompt
prompt = load_prompt(
    "planning",
    task_id="add-auth",
    description="Add JWT authentication to API",
    priority="high",
    estimated_duration="3h"
)

# Use with Claude CLI
subprocess.run(["claude", "-p", prompt], ...)
```

### With Optional Sections

```python
# Include optional context
prompt = load_prompt(
    "planning",
    task_id="add-auth",
    description="Add authentication",
    priority="high",
    estimated_duration="3h",
    # Optional fields
    context="Use PyJWT library, follow OAuth 2.0 patterns",
    focus_files=["src/auth/", "src/middleware/"],
    success_criteria="All tests pass\nNo security vulnerabilities"
)
```

### Using the Loader Class

```python
from fsd.core.prompt_loader import PromptLoader

loader = PromptLoader()

# Load template (cached)
template = loader.load_template("planning")

# Render with variables
prompt = template.render({
    "task_id": "add-auth",
    "description": "Add authentication",
    "priority": "high",
    "estimated_duration": "3h"
})

# List available templates
templates = loader.list_templates()
print(templates)  # ['planning', 'execution', 'validation', 'recovery']
```

## Available Templates

### 1. Planning (`planning.md`)

**Purpose:** Analyze task and create execution plan

**Required Variables:**
- `task_id` - Unique task identifier
- `description` - Task description
- `priority` - Task priority (low/medium/high/critical)
- `estimated_duration` - Time estimate (e.g., "2h30m")

**Optional Variables:**
- `context` - Additional task context
- `focus_files` - List of files to focus on
- `success_criteria` - Criteria for task completion

**Output:** JSON execution plan with steps

**Example:**
```python
prompt = load_prompt(
    "planning",
    task_id="refactor-auth",
    description="Refactor authentication module",
    priority="medium",
    estimated_duration="4h",
    context="Current auth code is hard to test",
    focus_files=["src/auth/legacy.py", "src/auth/session.py"]
)
```

### 2. Execution (`execution.md`)

**Purpose:** Implement a specific step from the plan

**Required Variables:**
- `task_id` - Task identifier
- `description` - Task description
- `step_number` - Current step number
- `total_steps` - Total number of steps
- `step_description` - What to do in this step
- `step_duration` - Time estimate for step
- `step_files` - Files to modify
- `step_validation` - How to verify step succeeded
- `step_checkpoint` - Whether to create checkpoint
- `plan_summary` - Brief summary of overall plan

**Optional Variables:**
- `previous_steps_section` - Summary of completed steps

**Output:** Code changes, tests, validation summary

**Example:**
```python
prompt = load_prompt(
    "execution",
    task_id="refactor-auth",
    description="Refactor authentication",
    step_number=2,
    total_steps=4,
    step_description="Extract token validation into separate class",
    step_duration="1h",
    step_files="src/auth/token.py, tests/test_token.py",
    step_validation="All token tests pass",
    step_checkpoint=True,
    plan_summary="4-step refactoring of auth module"
)
```

### 3. Validation (`validation.md`)

**Purpose:** Verify task implementation is complete and correct

**Required Variables:**
- `task_id` - Task identifier
- `description` - Task description
- `priority` - Task priority

**Optional Variables:**
- `success_criteria_section` - Formatted success criteria
- `execution_summary` - Summary of what was implemented

**Output:** JSON validation report with pass/fail status

**Example:**
```python
prompt = load_prompt(
    "validation",
    task_id="refactor-auth",
    description="Refactor authentication",
    priority="medium",
    success_criteria="Tests pass\nNo type errors\nCoverage >85%",
    execution_summary="Refactored auth into 3 modular classes"
)
```

### 4. Recovery (`recovery.md`)

**Purpose:** Fix issues when validation fails

**Required Variables:**
- `task_id` - Task identifier
- `description` - Task description
- `retry_count` - Current retry attempt number
- `max_retries` - Maximum retry attempts allowed

**Optional Variables:**
- `validation_failure_summary` - Summary of validation failures
- `failed_checks_list` - List of failed checks

**Output:** JSON recovery report with fixes applied

**Example:**
```python
prompt = load_prompt(
    "recovery",
    task_id="refactor-auth",
    description="Refactor authentication",
    retry_count=1,
    max_retries=3,
    validation_failure_summary="2 tests failing, 1 type error",
    failed_checks_list="test_token_expiry\ntest_refresh_token\nmypy: line 45"
)
```

## Creating Custom Templates

### Template Structure

```markdown
# Phase Name

Introduction and role description.

## Task Details
- **Variable:** {required_variable}
- **Optional:** {optional_variable}

{optional_section}

## Instructions
1. Step one
2. Step two
3. Step three

## Output Format
Describe expected output format (often JSON).

## Example
Show a concrete example.

Now, [instruction for Claude].
```

### Variable Naming Conventions

- **snake_case** - Use snake_case for variable names
- **_section suffix** - Optional sections end with `_section`
- **Descriptive** - Names should be self-explanatory

### Best Practices

1. **Clear Instructions**
   - Be specific about what Claude should do
   - Provide concrete examples
   - Define success criteria clearly

2. **Structured Output**
   - Request JSON for machine-parseable responses
   - Define the exact schema expected
   - Include validation rules

3. **Context and Examples**
   - Provide relevant context
   - Include few-shot examples
   - Show both good and bad examples when relevant

4. **Error Handling**
   - Explain what to do if something goes wrong
   - Provide fallback strategies
   - Define when to escalate to human

### Example Custom Template

```markdown
# Code Review Prompt

You are reviewing code for task **{task_id}**.

## Changes to Review

{code_changes}

## Review Criteria

- Code quality and style
- Test coverage
- Security concerns
- Performance implications

## Output Format

```json
{{
  "approved": true|false,
  "issues": [
    {{
      "severity": "critical|warning|suggestion",
      "file": "path/to/file",
      "line": 42,
      "issue": "Description of issue",
      "suggestion": "How to fix"
    }}
  ],
  "summary": "Overall assessment"
}}
```

Now, review the code changes.
```

## Testing Templates

### Unit Tests

```python
from fsd.core.prompt_loader import load_prompt

def test_my_template():
    result = load_prompt(
        "my_template",
        required_var="value",
        optional_var="optional"
    )

    assert "value" in result
    assert "optional" in result
```

### Integration Tests

```python
import subprocess

def test_template_with_claude():
    prompt = load_prompt("planning", ...)

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    # Verify output format
```

## Troubleshooting

### Missing Required Variable

```
PromptRenderError: Missing required variables for template 'planning': {'task_id'}
```

**Solution:** Provide all required variables
```python
# Bad
load_prompt("planning", description="...")

# Good
load_prompt("planning", task_id="abc", description="...", priority="high", ...)
```

### Template Not Found

```
PromptLoadError: Template file not found: /path/to/prompts/nonexistent.md
```

**Solution:** Check template name and file exists
```python
# List available templates
from fsd.core.prompt_loader import PromptLoader
loader = PromptLoader()
print(loader.list_templates())
```

### Variable Not Substituted

If `{variable_name}` appears in output, the variable wasn't provided.

**Solution:** Add the variable or make it optional
```python
# In template, mark as optional section
{optional_section}

# Or provide the variable
load_prompt("template", optional_value="provided")
```

## Advanced Usage

### Custom Prompts Directory

```python
from pathlib import Path
from fsd.core.prompt_loader import PromptLoader

# Use custom directory
loader = PromptLoader(prompts_dir=Path("./my_prompts"))
prompt = loader.render_template("custom", {...})
```

### Caching

Templates are cached automatically for performance:

```python
loader = PromptLoader()

# First load - reads file
template1 = loader.load_template("planning")

# Second load - from cache
template2 = loader.load_template("planning")

# Clear cache if needed
loader.clear_cache()
```

### Dynamic Section Formatting

The loader automatically formats optional sections:

- `{context_section}` → `## Additional Context\n\n{context}`
- `{focus_files_section}` → `## Focus Files\n- file1\n- file2`
- `{success_criteria_section}` → `## Success Criteria\n\n{criteria}`

## See Also

- [Claude Code CLI Documentation](https://docs.claude.ai/claude-code)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [Task Schema](./task-schema.yaml)
- [State Machine](./architecture.md#state-machine)
