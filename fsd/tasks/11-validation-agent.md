# Task 11: Validation Agent

**ID:** `fsd-validation-agent`
**Priority:** High
**Estimated Duration:** 5 hours

## Description

Implement the Validation Agent that verifies code changes through tests and quality checks.

The Validation Agent is responsible for:
- **Test execution** - Running project test suites
- **Code quality checks** - Running linters, type checkers, formatters
- **Security scanning** - Checking for secrets and vulnerabilities
- **Result analysis** - Parsing and interpreting validation results
- **Failure reporting** - Providing detailed feedback on failures

Core capabilities:
- **Test runner integration:**
  - Detect test framework (pytest, jest, npm test, cargo test, etc.)
  - Execute tests with proper configuration
  - Parse test output and extract results
  - Report pass/fail with detailed error messages

- **Code quality checks:**
  - Type checking (mypy, TypeScript, etc.)
  - Linting (ruff, eslint, clippy, etc.)
  - Code formatting (black, prettier, rustfmt, etc.)
  - Detect issues and report violations

- **Security checks:**
  - Secret scanning (detect API keys, passwords)
  - Dependency vulnerability scanning
  - Code security patterns (SQL injection, XSS, etc.)

- **Result aggregation:**
  - Combine results from all validators
  - Generate summary report
  - Determine overall pass/fail status
  - Provide actionable feedback for failures

Validation workflow:
1. Detect project type and available validators
2. Run all applicable checks in parallel when possible
3. Parse and normalize results
4. Store results in `.fsd/validation/<task-id>/`
5. Update state machine:
   - `validating` → `completed` (all pass)
   - `validating` → `executing` (failures, trigger retry)
   - `validating` → `failed` (critical errors)

## Context

- Support multiple language ecosystems (Python, JavaScript, Rust, etc.)
- Run validators in isolated environments when possible
- Parse structured output (JSON, TAP, JUnit XML) when available
- Fall back to regex parsing for plain text output
- Set reasonable timeouts for long-running test suites
- Integrate with checkpoint system before validation
- Log all validation results to activity tracker

## Success Criteria

- ✅ Can detect and run pytest, npm test, and other test frameworks
- ✅ Parses test output and extracts pass/fail results
- ✅ Runs type checking and linting tools
- ✅ Secret scanning detects common secret patterns
- ✅ Results are stored in structured format
- ✅ Validation failures trigger appropriate state transitions
- ✅ Detailed error reports for debugging
- ✅ Unit tests with mocked tool outputs
- ✅ Integration tests with real test projects

## Focus Files

- `fsd/agents/validation_agent.py`
- `fsd/agents/test_runner.py`
- `fsd/agents/quality_checker.py`
- `fsd/agents/security_scanner.py`
- `fsd/agents/result_parser.py`
- `tests/test_validation_agent.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Validation Agent with testing and quality checks"
- **Notify Slack:** No
