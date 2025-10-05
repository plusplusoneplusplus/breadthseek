# FSD Activity Tracking System

## Overview
The FSD system needs comprehensive activity tracking to monitor what the autonomous agent does overnight. This provides transparency, debugging capabilities, and accountability for all changes made.

## Activity Tracking Architecture

### 1. Command-Level Tracking
Every `claude` command execution is tracked with:

```json
{
  "timestamp": "2025-10-04T22:15:30Z",
  "task_id": "fix-auth-bug-123",
  "session_id": "fsd-20251004-220000",
  "command": "claude --dangerously-skip-permissions -p \"Fix authentication token expiration bug...\"",
  "working_directory": "/Users/yihengtao/Documents/Projects/mcp",
  "duration_ms": 45000,
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "files_changed": [
    "auth/token_manager.py",
    "tests/test_auth.py"
  ]
}
```

### 2. Git-Based Change Tracking
Every significant change creates a git commit with structured metadata:

```bash
# Commit message format
fix: Update token expiration to 24 hours

Task: fix-auth-bug-123
Session: fsd-20251004-220000
Agent: claude-cli
Duration: 45s
Files: auth/token_manager.py, tests/test_auth.py

🤖 FSD Autonomous Agent
```

### 3. File System Monitoring
Track all file system changes during execution:

```json
{
  "timestamp": "2025-10-04T22:16:15Z",
  "task_id": "fix-auth-bug-123",
  "operation": "modify",
  "file": "auth/token_manager.py",
  "lines_added": 5,
  "lines_removed": 2,
  "size_before": 2048,
  "size_after": 2156,
  "checksum_before": "abc123...",
  "checksum_after": "def456..."
}
```

### 4. Test Execution Tracking
Monitor all test runs and their results:

```json
{
  "timestamp": "2025-10-04T22:17:00Z",
  "task_id": "fix-auth-bug-123",
  "test_command": "uv run pytest tests/test_auth.py",
  "exit_code": 0,
  "duration_ms": 3500,
  "tests_run": 12,
  "tests_passed": 12,
  "tests_failed": 0,
  "coverage": 85.5,
  "output": "..."
}
```

### 5. Claude Interaction Logging
Log the prompts sent to Claude and responses received:

```json
{
  "timestamp": "2025-10-04T22:15:30Z",
  "task_id": "fix-auth-bug-123",
  "interaction_id": "claude-001",
  "prompt": "Fix authentication token expiration bug...",
  "response_summary": "Analyzed auth/token_manager.py, identified issue in TOKEN_EXPIRY constant...",
  "tools_used": ["read_file", "search_replace", "run_terminal_cmd"],
  "files_accessed": ["auth/token_manager.py", "tests/test_auth.py"],
  "duration_ms": 45000
}
```

## Storage Structure

### Log Directory Structure
```
fsd/logs/
├── sessions/
│   ├── 20251004-220000/           # Session directory
│   │   ├── session.json           # Session metadata
│   │   ├── commands.jsonl         # Command executions
│   │   ├── file_changes.jsonl     # File system changes
│   │   ├── test_runs.jsonl        # Test executions
│   │   ├── claude_interactions.jsonl # Claude conversations
│   │   └── tasks/
│   │       ├── fix-auth-bug-123/  # Per-task logs
│   │       │   ├── task.json      # Task definition
│   │       │   ├── timeline.jsonl # Chronological events
│   │       │   └── artifacts/     # Generated files
│   │       └── user-settings-page/
│   └── 20251005-220000/
├── daily_summaries/
│   ├── 2025-10-04.md             # Human-readable summary
│   └── 2025-10-05.md
└── analytics/
    ├── success_rates.json         # Success metrics
    └── performance.json           # Performance data
```

### Session Metadata
```json
{
  "session_id": "fsd-20251004-220000",
  "start_time": "2025-10-04T22:00:00Z",
  "end_time": "2025-10-05T06:00:00Z",
  "total_duration": "8h",
  "tasks_submitted": 4,
  "tasks_completed": 3,
  "tasks_failed": 1,
  "total_commits": 15,
  "total_files_changed": 23,
  "total_tests_run": 156,
  "claude_interactions": 47,
  "git_branch": "main",
  "working_directory": "/Users/yihengtao/Documents/Projects/mcp"
}
```

## Real-Time Monitoring

### Progress Tracking
```bash
# Live monitoring command
fsd monitor

# Output:
# 🤖 FSD Session: fsd-20251004-220000
# ⏰ Started: 22:00:00 (2h 15m ago)
# 📋 Tasks: 2/4 completed, 1 in progress, 1 queued
# 
# Current Task: user-settings-page
# 📝 Claude is working on: "Creating settings API endpoints"
# 📁 Files changed: 3 (backend/api/settings.py, tests/test_settings.py, ...)
# ✅ Tests: 45/45 passing
# ⏱️  Estimated completion: 1h 30m
```

### Health Monitoring
```bash
# Check system health
fsd health

# Output:
# 🟢 System Status: Healthy
# 💾 Disk Space: 45GB available
# 🧠 Memory: 6.2GB / 16GB used
# 🔄 Git Status: Clean, on branch fsd/user-settings-page
# 🐍 Claude CLI: Responsive (last ping: 30s ago)
# 📊 Success Rate: 85% (last 10 tasks)
```

## Activity Analysis

### Morning Summary Generation
```markdown
# FSD Overnight Summary - October 4, 2025

## 📊 Execution Summary
- **Duration**: 8 hours (22:00 - 06:00)
- **Tasks Completed**: 3/4 (75% success rate)
- **Files Modified**: 23 files across 8 directories
- **Commits Created**: 15 commits
- **Tests Run**: 156 tests (all passing)

## ✅ Completed Tasks

### 1. fix-auth-bug-123 (2h 15m)
- **Status**: ✅ Completed
- **Changes**: Fixed token expiration in `auth/token_manager.py`
- **Tests**: 12/12 passing
- **PR**: #456 created and ready for review

### 2. user-settings-page (4h 30m)
- **Status**: ✅ Completed  
- **Changes**: Full settings page implementation
- **Tests**: 28/28 passing, 87% coverage
- **PR**: #457 created and ready for review

## ⚠️ Issues & Blockers

### 3. refactor-database-layer
- **Status**: ❌ Failed after 1h 45m
- **Issue**: Type errors in async conversion
- **Action Needed**: Manual review of `db/models.py`
- **Branch**: `fsd/refactor-database-layer` (preserved for review)

## 📈 Metrics
- **Average Task Duration**: 2h 50m
- **Code Quality**: All tests passing, no linting errors
- **Git History**: Clean, atomic commits with good messages
- **Resource Usage**: Peak 4.2GB memory, 35% CPU

## 🎯 Next Steps
1. Review and merge PR #456 (auth fix)
2. Review and merge PR #457 (settings page)
3. Investigate database refactor type errors
4. Consider breaking down large refactor tasks
```

### Detailed Task Timeline
```bash
fsd timeline fix-auth-bug-123

# Output:
# 📋 Task Timeline: fix-auth-bug-123
# 
# 22:15:30 🎯 Task started
# 22:15:45 📖 Claude analyzed auth/token_manager.py
# 22:16:20 🔍 Identified TOKEN_EXPIRY constant issue
# 22:16:45 ✏️  Modified auth/token_manager.py (lines 45-47)
# 22:17:00 🧪 Ran pytest tests/test_auth.py (12/12 passed)
# 22:17:30 ✏️  Updated test expectations in tests/test_auth.py
# 22:18:00 🧪 Ran full test suite (156/156 passed)
# 22:18:15 📝 Created commit: "fix: Update token expiration to 24 hours"
# 22:18:30 🔀 Created PR #456
# 22:18:45 ✅ Task completed successfully
# 
# Total Duration: 3m 15s
# Files Changed: 2
# Commits: 1
# Tests Run: 168
```

## Implementation Details

### Activity Logger Class
```python
class ActivityLogger:
    def __init__(self, session_id: str, task_id: str = None):
        self.session_id = session_id
        self.task_id = task_id
        self.log_dir = Path(f"fsd/logs/sessions/{session_id}")
        
    def log_command(self, command: str, result: CommandResult):
        """Log claude command execution"""
        
    def log_file_change(self, file_path: str, operation: str):
        """Log file system changes"""
        
    def log_test_run(self, command: str, result: TestResult):
        """Log test execution"""
        
    def log_claude_interaction(self, prompt: str, response: str):
        """Log Claude conversation"""
        
    def create_checkpoint(self, description: str):
        """Create git checkpoint with metadata"""
```

### Git Integration
```python
class GitTracker:
    def create_checkpoint_commit(self, task_id: str, description: str, metadata: dict):
        """Create commit with FSD metadata"""
        commit_msg = f"{description}\n\nTask: {task_id}\n{format_metadata(metadata)}\n\n🤖 FSD Autonomous Agent"
        
    def track_file_changes(self) -> List[FileChange]:
        """Get list of changed files since last commit"""
        
    def create_task_branch(self, task_id: str) -> str:
        """Create isolated branch for task"""
```

This activity tracking system provides complete transparency into what the FSD agent does overnight, making it easy to understand, debug, and trust the autonomous coding process.
