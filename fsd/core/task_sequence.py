"""Task sequence management for monotonically incrementing numeric IDs."""

import json
import threading
from pathlib import Path
from typing import Optional


# Thread lock for sequence counter operations
_counter_lock = threading.Lock()


def get_next_task_id(fsd_dir: Optional[Path] = None) -> int:
    """Get the next sequential task ID.

    This function is thread-safe and ensures monotonically increasing IDs.

    Args:
        fsd_dir: FSD directory path (defaults to .fsd in current directory)

    Returns:
        Next sequential numeric task ID

    Raises:
        RuntimeError: If FSD directory doesn't exist
    """
    if fsd_dir is None:
        fsd_dir = Path.cwd() / ".fsd"

    if not fsd_dir.exists():
        raise RuntimeError("FSD not initialized. Run 'fsd init' first.")

    counter_file = fsd_dir / ".task_counter"

    with _counter_lock:
        # Read current counter value
        if counter_file.exists():
            try:
                with open(counter_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    current_id = data.get("next_id", 1)
            except (json.JSONDecodeError, KeyError):
                # If file is corrupted, start from 1
                current_id = 1
        else:
            # First task
            current_id = 1

        # Write next counter value
        next_id = current_id + 1
        counter_data = {
            "next_id": next_id,
            "last_assigned": current_id
        }

        with open(counter_file, "w", encoding="utf-8") as f:
            json.dump(counter_data, f, indent=2)

        return current_id


def get_current_counter(fsd_dir: Optional[Path] = None) -> int:
    """Get the current counter value without incrementing.

    Args:
        fsd_dir: FSD directory path (defaults to .fsd in current directory)

    Returns:
        Current counter value (next ID to be assigned)
    """
    if fsd_dir is None:
        fsd_dir = Path.cwd() / ".fsd"

    if not fsd_dir.exists():
        return 1

    counter_file = fsd_dir / ".task_counter"

    if not counter_file.exists():
        return 1

    try:
        with open(counter_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("next_id", 1)
    except (json.JSONDecodeError, KeyError):
        return 1


def reset_counter(fsd_dir: Optional[Path] = None, value: int = 1) -> None:
    """Reset the task counter to a specific value.

    WARNING: This should only be used for testing or maintenance.

    Args:
        fsd_dir: FSD directory path (defaults to .fsd in current directory)
        value: Value to reset counter to (default: 1)

    Raises:
        RuntimeError: If FSD directory doesn't exist
        ValueError: If value is less than 1
    """
    if value < 1:
        raise ValueError("Counter value must be at least 1")

    if fsd_dir is None:
        fsd_dir = Path.cwd() / ".fsd"

    if not fsd_dir.exists():
        raise RuntimeError("FSD not initialized. Run 'fsd init' first.")

    counter_file = fsd_dir / ".task_counter"

    with _counter_lock:
        counter_data = {
            "next_id": value,
            "last_assigned": value - 1
        }

        with open(counter_file, "w", encoding="utf-8") as f:
            json.dump(counter_data, f, indent=2)
