"""FSD Web Server - FastAPI backend for viewing FSD system information."""

import json
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio

from fsd.config.loader import load_config
from fsd.core.task_schema import TaskDefinition, load_task_from_yaml, Priority, CompletionActions
from fsd.core.state_machine import TaskStateMachine
from fsd.core.state_persistence import StatePersistence
from fsd.core.task_state import TaskState

app = FastAPI(
    title="FSD Web Interface",
    description="Web interface for FSD Autonomous Overnight Coding Agent System",
    version="0.1.0",
)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Request models
class CreateTaskNaturalLanguage(BaseModel):
    """Create task from natural language."""
    text: str


class CreateTaskStructured(BaseModel):
    """Create task from structured data."""
    id: str
    description: str
    priority: str
    estimated_duration: str
    context: Optional[str] = None
    focus_files: Optional[List[str]] = None
    success_criteria: Optional[str] = None
    create_pr: bool = True
    pr_title: Optional[str] = None
    notify_slack: bool = False


# Response models
class TaskInfo(BaseModel):
    """Task information model."""

    id: str
    description: str
    priority: str
    estimated_duration: str
    status: str
    context: Optional[str] = None
    focus_files: Optional[List[str]] = None
    success_criteria: Optional[str] = None


class CompletedTaskInfo(BaseModel):
    """Extended task information for completed tasks."""

    id: str
    description: str
    priority: str
    estimated_duration: str
    status: str
    context: Optional[str] = None
    focus_files: Optional[List[str]] = None
    success_criteria: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    retry_count: Optional[int] = None
    error_message: Optional[str] = None


class SystemStatus(BaseModel):
    """System status model."""

    execution_active: bool
    task_counts: Dict[str, int]
    total_tasks: int
    fsd_initialized: bool


class ActivityEvent(BaseModel):
    """Activity event model."""

    timestamp: str
    event_type: str
    message: str
    task_id: Optional[str] = None


# Helper functions
def get_fsd_dir() -> Path:
    """Get the .fsd directory."""
    return Path.cwd() / ".fsd"


def is_fsd_initialized() -> bool:
    """Check if FSD is initialized in the current directory."""
    return get_fsd_dir().exists()


def get_state_machine() -> Optional[TaskStateMachine]:
    """Get the state machine instance."""
    if not is_fsd_initialized():
        return None

    state_dir = get_fsd_dir() / "state"
    if not state_dir.exists():
        return None

    try:
        persistence = StatePersistence(state_dir=state_dir)
        return TaskStateMachine(persistence_handler=persistence)
    except Exception as e:
        print(f"Warning: Failed to initialize state machine: {e}")
        return None


def get_task_status(task_id: str) -> str:
    """Get the status of a task."""
    if not is_fsd_initialized():
        return "unknown"

    # Try to get status from state machine first
    state_machine = get_state_machine()
    if state_machine and state_machine.has_task(task_id):
        try:
            state = state_machine.get_state(task_id)
            return state.value
        except Exception:
            pass

    # Fall back to status file
    status_file = get_fsd_dir() / "status" / f"{task_id}.json"

    if not status_file.exists():
        return "queued"

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            status_data = json.load(f)
        return status_data.get("status", "queued")
    except Exception:
        return "queued"


def get_all_tasks() -> List[Dict[str, Any]]:
    """Get all tasks with their status."""
    if not is_fsd_initialized():
        return []

    queue_dir = get_fsd_dir() / "queue"
    if not queue_dir.exists():
        return []

    tasks = []
    task_files = list(queue_dir.glob("*.yaml"))
    
    # Log if there are many tasks
    if len(task_files) > 100:
        print(f"Warning: Loading {len(task_files)} tasks, this may be slow")

    for task_file in task_files:
        try:
            # Load task with better error handling
            task = load_task_from_yaml(task_file)
            status = get_task_status(task.id)

            # Get file stats safely
            try:
                stat = task_file.stat()
                created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
                modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except (OSError, ValueError) as e:
                print(f"Warning: Failed to get file stats for {task_file}: {e}")
                created_at = datetime.now().isoformat()
                modified_at = created_at

            tasks.append({
                "task": task,
                "status": status,
                "file": str(task_file),
                "created_at": created_at,
                "modified_at": modified_at,
            })
        except FileNotFoundError:
            # Task file was deleted between glob and load
            print(f"Warning: Task file disappeared: {task_file}")
            continue
        except ValueError as e:
            # Invalid task definition
            print(f"Warning: Invalid task file {task_file}: {e}")
            continue
        except Exception as e:
            # Other errors - log but continue
            print(f"Error: Failed to load {task_file}: {type(e).__name__}: {e}")
            continue

    # Sort by priority and creation time
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    try:
        tasks.sort(
            key=lambda t: (
                priority_order.get(t["task"].priority.value, 99),
                t["created_at"],
            )
        )
    except Exception as e:
        print(f"Warning: Failed to sort tasks: {e}")
        # Return unsorted tasks rather than failing completely

    return tasks


def get_activity_logs(limit: int = 50) -> List[ActivityEvent]:
    """Get recent activity logs."""
    if not is_fsd_initialized():
        return []

    logs_dir = get_fsd_dir() / "logs"
    if not logs_dir.exists():
        return []

    # For now, return placeholder activity
    # This will be enhanced with actual log parsing
    events = []

    # Check for task status changes
    status_dir = get_fsd_dir() / "status"
    if status_dir.exists():
        for status_file in sorted(status_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]:
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)

                task_id = status_file.stem
                timestamp = datetime.fromtimestamp(status_file.stat().st_mtime).isoformat()

                events.append(ActivityEvent(
                    timestamp=timestamp,
                    event_type="status_change",
                    message=f"Task '{task_id}' status changed to {status_data.get('status', 'unknown')}",
                    task_id=task_id,
                ))
            except Exception:
                pass

    return events[:limit]


# API Routes
@app.get("/")
async def root() -> HTMLResponse:
    """Serve the main web interface."""
    html_file = Path(__file__).parent / "static" / "index.html"

    if not html_file.exists():
        return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head><title>FSD Web Interface</title></head>
            <body>
                <h1>FSD Web Interface</h1>
                <p>Frontend not found. Please ensure static files are in place.</p>
                <p>API is available at <a href="/docs">/docs</a></p>
            </body>
            </html>
        """)

    with open(html_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
    }


@app.get("/api/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    """Get system status."""
    if not is_fsd_initialized():
        return SystemStatus(
            execution_active=False,
            task_counts={"queued": 0, "running": 0, "completed": 0, "failed": 0},
            total_tasks=0,
            fsd_initialized=False,
        )

    tasks = get_all_tasks()

    task_counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
    for task_info in tasks:
        status = task_info["status"]
        if status in task_counts:
            task_counts[status] += 1

    execution_active = task_counts["running"] > 0

    return SystemStatus(
        execution_active=execution_active,
        task_counts=task_counts,
        total_tasks=len(tasks),
        fsd_initialized=True,
    )


@app.get("/api/tasks", response_model=List[TaskInfo])
async def list_tasks(status: Optional[str] = None) -> List[TaskInfo]:
    """List all tasks, optionally filtered by status."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    try:
        tasks = get_all_tasks()
    except Exception as e:
        print(f"Error loading tasks: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load tasks: {str(e)}")

    # Filter by status if requested
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    try:
        return [
            TaskInfo(
                id=t["task"].id,
                description=t["task"].description,
                priority=t["task"].priority.value,
                estimated_duration=t["task"].estimated_duration,
                status=t["status"],
                context=t["task"].context,
                focus_files=t["task"].focus_files,
                success_criteria=t["task"].success_criteria,
            )
            for t in tasks
        ]
    except Exception as e:
        print(f"Error serializing tasks: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serialize tasks: {str(e)}")


@app.get("/api/tasks/{task_id}", response_model=TaskInfo)
async def get_task(task_id: str) -> TaskInfo:
    """Get details of a specific task."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    tasks = get_all_tasks()

    for task_info in tasks:
        if task_info["task"].id == task_id:
            return TaskInfo(
                id=task_info["task"].id,
                description=task_info["task"].description,
                priority=task_info["task"].priority.value,
                estimated_duration=task_info["task"].estimated_duration,
                status=task_info["status"],
                context=task_info["task"].context,
                focus_files=task_info["task"].focus_files,
                success_criteria=task_info["task"].success_criteria,
            )

    raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")


@app.get("/api/tasks/completed/recent", response_model=List[CompletedTaskInfo])
async def get_recent_completed_tasks(limit: int = 10) -> List[CompletedTaskInfo]:
    """Get recent completed tasks with execution metadata."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    state_machine = get_state_machine()
    if not state_machine:
        # Fall back to simple completed task list
        tasks = get_all_tasks()
        completed = [t for t in tasks if t["status"] in ["completed", "failed"]]
        completed.sort(key=lambda t: t.get("modified_at", ""), reverse=True)

        return [
            CompletedTaskInfo(
                id=t["task"].id,
                description=t["task"].description,
                priority=t["task"].priority.value,
                estimated_duration=t["task"].estimated_duration,
                status=t["status"],
                context=t["task"].context,
                focus_files=t["task"].focus_files,
                success_criteria=t["task"].success_criteria,
                completed_at=t.get("modified_at"),
            )
            for t in completed[:limit]
        ]

    # Get completed tasks from state machine
    completed_tasks = []

    try:
        all_task_ids = state_machine.list_tasks()

        for task_id in all_task_ids:
            try:
                state_info = state_machine.get_state_info(task_id)

                # Only include completed or failed tasks
                if state_info.current_state not in [TaskState.COMPLETED, TaskState.FAILED]:
                    continue

                # Load task definition
                task_file = get_fsd_dir() / "queue" / f"{task_id}.yaml"
                if not task_file.exists():
                    continue

                task = load_task_from_yaml(task_file)

                # Extract metadata
                metadata = state_info.metadata or {}
                completed_at = None
                duration_seconds = None

                # Get completion timestamp from history
                if state_info.history:
                    last_transition = state_info.history[-1]
                    completed_at = last_transition.timestamp.isoformat()

                    # Calculate duration if we have start time
                    if len(state_info.history) > 0:
                        start_time = state_info.history[0].timestamp
                        end_time = last_transition.timestamp
                        duration_seconds = (end_time - start_time).total_seconds()

                completed_tasks.append(CompletedTaskInfo(
                    id=task.id,
                    description=task.description,
                    priority=task.priority.value,
                    estimated_duration=task.estimated_duration,
                    status=state_info.current_state.value,
                    context=task.context,
                    focus_files=task.focus_files,
                    success_criteria=task.success_criteria,
                    completed_at=completed_at,
                    duration_seconds=duration_seconds,
                    retry_count=metadata.get("retry_count", 0),
                    error_message=metadata.get("error"),
                ))
            except Exception as e:
                print(f"Warning: Failed to load completed task {task_id}: {e}")
                continue

        # Sort by completion time (most recent first)
        completed_tasks.sort(
            key=lambda t: t.completed_at or "",
            reverse=True
        )

        return completed_tasks[:limit]

    except Exception as e:
        print(f"Error loading completed tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load completed tasks: {str(e)}")


@app.post("/api/tasks/natural")
async def create_task_from_natural_language(request: CreateTaskNaturalLanguage) -> Dict[str, Any]:
    """Create a new task from natural language text."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    try:
        task = _create_task_from_text(request.text)
        _submit_task(task)

        return {
            "success": True,
            "message": f"Task '{task.id}' created successfully",
            "task": TaskInfo(
                id=task.id,
                description=task.description,
                priority=task.priority.value,
                estimated_duration=task.estimated_duration,
                status="queued",
                context=task.context,
                focus_files=task.focus_files,
                success_criteria=task.success_criteria,
            ).model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create task: {str(e)}")


@app.post("/api/tasks/structured")
async def create_task_from_structured(request: CreateTaskStructured) -> Dict[str, Any]:
    """Create a new task from structured data."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    try:
        # Build completion actions
        on_completion = None
        if request.create_pr or request.notify_slack:
            on_completion = CompletionActions(
                create_pr=request.create_pr,
                pr_title=request.pr_title,
                notify_slack=request.notify_slack,
            )

        # Create task
        task = TaskDefinition(
            id=request.id,
            description=request.description,
            priority=Priority(request.priority),
            estimated_duration=request.estimated_duration,
            context=request.context,
            focus_files=request.focus_files,
            success_criteria=request.success_criteria,
            on_completion=on_completion,
        )

        _submit_task(task)

        return {
            "success": True,
            "message": f"Task '{task.id}' created successfully",
            "task": TaskInfo(
                id=task.id,
                description=task.description,
                priority=task.priority.value,
                estimated_duration=task.estimated_duration,
                status="queued",
                context=task.context,
                focus_files=task.focus_files,
                success_criteria=task.success_criteria,
            ).model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create task: {str(e)}")


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str) -> Dict[str, Any]:
    """Remove a task from the queue."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    try:
        fsd_dir = get_fsd_dir()
        queue_dir = fsd_dir / "queue"
        task_file = queue_dir / f"{task_id}.yaml"

        if not task_file.exists():
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        # Check if task is running
        status = get_task_status(task_id)
        if status == "running":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete running task '{task_id}'. Stop the task first."
            )

        # Delete task file
        task_file.unlink()

        # Delete status file if it exists
        status_file = fsd_dir / "status" / f"{task_id}.json"
        if status_file.exists():
            status_file.unlink()

        return {
            "success": True,
            "message": f"Task '{task_id}' removed from queue"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")


@app.patch("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, new_status: str) -> Dict[str, Any]:
    """Update the status of a task."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    valid_statuses = ["queued", "running", "completed", "failed"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    try:
        fsd_dir = get_fsd_dir()
        queue_dir = fsd_dir / "queue"
        task_file = queue_dir / f"{task_id}.yaml"

        if not task_file.exists():
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        # Update status
        status_dir = fsd_dir / "status"
        status_dir.mkdir(exist_ok=True)
        status_file = status_dir / f"{task_id}.json"

        status_data = {
            "status": new_status,
            "updated_at": datetime.now().isoformat(),
        }

        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

        return {
            "success": True,
            "message": f"Task '{task_id}' status updated to '{new_status}'",
            "status": new_status
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a running or queued task."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    try:
        fsd_dir = get_fsd_dir()
        queue_dir = fsd_dir / "queue"
        task_file = queue_dir / f"{task_id}.yaml"

        if not task_file.exists():
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        # Get current status
        current_status = get_task_status(task_id)

        if current_status == "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel completed task '{task_id}'"
            )

        if current_status == "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel failed task '{task_id}'"
            )

        # Update status to failed with cancellation note
        status_dir = fsd_dir / "status"
        status_dir.mkdir(exist_ok=True)
        status_file = status_dir / f"{task_id}.json"

        status_data = {
            "status": "failed",
            "updated_at": datetime.now().isoformat(),
            "cancelled": True,
            "reason": "Cancelled by user"
        }

        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

        return {
            "success": True,
            "message": f"Task '{task_id}' cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


@app.post("/api/tasks/bulk-delete")
async def bulk_delete_tasks(status_filter: Optional[str] = None) -> Dict[str, Any]:
    """Bulk delete tasks by status filter."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    valid_filters = ["completed", "failed", "all"]
    if status_filter and status_filter not in valid_filters:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filter. Must be one of: {', '.join(valid_filters)}"
        )

    try:
        fsd_dir = get_fsd_dir()
        queue_dir = fsd_dir / "queue"

        if not queue_dir.exists():
            return {"success": True, "message": "No tasks to delete", "deleted_count": 0}

        deleted_count = 0
        tasks = get_all_tasks()

        for task_info in tasks:
            task_id = task_info["task"].id
            task_status = task_info["status"]

            # Determine if task should be deleted
            should_delete = False
            if status_filter == "all":
                # Don't delete running tasks
                should_delete = task_status != "running"
            elif status_filter == "completed":
                should_delete = task_status == "completed"
            elif status_filter == "failed":
                should_delete = task_status == "failed"

            if should_delete:
                task_file = queue_dir / f"{task_id}.yaml"
                if task_file.exists():
                    task_file.unlink()
                    deleted_count += 1

                # Delete status file
                status_file = fsd_dir / "status" / f"{task_id}.json"
                if status_file.exists():
                    status_file.unlink()

        message = f"Deleted {deleted_count} task(s)"
        if status_filter:
            message = f"Deleted {deleted_count} {status_filter} task(s)"

        return {
            "success": True,
            "message": message,
            "deleted_count": deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk delete: {str(e)}")


@app.get("/api/activity", response_model=List[ActivityEvent])
async def get_activity(limit: int = 50) -> List[ActivityEvent]:
    """Get recent activity events."""
    if not is_fsd_initialized():
        return []

    return get_activity_logs(limit=limit)


@app.post("/api/execution/start")
async def start_execution(
    mode: str = "interactive",
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """Start task execution.
    
    Args:
        mode: Execution mode (interactive, autonomous, overnight)
        task_id: Optional specific task ID to execute
    """
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")
    
    valid_modes = ["interactive", "autonomous", "overnight"]
    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}"
        )
    
    try:
        from pathlib import Path
        import subprocess
        import threading
        import time
        
        fsd_dir = get_fsd_dir()
        logs_dir = fsd_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Get queued tasks
        tasks = get_all_tasks()
        queued_tasks = [t for t in tasks if t["status"] == "queued"]
        
        if not queued_tasks:
            raise HTTPException(status_code=400, detail="No queued tasks found")
        
        # Determine which tasks to execute
        tasks_to_execute = []
        if task_id:
            task_found = False
            for task_info in queued_tasks:
                if task_info["task"].id == task_id:
                    task_found = True
                    tasks_to_execute = [task_info]
                    break
            
            if not task_found:
                raise HTTPException(
                    status_code=404,
                    detail=f"Task '{task_id}' not found or not queued"
                )
        else:
            tasks_to_execute = queued_tasks
        
        # Execute tasks in background thread with logging
        def run_execution():
            for task_info in tasks_to_execute:
                task = task_info["task"]
                task_log_file = logs_dir / f"{task.id}.log"
                
                try:
                    # Update status to running
                    status_dir = fsd_dir / "status"
                    status_dir.mkdir(exist_ok=True)
                    status_file = status_dir / f"{task.id}.json"
                    
                    with open(status_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "status": "running",
                            "updated_at": datetime.now().isoformat(),
                            "mode": mode
                        }, f, indent=2)
                    
                    # Write execution logs
                    with open(task_log_file, "a", encoding="utf-8") as log:
                        log.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "message": f"Starting task execution in {mode} mode",
                            "task_id": task.id
                        }) + "\n")
                        
                        log.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "message": f"Task: {task.description}",
                            "task_id": task.id
                        }) + "\n")
                        
                        log.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "message": f"Priority: {task.priority.value}, Duration: {task.estimated_duration}",
                            "task_id": task.id
                        }) + "\n")
                    
                    # Simulate task execution (since actual agent execution isn't implemented)
                    time.sleep(2)  # Simulate some work
                    
                    with open(task_log_file, "a", encoding="utf-8") as log:
                        log.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "level": "WARN",
                            "message": "Task execution engine not yet fully implemented - this is a placeholder",
                            "task_id": task.id
                        }) + "\n")
                        
                        log.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "message": "Task marked as completed (placeholder execution)",
                            "task_id": task.id
                        }) + "\n")
                    
                    # Update status to completed
                    with open(status_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "status": "completed",
                            "updated_at": datetime.now().isoformat(),
                            "mode": mode,
                            "note": "Placeholder execution - full agent implementation pending"
                        }, f, indent=2)
                    
                except Exception as e:
                    # Log error and mark as failed
                    error_msg = str(e)
                    print(f"Execution error for task {task.id}: {error_msg}")
                    
                    with open(task_log_file, "a", encoding="utf-8") as log:
                        log.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "level": "ERROR",
                            "message": f"Task execution failed: {error_msg}",
                            "task_id": task.id,
                            "error": error_msg
                        }) + "\n")
                    
                    with open(status_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "status": "failed",
                            "updated_at": datetime.now().isoformat(),
                            "mode": mode,
                            "error": error_msg
                        }, f, indent=2)
        
        thread = threading.Thread(target=run_execution, daemon=True)
        thread.start()
        
        return {
            "success": True,
            "message": f"Task execution started in {mode} mode - check logs for progress",
            "mode": mode,
            "task_id": task_id,
            "queued_tasks_count": len(queued_tasks),
            "note": "Execution engine is a placeholder - full agent implementation pending"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start execution: {str(e)}"
        )


@app.post("/api/execution/stop")
async def stop_execution() -> Dict[str, Any]:
    """Stop task execution."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")
    
    try:
        # Find running tasks and mark them as failed (cancelled)
        tasks = get_all_tasks()
        running_tasks = [t for t in tasks if t["status"] == "running"]
        
        if not running_tasks:
            return {
                "success": True,
                "message": "No running tasks to stop",
                "stopped_count": 0
            }
        
        fsd_dir = get_fsd_dir()
        status_dir = fsd_dir / "status"
        
        for task_info in running_tasks:
            task_id = task_info["task"].id
            status_file = status_dir / f"{task_id}.json"
            
            status_data = {
                "status": "failed",
                "updated_at": datetime.now().isoformat(),
                "cancelled": True,
                "reason": "Stopped by user via web interface"
            }
            
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)
        
        return {
            "success": True,
            "message": f"Stopped {len(running_tasks)} running task(s)",
            "stopped_count": len(running_tasks)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop execution: {str(e)}"
        )


@app.get("/api/logs/{task_id}")
async def get_task_logs(
    task_id: str,
    lines: int = 100,
    level: Optional[str] = None
) -> Dict[str, Any]:
    """Get logs for a specific task.
    
    Args:
        task_id: Task ID to get logs for
        lines: Number of lines to return (default: 100)
        level: Filter by log level (DEBUG, INFO, WARN, ERROR)
    """
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")
    
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    if level and level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}"
        )
    
    try:
        fsd_dir = get_fsd_dir()
        logs_dir = fsd_dir / "logs"
        task_log_file = logs_dir / f"{task_id}.log"
        
        if not task_log_file.exists():
            return {
                "task_id": task_id,
                "logs": [],
                "message": "No logs found for this task"
            }
        
        # Read and parse log file
        log_entries = []
        
        with open(task_log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # Try to parse as JSON
                    entry = json.loads(line)
                    
                    # Filter by level if specified
                    if level and entry.get("level") != level:
                        continue
                    
                    log_entries.append(entry)
                
                except json.JSONDecodeError:
                    # Handle non-JSON log lines
                    log_entries.append({
                        "timestamp": "unknown",
                        "level": "INFO",
                        "message": line,
                        "raw": True
                    })
        
        # Return last N entries
        recent_entries = log_entries[-lines:] if lines else log_entries
        
        return {
            "task_id": task_id,
            "logs": recent_entries,
            "total_count": len(log_entries),
            "returned_count": len(recent_entries)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read logs: {str(e)}"
        )


@app.get("/api/logs")
async def get_system_logs(
    lines: int = 100,
    level: Optional[str] = None
) -> Dict[str, Any]:
    """Get system-wide logs from all tasks.
    
    Args:
        lines: Number of lines to return (default: 100)
        level: Filter by log level (DEBUG, INFO, WARN, ERROR)
    """
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")
    
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    if level and level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}"
        )
    
    try:
        fsd_dir = get_fsd_dir()
        logs_dir = fsd_dir / "logs"
        
        if not logs_dir.exists():
            return {
                "logs": [],
                "message": "No logs directory found"
            }
        
        # Collect logs from all task files
        all_entries = []
        
        for log_file in logs_dir.glob("*.log"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            entry = json.loads(line)
                            
                            # Filter by level if specified
                            if level and entry.get("level") != level:
                                continue
                            
                            # Add task_id from filename
                            entry["task_id"] = log_file.stem
                            all_entries.append(entry)
                        
                        except json.JSONDecodeError:
                            all_entries.append({
                                "timestamp": "unknown",
                                "level": "INFO",
                                "message": line,
                                "task_id": log_file.stem,
                                "raw": True
                            })
            
            except Exception as e:
                print(f"Warning: Failed to read {log_file}: {e}")
        
        # Sort by timestamp and take last N entries
        all_entries.sort(key=lambda e: e.get("timestamp", ""))
        recent_entries = all_entries[-lines:] if lines else all_entries
        
        return {
            "logs": recent_entries,
            "total_count": len(all_entries),
            "returned_count": len(recent_entries)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read system logs: {str(e)}"
        )


@app.get("/api/logs/{task_id}/stream")
async def stream_task_logs(
    task_id: str,
    level: Optional[str] = None
):
    """Stream logs for a specific task in real-time using Server-Sent Events.
    
    Args:
        task_id: Task ID to stream logs for
        level: Filter by log level (DEBUG, INFO, WARN, ERROR)
    """
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")
    
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    if level and level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}"
        )
    
    async def log_generator():
        """Generate log events as they are written to the file."""
        fsd_dir = get_fsd_dir()
        logs_dir = fsd_dir / "logs"
        task_log_file = logs_dir / f"{task_id}.log"
        
        # Track file position
        last_position = 0
        last_size = 0
        
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'task_id': task_id})}\n\n"
        
        try:
            while True:
                # Check if file exists and has changed
                if task_log_file.exists():
                    current_size = task_log_file.stat().st_size
                    
                    # Only read if file size changed
                    if current_size > last_size:
                        with open(task_log_file, "r", encoding="utf-8") as f:
                            f.seek(last_position)
                            new_content = f.read()
                            
                            if new_content:
                                # Parse new log entries
                                for line in new_content.strip().split("\n"):
                                    if line.strip():
                                        try:
                                            entry = json.loads(line)
                                            
                                            # Filter by level if specified
                                            if level and entry.get("level") != level:
                                                continue
                                            
                                            # Send log entry as SSE event
                                            yield f"data: {json.dumps({'type': 'log', 'entry': entry})}\n\n"
                                        
                                        except json.JSONDecodeError:
                                            # Handle non-JSON log lines
                                            entry = {
                                                "timestamp": "unknown",
                                                "level": "INFO",
                                                "message": line,
                                                "raw": True
                                            }
                                            yield f"data: {json.dumps({'type': 'log', 'entry': entry})}\n\n"
                            
                            last_position = f.tell()
                        
                        last_size = current_size
                
                # Send heartbeat every 5 seconds to keep connection alive
                yield f": heartbeat\n\n"
                
                # Wait before checking again
                await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            # Client disconnected
            yield f"data: {json.dumps({'type': 'disconnected'})}\n\n"
    
    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )


@app.get("/api/config")
async def get_config() -> Dict[str, Any]:
    """Get current FSD configuration."""
    if not is_fsd_initialized():
        raise HTTPException(status_code=400, detail="FSD not initialized")

    try:
        config = load_config()
        # Convert to dict for JSON serialization
        return config.model_dump(exclude_none=True, mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@app.post("/api/init")
async def initialize_fsd(force: bool = False) -> Dict[str, Any]:
    """Initialize FSD in the current directory."""
    fsd_dir = get_fsd_dir()

    # Check if already initialized
    if fsd_dir.exists() and not force:
        raise HTTPException(
            status_code=400,
            detail="FSD already initialized. Use force=true to reinitialize.",
        )

    try:
        # Create .fsd directory structure
        fsd_dir.mkdir(exist_ok=True)
        (fsd_dir / "logs").mkdir(exist_ok=True)
        (fsd_dir / "tasks").mkdir(exist_ok=True)
        (fsd_dir / "reports").mkdir(exist_ok=True)
        (fsd_dir / "queue").mkdir(exist_ok=True)
        (fsd_dir / "status").mkdir(exist_ok=True)

        # Create default config
        config_path = fsd_dir / "config.yaml"
        if not config_path.exists() or force:
            default_config = _get_default_config()
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)

        # Create .gitignore for FSD directory
        gitignore_path = fsd_dir / ".gitignore"
        if not gitignore_path.exists() or force:
            gitignore_content = """# FSD generated files
logs/
reports/
*.tmp
*.lock
"""
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(gitignore_content)

        # Create example task
        example_task_path = fsd_dir / "tasks" / "example.yaml"
        if not example_task_path.exists() or force:
            example_task = _get_example_task()
            with open(example_task_path, "w", encoding="utf-8") as f:
                yaml.dump(example_task, f, default_flow_style=False, indent=2)

        return {
            "success": True,
            "message": "FSD initialized successfully",
            "fsd_dir": str(fsd_dir),
            "config_path": str(config_path),
            "example_task_path": str(example_task_path),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize FSD: {str(e)}"
        )


def _get_default_config() -> Dict[str, Any]:
    """Get default FSD configuration."""
    return {
        "agent": {
            "max_execution_time": "8h",
            "checkpoint_interval": "5m",
            "parallel_tasks": 1,
            "mode": "autonomous",
        },
        "claude": {
            "command": "claude --dangerously-skip-permissions",
            "working_dir": ".",
            "timeout": "30m",
        },
        "safety": {
            "protected_branches": ["main", "master", "production"],
            "require_tests": True,
            "require_type_check": True,
            "secret_scan": True,
            "auto_merge": False,
        },
        "git": {
            "branch_prefix": "fsd/",
            "user": {"name": "FSD Agent", "email": "fsd-agent@example.com"},
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "output_dir": ".fsd/logs",
            "retention_days": 30,
        },
        "notifications": {
            "enabled": False,
            "slack": {"enabled": False, "webhook_url": "${SLACK_WEBHOOK_URL}"},
        },
    }


def _get_example_task() -> Dict[str, Any]:
    """Get example task definition."""
    return {
        "id": "example-task",
        "description": (
            "This is an example task. Replace this with your actual task description.\n\n"
            "Describe what you want the autonomous agent to do in natural language. "
            "Be specific about the requirements, files to focus on, and success criteria."
        ),
        "priority": "medium",
        "estimated_duration": "1h",
        "context": (
            "Add any additional context here that might help the agent understand "
            "the task better, such as relevant files, coding patterns to follow, "
            "or constraints to keep in mind."
        ),
        "success_criteria": (
            "Define what success looks like:\n"
            "- All tests pass\n"
            "- Code follows project conventions\n"
            "- No breaking changes\n"
            "- Documentation is updated if needed"
        ),
        "on_completion": {
            "create_pr": True,
            "pr_title": "feat: Example task implementation",
            "notify_slack": False,
        },
    }


def _submit_task(task: TaskDefinition) -> None:
    """Submit task to the queue."""
    fsd_dir = get_fsd_dir()

    if not fsd_dir.exists():
        raise ValueError("FSD not initialized")

    # Create queue directory if it doesn't exist
    queue_dir = fsd_dir / "queue"
    queue_dir.mkdir(exist_ok=True)

    # Save task to queue
    task_file = queue_dir / f"{task.id}.yaml"
    if task_file.exists():
        raise ValueError(f"Task '{task.id}' already exists in queue")

    # Convert task to dict and save
    task_dict = task.model_dump(exclude_none=True, mode="json")
    with open(task_file, "w", encoding="utf-8") as f:
        yaml.dump(task_dict, f, default_flow_style=False, indent=2)


def _create_task_from_text(text: str) -> TaskDefinition:
    """Create a task from natural language text."""
    # Extract priority
    priority, text_without_priority = _extract_priority(text)

    # Extract duration
    duration, text_without_duration = _extract_duration(text_without_priority)

    # Extract focus files
    focus_files, clean_description = _extract_focus_files(text_without_duration)

    # Generate task ID from description
    task_id = _generate_task_id(clean_description)

    # Build task
    task = TaskDefinition(
        id=task_id,
        description=clean_description.strip(),
        priority=priority,
        estimated_duration=duration,
        focus_files=focus_files if focus_files else None,
        on_completion=CompletionActions(
            create_pr=True,
            pr_title=_generate_pr_title(clean_description)
        )
    )

    return task


def _extract_priority(text: str) -> Tuple[Priority, str]:
    """Extract priority from text."""
    text_upper = text.upper()

    # Check for priority keywords
    priority_patterns = [
        (r'\b(CRITICAL|CRIT)\b[:\s]?', Priority.CRITICAL),
        (r'\b(HIGH|URGENT)\b[:\s]?', Priority.HIGH),
        (r'\b(MEDIUM|MED|NORMAL)\b[:\s]?', Priority.MEDIUM),
        (r'\b(LOW)\b[:\s]?', Priority.LOW),
    ]

    for pattern, priority in priority_patterns:
        match = re.search(pattern, text_upper)
        if match:
            # Remove priority keyword from text
            text = text[:match.start()] + text[match.end():]
            return priority, text.strip()

    # Default to medium priority
    return Priority.MEDIUM, text


def _extract_duration(text: str) -> Tuple[str, str]:
    """Extract duration from text."""
    # Patterns for duration: "30m", "2h", "1h30m", "takes 2h", "should take 30m"
    duration_patterns = [
        r'\b(?:takes?|should take|needs?|requires?)\s+(\d+h(?:\d+m)?|\d+m)\b',
        r'\b(\d+h(?:\d+m)?|\d+m)\b',
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            duration = match.group(1) if match.lastindex else match.group(0)
            # Clean up duration to just the time part
            duration = re.search(r'(\d+h(?:\d+m)?|\d+m)', duration).group(1)
            # Remove duration from text
            text = text[:match.start()] + text[match.end():]
            return duration.lower(), text.strip()

    # Default duration estimation based on text length
    return _estimate_duration(text), text


def _estimate_duration(text: str) -> str:
    """Estimate duration based on text complexity."""
    word_count = len(text.split())

    # Simple heuristic based on word count and keywords
    keywords_long = ['implement', 'refactor', 'migrate', 'design', 'architecture']
    keywords_short = ['fix', 'update', 'change', 'add']

    text_lower = text.lower()

    if any(keyword in text_lower for keyword in keywords_long) or word_count > 30:
        return "2h"
    elif any(keyword in text_lower for keyword in keywords_short) or word_count > 15:
        return "1h"
    else:
        return "30m"


def _extract_focus_files(text: str) -> Tuple[Optional[List[str]], str]:
    """Extract file paths from text."""
    # Pattern for files: explicit "files:" or common extensions
    files = []

    # Check for explicit "files:" mentions
    files_pattern = r'(?:files?)\s*[:\s]\s*([a-zA-Z0-9_/\-.,\s]+\.(?:py|js|ts|tsx|jsx|java|go|rs|yaml|yml|json|md)(?:\s*,\s*[a-zA-Z0-9_/\-]+\.(?:py|js|ts|tsx|jsx|java|go|rs|yaml|yml|json|md))*)'
    match = re.search(files_pattern, text, re.IGNORECASE)

    if match:
        files_str = match.group(1)
        # Split by comma and clean up
        files = [f.strip() for f in re.split(r'[,\s]+', files_str) if '.' in f]
        # Remove from text
        text = text[:match.start()] + text[match.end():]
    else:
        # Look for file mentions with common extensions (but keep them in description)
        file_pattern = r'\b([a-zA-Z0-9_/\-]+\.(?:py|js|ts|tsx|jsx|java|go|rs|yaml|yml|json|md))\b'
        matches = re.finditer(file_pattern, text)

        for match in matches:
            files.append(match.group(1))

        # Don't remove file mentions from text - they're part of the description
        # Just clean up extra spaces
        text = re.sub(r'\s+', ' ', text)

    return files if files else None, text.strip()


def _generate_task_id(description: str) -> str:
    """Generate a task ID from description."""
    # Take first significant words (up to 5)
    words = re.findall(r'\b[a-zA-Z]+\b', description.lower())

    # Filter out common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    significant_words = [w for w in words if w not in stop_words][:5]

    # Join with hyphens
    task_id = '-'.join(significant_words)

    # Ensure minimum length
    if len(task_id) < 3:
        task_id = 'task-' + task_id

    # Truncate if too long
    if len(task_id) > 50:
        task_id = task_id[:50].rstrip('-')

    return task_id


def _generate_pr_title(description: str) -> str:
    """Generate a PR title from description."""
    # Take first sentence or first 60 chars
    first_sentence = description.split('.')[0].strip()

    # Detect conventional commit type
    text_lower = first_sentence.lower()
    if 'fix' in text_lower or 'bug' in text_lower:
        prefix = "fix: "
    elif 'refactor' in text_lower:
        prefix = "refactor: "
    elif 'test' in text_lower:
        prefix = "test: "
    elif 'doc' in text_lower:
        prefix = "docs: "
    else:
        prefix = "feat: "

    title = prefix + first_sentence

    # Truncate if too long
    if len(title) > 72:
        title = title[:69] + "..."

    return title


def run_server(host: str = "127.0.0.1", port: int = 10010, reload: bool = False) -> None:
    """Run the web server."""
    import uvicorn

    uvicorn.run(
        "fsd.web.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_server(reload=True)
