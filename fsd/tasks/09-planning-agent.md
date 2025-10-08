# Task 9: Prompt Template System

**ID:** `fsd-prompt-templates`
**Priority:** High
**Estimated Duration:** 2 hours

## Description

Create a prompt template system for guiding Claude Code CLI through different task phases.

**Key Insight:** Since Claude Code CLI is already a full-featured autonomous agent, we don't need to build separate planning/execution/validation agents. Instead, we create well-crafted prompt templates that leverage Claude Code's existing capabilities.

The Prompt Template System provides:
- **Phase-specific prompts** - Templates for planning, execution, and validation
- **Variable substitution** - Fill in task details, context, and requirements
- **Structured output** - Guide Claude to produce parseable JSON responses
- **Best practices** - Encode domain knowledge into prompt engineering
- **Reusability** - Templates work across different task types

Core capabilities:
- Load and parse markdown prompt templates
- Substitute variables (task description, context, files, criteria)
- Validate template structure and required fields
- Support conditional sections based on task properties
- Store templates in version-controlled `.fsd/prompts/`

Template structure (markdown format):
```markdown
# Planning Phase Prompt

You are helping with autonomous overnight task execution.

## Task Details
- **ID:** {task_id}
- **Description:** {description}
- **Priority:** {priority}
- **Estimated Duration:** {estimated_duration}

## Context
{context}

## Instructions
Analyze this task and create a detailed execution plan...

## Output Format
Return a JSON plan with the following structure:
{expected_plan_schema}
```

## Context

- Use markdown for readability and version control
- Support Jinja2-style variable substitution: `{variable_name}`
- Templates guide Claude Code CLI (already has all capabilities)
- No need for Anthropic SDK - just subprocess to `claude` CLI
- Store templates in `fsd/prompts/`:
  - `planning.md` - Task analysis and plan generation
  - `execution.md` - Code implementation guidance
  - `validation.md` - Testing and verification
  - `recovery.md` - Error handling and retry strategies
- Include few-shot examples in templates
- Templates are configuration, not code

## Success Criteria

- ✅ Template loader can read and parse markdown templates
- ✅ Variable substitution works correctly
- ✅ Templates validate required variables are provided
- ✅ Support for optional/conditional sections
- ✅ Templates produce structured JSON output when needed
- ✅ All phase templates created (planning, execution, validation, recovery)
- ✅ Templates include clear instructions and examples
- ✅ Unit tests for template rendering
- ✅ Documentation on creating custom templates

## Focus Files

- `fsd/prompts/planning.md` - Planning phase template
- `fsd/prompts/execution.md` - Execution phase template
- `fsd/prompts/validation.md` - Validation phase template
- `fsd/prompts/recovery.md` - Recovery phase template
- `fsd/core/prompt_loader.py` - Template loading and rendering
- `tests/test_prompt_loader.py` - Template tests
- `docs/prompt-templates.md` - Template documentation

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Prompt template system for Claude Code CLI phases"
- **Notify Slack:** No
