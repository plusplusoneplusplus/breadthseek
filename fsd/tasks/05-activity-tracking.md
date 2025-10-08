# Task 5: Activity Tracking Foundation

**ID:** `fsd-activity-tracking`
**Priority:** Medium
**Estimated Duration:** 3 hours

## Description

Implement the core activity tracking system to monitor all FSD operations.

Create the activity logging infrastructure:
- `ActivityLogger` class that logs different types of events
- Structured JSON logging for all activities
- Log different event types: command execution, file changes, git operations, etc.
- Session management (each overnight run gets a unique session ID)
- Log storage in organized directory structure (`.fsd/logs/sessions/`)

Event types to track:
- Session start/end with metadata
- Task start/completion/failure
- Claude CLI command executions
- File system changes (before/after checksums)
- Git operations (commits, branch creation)
- Test runs and results

The system should:
- Use structured logging (JSON format)
- Be thread-safe for concurrent operations
- Handle log rotation and retention
- Provide easy querying of recent activities
- Store logs in a way that's easy to analyze later

## Context

- Follow the activity tracking design from `fsd/docs/activity-tracking.md`
- Use Python's logging module with JSON formatter
- Store logs in `.fsd/logs/` directory
- Each session gets its own subdirectory
- Make it easy to add new event types later

## Success Criteria

- ✅ ActivityLogger class is implemented and functional
- ✅ Can log all major event types with proper structure
- ✅ Session management works correctly
- ✅ Log files are organized and easy to navigate
- ✅ Thread-safe logging for concurrent operations
- ✅ Unit tests cover all logging scenarios

## Focus Files

- `fsd/tracking/`
- `fsd/tracking/activity_logger.py`
- `fsd/tracking/session.py`
- `tests/test_activity_tracking.py`

## On Completion

- **Create PR:** Yes
- **PR Title:** "feat: Activity tracking foundation with structured logging"
- **Notify Slack:** No
