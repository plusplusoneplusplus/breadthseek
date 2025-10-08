# FSD Web Interface

A modern web-based dashboard for managing and monitoring the FSD (Autonomous Overnight Coding Agent System).

## Quick Start

```bash
# Start the web server (default: http://127.0.0.1:10010)
fsd serve

# Custom port
fsd serve --port 3000

# Allow external connections
fsd serve --host 0.0.0.0

# Development mode with auto-reload
fsd serve --reload
```

## Features

### 🚀 System Initialization

- **Initialize FSD from UI**: First-time setup with a single click
- **Automatic detection**: Shows welcome screen when FSD is not initialized
- **One-click setup**: Creates all necessary directories and configuration files

### 📝 Task Creation

#### Natural Language Input
- **Plain English descriptions**: "HIGH priority: Fix login bug in auth.py. Should take 30m"
- **Auto-extraction of**:
  - Priority (LOW, MEDIUM, HIGH, CRITICAL)
  - Duration (e.g., "30m", "2h", "1h30m")
  - Focus files (auto-detected from file mentions)
  - Task ID generation from description
  - PR title generation with conventional commit prefixes

#### Structured Form Input
- **Required fields**: Task ID, description, priority, estimated duration
- **Optional fields**: Context, focus files, success criteria
- **PR configuration**: Auto-create PR with custom title
- **Validation**: Real-time input validation with helpful hints

### 📊 Task Management

#### Task List View
- **Real-time updates**: Auto-refresh every 5 seconds
- **Status filtering**: View all, queued, running, completed, or failed tasks
- **Priority badges**: Color-coded priority indicators
- **Status badges**: Visual status indicators
- **Quick actions**: Inline buttons for common operations

#### Task Detail View
- **Complete information**: All task fields and metadata
- **Focus files list**: Formatted file paths with icons
- **Success criteria**: Formatted display with syntax highlighting
- **Context-aware actions**: Different buttons based on task status

### 🎯 Task Operations

#### Individual Task Actions
- **For Queued Tasks**:
  - View details
  - Cancel (marks as failed)
  - Delete (removes from queue)

- **For Running Tasks**:
  - View details
  - Cancel execution

- **For Completed/Failed Tasks**:
  - View details
  - Re-queue (mark as queued again)
  - Delete (removes from queue)

#### Bulk Operations
- **Clear Completed**: Remove all completed and failed tasks at once
- **Smart counting**: Shows how many tasks will be affected
- **Safe operation**: Cannot delete running tasks

### 📈 System Monitoring

#### Status Dashboard
- **System state**: Active or Idle indicator with live status
- **Task counters**: Real-time counts by status (queued, running, completed, failed)
- **Total tasks**: Overall task count
- **Visual indicators**: Color-coded badges and animated status dots

#### Activity Feed
- **Recent events**: Last 20 activity events
- **Timestamps**: Local time formatting
- **Task tracking**: Links to related tasks
- **Auto-refresh**: Updates every 5 seconds

### 🎨 User Interface

#### Design Features
- **Modern gradient design**: Purple-themed with smooth animations
- **Responsive layout**: Works on desktop and mobile
- **Modal dialogs**: Clean, focused interfaces for task operations
- **Floating Action Button**: Quick access to create new tasks
- **Tab navigation**: Switch between natural language and structured input
- **Loading states**: Clear feedback during operations
- **Error handling**: User-friendly error messages
- **Success notifications**: Confirmation messages for completed actions

#### Accessibility
- **Keyboard navigation**: Full keyboard support
- **Click-outside to close**: Intuitive modal interactions
- **Clear labels**: Descriptive form labels and hints
- **Visual feedback**: Hover states and transitions

## REST API Endpoints

### System
- `GET /api/health` - Health check
- `GET /api/status` - System status and task counts
- `GET /api/config` - Current FSD configuration
- `POST /api/init` - Initialize FSD in current directory

### Tasks
- `GET /api/tasks` - List all tasks (optional status filter)
- `GET /api/tasks/{task_id}` - Get specific task details
- `POST /api/tasks/natural` - Create task from natural language
- `POST /api/tasks/structured` - Create task from structured data
- `DELETE /api/tasks/{task_id}` - Remove task from queue
- `PATCH /api/tasks/{task_id}/status` - Update task status
- `POST /api/tasks/{task_id}/cancel` - Cancel a task
- `POST /api/tasks/bulk-delete` - Bulk delete by status filter

### Activity
- `GET /api/activity` - Recent activity events (configurable limit)

### API Documentation
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Technology Stack

### Backend
- **FastAPI**: High-performance async web framework
- **Pydantic**: Data validation and serialization
- **PyYAML**: YAML file handling
- **Uvicorn**: ASGI server

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **HTML5/CSS3**: Modern web standards
- **Fetch API**: Async HTTP requests
- **CommonMark**: Markdown rendering support

## File Structure

```
fsd/web/
├── README.md           # This file
├── __init__.py         # Package initialization
├── server.py           # FastAPI backend server
└── static/
    └── index.html      # Single-page application
```

## Features in Detail

### Natural Language Processing
- **Priority extraction**: Recognizes CRITICAL, HIGH, MEDIUM, LOW keywords
- **Duration parsing**: Supports "30m", "2h", "1h30m" formats
- **File detection**: Auto-detects .py, .js, .ts, .tsx, .jsx, .java, .go, .rs, .yaml, .yml, .json, .md files
- **ID generation**: Creates valid task IDs from descriptions
- **PR title generation**: Conventional commit format (feat:, fix:, refactor:, etc.)

### Safety Features
- **Running task protection**: Cannot delete tasks that are currently executing
- **Status validation**: Only allows valid status transitions
- **Error handling**: Graceful failure with user-friendly messages
- **Timeout handling**: 10-second timeout for API requests
- **Data validation**: Server-side validation using Pydantic models

### Performance
- **Auto-refresh**: Smart refresh that only updates when initialized
- **Parallel loading**: Multiple API calls in parallel using Promise.allSettled
- **Efficient sorting**: Tasks sorted by priority and creation time
- **Lazy loading**: Task details loaded on-demand
- **Error recovery**: Individual component failures don't break the entire UI

## Development

### Running in Development Mode

```bash
# With auto-reload on file changes
fsd serve --reload

# The server will restart automatically when you modify:
# - fsd/web/server.py
# - fsd/web/static/index.html
# - Any imported modules
```

### Testing the API

```bash
# Health check
curl http://localhost:10010/api/health

# Get system status
curl http://localhost:10010/api/status

# List all tasks
curl http://localhost:10010/api/tasks

# Create task from natural language
curl -X POST http://localhost:10010/api/tasks/natural \
  -H "Content-Type: application/json" \
  -d '{"text": "HIGH priority: Fix bug in auth.py. Takes 30m"}'
```

### API Documentation

Visit `http://localhost:10010/docs` for interactive API documentation where you can:
- Browse all endpoints
- View request/response schemas
- Test API calls directly from the browser
- Download OpenAPI specification

## Browser Compatibility

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Opera 76+

## License

Same as the FSD project (MIT License)
