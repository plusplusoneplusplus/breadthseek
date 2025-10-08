# FSD Test Suite

Comprehensive test suite for the FSD (Feature-Sliced Design) autonomous overnight coding agent system.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and pytest configuration
├── fixtures/                # Test data files (YAML configs, sample tasks)
├── integration/             # Integration tests
│   ├── test_task_submission.py
│   └── test_full_workflow.py
├── test_task_schema.py      # Task definition and validation tests
├── test_state_machine.py    # State machine and persistence tests
├── test_checkpoint.py       # Checkpoint and git integration tests
├── test_config.py           # Configuration loading and validation tests
├── test_activity_tracking.py # Activity logging tests
└── test_cli.py              # CLI command tests
```

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run specific test file
```bash
uv run pytest tests/test_task_schema.py
```

### Run tests by marker
```bash
# Unit tests only (fast)
uv run pytest -m unit

# Integration tests
uv run pytest -m integration

# Skip slow tests
uv run pytest -m "not slow"
```

### Run with coverage report
```bash
uv run pytest --cov=fsd --cov-report=html
# Open htmlcov/index.html to view detailed coverage
```

### Run specific test
```bash
uv run pytest tests/test_task_schema.py::TestTaskDefinition::test_valid_task_minimal
```

### Run in parallel (faster)
```bash
uv run pytest -n auto
```

## Test Categories

### Unit Tests
- Fast, isolated tests
- Mock external dependencies
- Test individual functions and classes
- Marked with `@pytest.mark.unit`

### Integration Tests
- Test component interactions
- May use temporary files and git repositories
- Test end-to-end workflows
- Marked with `@pytest.mark.integration`

### Git Tests
- Require git operations
- Use temporary git repositories
- Test checkpoint and rollback functionality
- Marked with `@pytest.mark.git`

## Writing Tests

### Using Fixtures

Shared fixtures are defined in `conftest.py`:

```python
def test_my_feature(sample_task, tmp_fsd_dir):
    # sample_task: Pre-configured TaskDefinition
    # tmp_fsd_dir: Temporary .fsd directory structure
    ...
```

### Common Fixtures

- `tmp_fsd_dir` - Temporary .fsd directory with standard structure
- `git_repo` - Temporary git repository with initial commit
- `sample_task` - Basic task definition
- `complete_task` - Task with all fields populated
- `state_machine` - TaskStateMachine instance
- `checkpoint_manager` - CheckpointManager instance

### Test Data

Sample data files in `fixtures/`:
- `sample_tasks.yaml` - Various task definitions
- `sample_config.yaml` - FSD configuration
- `invalid_tasks.yaml` - Invalid tasks for validation testing
- `multiple_tasks.yaml` - Batch task testing

## Coverage Goals

- **Overall:** ≥80% code coverage
- **Critical modules:** ≥90% coverage
  - `core/state_machine.py`
  - `core/checkpoint_manager.py`
  - `core/task_schema.py`

## Best Practices

1. **Test naming:** Use descriptive names that explain what is being tested
   ```python
   def test_task_submission_creates_queue_file()
   def test_invalid_transition_raises_error()
   ```

2. **Arrange-Act-Assert:** Structure tests clearly
   ```python
   def test_example():
       # Arrange
       task = TaskDefinition(...)

       # Act
       result = process_task(task)

       # Assert
       assert result.success
   ```

3. **Use markers:** Tag tests appropriately
   ```python
   @pytest.mark.unit
   @pytest.mark.integration
   @pytest.mark.slow
   ```

4. **Isolation:** Tests should not depend on each other
   - Use fixtures for setup
   - Clean up in teardown
   - Don't rely on test execution order

5. **Fast feedback:** Keep unit tests fast (< 1s each)
   - Mock external dependencies
   - Use in-memory data when possible
   - Reserve slow tests for integration

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to main branch
- Nightly builds

CI requirements:
- All tests must pass
- Coverage must be ≥80%
- No new linting errors

## Troubleshooting

### Git tests failing
Ensure git is configured:
```bash
git config --global user.name "Test User"
git config --global user.email "test@example.com"
```

### Coverage too low
View detailed coverage report:
```bash
uv run pytest --cov-report=html
open htmlcov/index.html
```

### Slow test suite
Run only unit tests:
```bash
uv run pytest -m unit
```

Or use parallel execution:
```bash
uv run pytest -n auto
```
