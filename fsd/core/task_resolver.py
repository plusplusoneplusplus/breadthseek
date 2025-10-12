"""Task ID resolver - resolve numeric IDs or partial IDs to full task IDs."""

from pathlib import Path
from typing import Dict, Optional

from .task_schema import load_task_from_yaml


def resolve_task_id(task_id_or_number: str, fsd_dir: Optional[Path] = None) -> Optional[str]:
    """Resolve a task ID, numeric ID, or partial ID to a full task ID.

    Args:
        task_id_or_number: Task ID, numeric ID (e.g., "4" or "#4"), or partial ID
        fsd_dir: FSD directory (default: current directory/.fsd)

    Returns:
        Full task ID if found, None otherwise

    Examples:
        resolve_task_id("4") -> "can-you-add-support-can"
        resolve_task_id("#4") -> "can-you-add-support-can"
        resolve_task_id("can-you-add-support-can") -> "can-you-add-support-can"
        resolve_task_id("can-you-add") -> "can-you-add-support-can" (if unique)
    """
    if fsd_dir is None:
        fsd_dir = Path.cwd() / ".fsd"

    if not fsd_dir.exists():
        return None

    # Remove # prefix if present
    search_term = task_id_or_number.lstrip("#")

    # Check if it's a numeric ID
    if search_term.isdigit():
        numeric_id = int(search_term)
        return _resolve_numeric_id(numeric_id, fsd_dir)

    # Check if it's already a full task ID
    queue_file = fsd_dir / "queue" / f"{search_term}.yaml"
    if queue_file.exists():
        return search_term

    # Check in state directory
    state_file = fsd_dir / "state" / f"{search_term}.json"
    if state_file.exists():
        return search_term

    # Try partial match
    return _resolve_partial_id(search_term, fsd_dir)


def _resolve_numeric_id(numeric_id: int, fsd_dir: Path) -> Optional[str]:
    """Resolve a numeric ID to a task ID.

    Searches both queue and state directories to build a comprehensive mapping.
    This ensures numeric IDs work for tasks in all states (queued, planning,
    executing, validating, completed, failed).

    Args:
        numeric_id: Numeric task ID
        fsd_dir: FSD directory

    Returns:
        Task ID if found, None otherwise
    """
    # Build comprehensive numeric ID mapping
    numeric_id_map = _build_numeric_id_mapping(fsd_dir)

    return numeric_id_map.get(numeric_id)


def _build_numeric_id_mapping(fsd_dir: Path) -> Dict[int, str]:
    """Build a mapping of numeric IDs to task IDs.

    This function searches all task files in the queue directory to create
    a comprehensive mapping. Tasks maintain their numeric IDs throughout
    their lifecycle, even as they transition between states.

    Args:
        fsd_dir: FSD directory

    Returns:
        Dictionary mapping numeric IDs to task IDs
    """
    mapping = {}

    # Search queue directory for all tasks
    queue_dir = fsd_dir / "queue"
    if queue_dir.exists():
        for task_file in sorted(queue_dir.glob("*.yaml")):
            try:
                task = load_task_from_yaml(task_file)
                if task.numeric_id is not None:
                    mapping[task.numeric_id] = task.id
            except Exception:
                # Silently skip malformed task files
                pass

    return mapping


def _resolve_partial_id(partial_id: str, fsd_dir: Path) -> Optional[str]:
    """Resolve a partial task ID to a full task ID.

    Args:
        partial_id: Partial task ID
        fsd_dir: FSD directory

    Returns:
        Full task ID if unique match found, None otherwise
    """
    matches = []

    # Search in queue
    queue_dir = fsd_dir / "queue"
    if queue_dir.exists():
        for task_file in queue_dir.glob("*.yaml"):
            task_id = task_file.stem
            if task_id.startswith(partial_id):
                matches.append(task_id)

    # Search in state
    state_dir = fsd_dir / "state"
    if state_dir.exists():
        for state_file in state_dir.glob("*.json"):
            task_id = state_file.stem
            if task_id.startswith(partial_id) and task_id not in matches:
                matches.append(task_id)

    # Return if unique match
    if len(matches) == 1:
        return matches[0]

    return None


def get_task_display_name(task_id: str, numeric_id: Optional[int] = None) -> str:
    """Get a display name for a task (with numeric ID if available).

    Args:
        task_id: Full task ID
        numeric_id: Numeric ID (if available)

    Returns:
        Display name like "#4: can-you-add-support-can" or just "can-you-add-support-can"
    """
    if numeric_id is not None:
        return f"#{numeric_id}: {task_id}"
    return task_id
