# FSD: Autonomous Overnight Coding Agent System

## Overview
A Feature-Sliced Design system that enables a CLI-based coding agent to work autonomously overnight, executing multi-step development tasks with checkpoints, recovery mechanisms, and human-in-the-loop safeguards.

## Core Principles

### 1. **Autonomous Operation**
- Self-contained task execution without human intervention
- Intelligent error recovery and retry mechanisms
- Progress checkpointing for resumability
- Resource management (rate limits, quotas, timeouts)

### 2. **Safety & Reliability**
- Pre-execution validation and dry-run capabilities
- Git-based checkpointing (branch per task, commits per step)
- Rollback mechanisms for failed operations
- Safety constraints (no force pushes, protected branches, secret scanning)

### 3. **Observability**
- Detailed logging with structured output
- Progress tracking with time estimates
- Health checks and heartbeat monitoring
- Morning summary reports with actionable items

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Interface                           │
│  (Task submission, monitoring, configuration)                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Orchestration Layer                         │
│  • Task Queue Manager                                        │
│  • Execution Engine (sequential/parallel)                    │
│  • State Machine (planning → executing → validating)         │
│  • Checkpoint Manager                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Agent Core Layer                           │
│  • Claude CLI Agent (natural language task execution)        │
│  • Activity Tracker (comprehensive logging)                  │
│  • Safety Monitor (git, tests, secrets)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Tool Layer                                 │
│  • MCP Tools (existing plugins)                              │
│  • Git Operations (commits, branches, PRs)                   │
│  • Test Runners (pytest, npm test)                           │
│  • Code Analysis (linters, type checkers)                    │
│  • Claude CLI Interface                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 Persistence Layer                            │
│  • Task Database (Neo4j/SQLite)                              │
│  • Execution Logs (structured JSON)                          │
│  • Checkpoint Store (Git + metadata)                         │
│  • Metrics & Analytics                                       │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### Task Queue Manager
- **Purpose**: Manage overnight task pipeline
- **Features**:
  - Priority-based scheduling
  - Dependency resolution (task A before task B)
  - Time-boxed execution windows
  - Pause/resume capabilities

### Execution Engine
- **Purpose**: Execute tasks with safety guardrails
- **Features**:
  - Isolated execution environments (git branches)
  - Step-by-step execution with validation
  - Automatic retries with exponential backoff
  - Circuit breaker for repeated failures

### Claude CLI Agent
- **Purpose**: Execute tasks using Claude's built-in capabilities
- **Features**:
  - Natural language task interpretation
  - Autonomous code analysis and modification
  - Built-in tool usage (file operations, terminal commands)
  - Self-directed problem solving and recovery

### Checkpoint Manager
- **Purpose**: Enable resumability and rollback
- **Features**:
  - Git commit after each successful step
  - Store metadata (step number, timestamp, status)
  - Support resume from any checkpoint
  - Quick rollback to last known good state

## Workflow

### 1. Task Submission (Evening)
```bash
# User submits overnight tasks
fsd submit --plan "Implement user authentication system"
fsd submit --task "Fix all TypeScript errors in wu-wei extension"
fsd submit --task "Update dependencies and fix breaking changes"

# System validates and schedules
fsd queue list
fsd queue start --mode overnight
```

### 2. Autonomous Execution (Overnight)
```
For each task:
  1. Setup Phase
     - Create git branch for task
     - Initialize activity logging
     - Start checkpoint tracking

  2. Execution Phase
     - Pass natural language description to Claude CLI
     - Claude autonomously:
       * Analyzes the problem
       * Plans the approach
       * Makes code changes
       * Runs tests and validations
       * Handles errors and retries
     - FSD system monitors and logs all activity
     - Creates git commits at regular intervals

  3. Completion Phase
     - Run final validation (tests, linting)
     - Create PR if configured
     - Generate execution report
     - Update task status
```

### 3. Morning Review
```bash
# User reviews results
fsd report --overnight

# Output shows:
# ✅ Completed: 2 tasks
# ⚠️  Partial: 1 task (blocked on dependency issue)
# ❌ Failed: 1 task (tests failed after retry)
#
# Details:
# [Task 1] ✅ User authentication - PR #123 created
# [Task 2] ✅ TypeScript errors - 47 errors fixed, 2 remain (need manual review)
# [Task 3] ⚠️  Dependency updates - lodash updated, react blocked (breaking changes)
# [Task 4] ❌ Refactor database layer - tests fail, see logs

fsd review task-3  # Interactive review of blocked task
fsd approve pr-123  # Approve and merge successful PR
```

## Safety Mechanisms

### Pre-Flight Checks
- Ensure git working directory is clean
- Verify tests pass before starting
- Check for available disk space, memory
- Validate API keys and credentials
- Estimate total execution time

### During Execution
- Never modify main/master branch directly
- Each task gets isolated branch
- Commit after each successful step
- Scan for secrets before committing
- Rate limit API calls
- Monitor resource usage

### Failure Handling
- Max 3 retries per step with exponential backoff
- Different strategies per error type:
  - Network errors: retry
  - Test failures: analyze logs, attempt fix
  - Type errors: use LLM to fix
  - Resource exhaustion: pause and wait
- Escalation path for blockers

### Human Safeguards
- Never push to main without approval
- Create PRs instead of direct merges
- Mark uncertain changes for review
- Provide detailed change explanations
- Allow manual intervention checkpoints

## Configuration

### Example: `fsd.config.yaml`
```yaml
agent:
  max_execution_time: 8h  # Stop after 8 hours
  checkpoint_interval: 5m  # Commit every 5 minutes if changes
  parallel_tasks: 2  # Run 2 tasks concurrently max

claude:
  command: "claude --dangerously-skip-permissions"
  working_dir: "."
  timeout: 30m

safety:
  protected_branches: [main, master, production]
  require_tests: true
  require_type_check: true
  secret_scan: true
  auto_merge: false  # Never auto-merge PRs

notifications:
  slack_webhook: ${SLACK_WEBHOOK_URL}
  email: ${NOTIFICATION_EMAIL}
  events: [task_completed, task_failed, execution_finished]

logging:
  level: INFO
  format: json
  output: ./fsd/logs/
  retention: 30d
```

## Task Definition Format

### Example: `task.yaml`
```yaml
id: auth-implementation
description: |
  Implement a user authentication system for the application.
  
  Users should be able to:
  - Register with email and password
  - Login and receive a JWT token
  - Access protected routes with authentication
  
  Use bcrypt for password hashing and make sure to add proper validation.
  Create database migrations for the users table and add comprehensive tests.
  Aim for >80% test coverage on the auth endpoints.

priority: high
estimated_duration: 4h

success_criteria: |
  - Registration and login work correctly
  - JWT tokens are issued and validated
  - Protected routes require authentication
  - All tests pass with >80% coverage
  - No secrets are committed to git

on_completion:
  create_pr: true
  pr_title: "feat: Implement user authentication system"
  notify_slack: true
```

## Integration with Existing MCP

### Leveraging Current Infrastructure
- **MCP Tools**: Use existing command_execution, browser automation tools
- **Server**: Extend `/server/` with FSD orchestration endpoints
- **Plugins**: Integrate git_tools, knowledge_indexer for context
- **Utils**: Use async_jobs for background execution

### New Components Needed
```
/fsd/
├── agents/          # Planning, Execution, Validation, Recovery agents
├── orchestrator/    # Task queue, execution engine, state machine
├── checkpoint/      # Git-based checkpoint management
├── config/          # Configuration schemas and defaults
├── tasks/           # Task definition library
├── logs/            # Execution logs and reports
└── cli/             # Command-line interface
```

## Success Metrics

### Overnight Session
- **Tasks Completed**: % of tasks fully finished
- **Code Quality**: Test coverage, type safety, lint score
- **Reliability**: Success rate, recovery rate
- **Efficiency**: Time per task, resource usage

### Morning Review
- **Review Time**: How long to understand results
- **Merge Rate**: % of PRs merged without changes
- **Blocker Rate**: % of tasks blocked for human input
- **Rework Rate**: % of code requiring fixes

## Future Enhancements

1. **Learning System**: Learn from past executions to improve planning
2. **Cost Optimization**: Estimate and minimize LLM API costs
3. **Distributed Execution**: Run tasks across multiple machines
4. **Interactive Mode**: Allow human intervention during execution
5. **Template Library**: Pre-built task templates for common operations
6. **Collaboration**: Multi-agent coordination for complex tasks
