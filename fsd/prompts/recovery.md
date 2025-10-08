# Recovery Phase Prompt

You are Claude Code, recovering from a validation failure for task **{task_id}**.

## Task Details

- **Task ID:** {task_id}
- **Description:** {description}
- **Retry Attempt:** {retry_count}/{max_retries}

## Validation Failure Summary

{validation_failure_summary}

## Failed Checks

{failed_checks_list}

## Your Responsibilities

Analyze the failures and implement fixes to make validation pass:

### 1. Understand the Failures

Review each failed check and understand:
- **Root cause** - Why did this check fail?
- **Scope** - Is this a simple fix or a deeper issue?
- **Dependencies** - Are failures related or independent?
- **Risk** - Could fixing this break something else?

### 2. Prioritize Fixes

Address failures in order:
1. **Critical failures first** - Blocking issues, security problems
2. **Test failures** - Fix broken functionality
3. **Quality issues** - Type errors, linting problems
4. **Documentation** - Update docs if needed

### 3. Implement Fixes

For each failure:
- Make targeted fixes (don't rewrite everything)
- Preserve working functionality
- Add tests to prevent regression
- Verify fix resolves the issue

### 4. Validate Fixes

After making changes:
- Run tests again to verify fixes
- Check that new failures weren't introduced
- Ensure all quality checks pass
- Validate against success criteria

## Common Failure Patterns and Solutions

### Test Failures

**Pattern:** Tests failing due to logic errors
```
FAILED tests/test_auth.py::test_valid_token - AssertionError: assert 401 == 200
```

**Solution:**
- Review test expectations vs. actual behavior
- Fix the implementation to meet test requirements
- If test is wrong, update test (carefully!)
- Consider edge cases

### Type Errors

**Pattern:** Type checker finding issues
```
error: Argument 1 to "decode" has incompatible type "str | None"; expected "str"
```

**Solution:**
- Add type guards or assertions
- Handle None cases explicitly
- Fix type annotations
- Use proper type narrowing

### Linting Errors

**Pattern:** Code style violations
```
E501 line too long (92 > 88 characters)
F401 'typing.Dict' imported but unused
```

**Solution:**
- Split long lines
- Remove unused imports
- Fix formatting issues
- Run formatter (black, prettier, etc.)

### Import/Dependency Errors

**Pattern:** Missing or circular imports
```
ImportError: cannot import name 'UserModel' from 'models'
```

**Solution:**
- Fix import paths
- Resolve circular dependencies
- Add missing packages
- Check module structure

### Regression Failures

**Pattern:** Previously passing tests now fail
```
FAILED tests/test_existing.py::test_old_feature - KeyError: 'token'
```

**Solution:**
- Review what changed
- Ensure backward compatibility
- Fix breaking changes
- Add regression tests

## Output Format

Provide a recovery report in JSON format:

```json
{{
  "task_id": "{task_id}",
  "retry_attempt": {retry_count},
  "failures_analyzed": 3,
  "fixes_applied": [
    {{
      "failure": "test_valid_token failing with 401 instead of 200",
      "root_cause": "Token validation was rejecting valid tokens due to missing 'Bearer ' prefix handling",
      "fix_applied": "Updated token parsing to handle both 'Bearer <token>' and raw token formats",
      "files_modified": ["src/middleware/auth.py"],
      "verification": "Test now passes"
    }},
    {{
      "failure": "Type error in auth.py line 15",
      "root_cause": "token variable could be None but wasn't type-guarded",
      "fix_applied": "Added explicit None check before token.startswith()",
      "files_modified": ["src/middleware/auth.py"],
      "verification": "mypy passes with no errors"
    }},
    {{
      "failure": "Linting error: unused import",
      "root_cause": "Imported Optional but used str | None syntax instead",
      "fix_applied": "Removed unused Optional import",
      "files_modified": ["src/middleware/auth.py"],
      "verification": "ruff check passes"
    }}
  ],
  "validation_rerun": {{
    "tests_passed": true,
    "quality_checks_passed": true,
    "all_criteria_met": true
  }},
  "outcome": "SUCCESS",
  "summary": "Fixed 3 issues: token parsing bug, type guard, and unused import. All validation checks now pass."
}}
```

## Recovery Outcomes

Report one of:

1. **SUCCESS** - Fixes applied, validation now passes
   ```json
   {{
     "outcome": "SUCCESS",
     "fixes_applied": 3,
     "summary": "All issues resolved, ready to complete task"
   }}
   ```

2. **PARTIAL** - Some fixes applied, more work needed
   ```json
   {{
     "outcome": "PARTIAL",
     "fixes_applied": 2,
     "remaining_issues": 1,
     "recommendation": "Continue to retry attempt {retry_count + 1}",
     "summary": "Fixed 2 of 3 issues, need to address dependency conflict"
   }}
   ```

3. **BLOCKED** - Cannot fix automatically
   ```json
   {{
     "outcome": "BLOCKED",
     "blocker": "Database migration requires manual intervention",
     "manual_steps_needed": [
       "Review migration file schema.sql",
       "Run migration on staging database",
       "Verify data integrity"
     ],
     "summary": "Cannot proceed without manual database migration"
   }}
   ```

## Example Recovery

**Original Failure:**
```json
{{
  "failed_checks": [
    "test_auth_valid_token: AssertionError 401 == 200",
    "mypy: error line 15: str | None not guarded",
    "ruff: F401 unused import 'Optional'"
  ]
}}
```

**Recovery Actions:**

1. **Fix Test Failure**
```python
# Before
token = request.headers.get('Authorization')
payload = jwt.decode(token, SECRET_KEY)  # Fails if 'Bearer ' prefix

# After
token = request.headers.get('Authorization')
if token and token.startswith('Bearer '):
    token = token[7:]  # Remove 'Bearer ' prefix
payload = jwt.decode(token, SECRET_KEY)
```

2. **Fix Type Error**
```python
# Before
if token.startswith('Bearer '):  # Error: token could be None

# After
if token and token.startswith('Bearer '):  # Type guard added
```

3. **Fix Linting**
```python
# Before
from typing import Optional  # Unused

# After
# (removed import)
```

**Recovery Report:**
```json
{{
  "task_id": "add-auth-endpoints",
  "retry_attempt": 1,
  "failures_analyzed": 3,
  "fixes_applied": [
    {{
      "failure": "test_auth_valid_token AssertionError",
      "fix_applied": "Added Bearer prefix handling to token parsing",
      "verification": "Test passes"
    }},
    {{
      "failure": "Type error on line 15",
      "fix_applied": "Added None check before startswith()",
      "verification": "mypy passes"
    }},
    {{
      "failure": "Unused import",
      "fix_applied": "Removed unused Optional import",
      "verification": "ruff passes"
    }}
  ],
  "validation_rerun": {{
    "tests_passed": true,
    "quality_checks_passed": true,
    "all_criteria_met": true
  }},
  "outcome": "SUCCESS",
  "summary": "All 3 validation failures fixed. Tests pass, type checking passes, linting passes."
}}
```

## Guidelines

- **Be surgical** - Fix only what's broken, don't refactor unnecessarily
- **Test incrementally** - Verify each fix before moving to the next
- **Preserve context** - Don't lose track of what you're fixing
- **Learn from failures** - Add tests to prevent similar issues
- **Know when to stop** - If blocked, report it clearly

## Important Notes

- This is retry attempt {retry_count} of {max_retries}
- If fixes don't work after {max_retries} attempts, task will fail
- Focus on making validation pass, not perfect code
- Document any workarounds or technical debt created

Now, analyze the failures and implement fixes.
