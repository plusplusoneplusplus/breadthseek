# Task 9: Planning Agent

**ID:** `fsd-planning-agent`
**Priority:** High
**Estimated Duration:** 5 hours

## Description

Implement the Planning Agent that decomposes tasks into executable steps using LLM.

The Planning Agent is responsible for:
- **Task analysis** - Understanding the task requirements and context
- **Step decomposition** - Breaking down the task into detailed, actionable steps
- **Complexity estimation** - Estimating time and difficulty for each step
- **Validation criteria** - Defining how to verify each step succeeded
- **Recovery strategies** - Planning for potential failures

Core capabilities:
- Parse task description and context
- Analyze codebase to understand current state
- Use LLM (Claude) to generate execution plan
- Create structured plan with steps, substeps, and checkpoints
- Estimate execution time based on complexity
- Identify files that will likely be modified
- Define test and validation requirements
- Output plan in structured format for execution

Plan structure:
```python
{
  "task_id": "...",
  "steps": [
    {
      "step_number": 1,
      "description": "...",
      "estimated_duration": "15m",
      "files_to_modify": ["..."],
      "validation": "...",
      "checkpoint": true
    }
  ],
  "total_estimate": "2h",
  "complexity": "medium"
}
```

## Context

- Integrate with Claude API (use Anthropic SDK)
- Use project context from codebase analysis
- Consider using retrieval for large codebases
- Store plans in `.fsd/plans/<task-id>.json`
- Plan should be detailed enough for automated execution
- Use few-shot examples to guide LLM planning
- Handle API errors and rate limits gracefully

## Success Criteria

- ✅ Can analyze task description and generate detailed plan
- ✅ Uses codebase context to inform planning
- ✅ Plans include all required fields (steps, validation, etc.)
- ✅ Time estimates are reasonable
- ✅ Plans are stored in structured JSON format
- ✅ Handles LLM API errors gracefully
- ✅ Unit tests with mocked LLM responses
- ✅ Integration test with real API (optional, manual)

## Focus Files

- `fsd/agents/planning_agent.py`
- `fsd/agents/llm_client.py`
- `fsd/agents/codebase_analyzer.py`
- `fsd/agents/plan_schema.py`
- `tests/test_planning_agent.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Planning Agent with LLM-powered task decomposition"
- **Notify Slack:** No
