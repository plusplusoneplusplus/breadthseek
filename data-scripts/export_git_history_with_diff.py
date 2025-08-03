
import subprocess
import json
import argparse
from datetime import datetime, timezone


def export_git_history_with_diff(output_file, author=None, limit=None, start=None, end=None):
    # Build git log command with optional filters and commit range
    cmd = ["git", "log", "--pretty=format:%H"]
    # Handle commit range
    range_spec = None
    if start and end:
        # To include the start commit, use <start>^..<end>
        range_spec = f"{start}^..{end}"
    elif start:
        range_spec = f"{start}^..HEAD"
    elif end:
        range_spec = f"{end}"
    if range_spec:
        cmd.append(range_spec)
    if author:
        cmd.append(f"--author={author}")
    if limit:
        cmd.append(f"-n{limit}")

    hashes = subprocess.check_output(cmd, text=True).splitlines()

    with open(output_file, "w", encoding="utf-8") as f:
        for h in hashes:
            meta = subprocess.check_output(
                ["git", "show", h, "--quiet", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso-strict"],
                text=True
            ).strip()
            parts = meta.split("|", 4)
            if len(parts) != 5:
                continue
            # Get parent commit(s)
            parent_str = subprocess.check_output(
                ["git", "show", "-s", "--pretty=%P", h],
                text=True
            ).strip()
            parents = parent_str.split() if parent_str else []
            # Convert date string to UTC ISO 8601
            try:
                # Parse the date string (which may have offset info)
                dt = datetime.fromisoformat(parts[3])
                dt_utc = dt.astimezone(timezone.utc)
                date_utc = dt_utc.isoformat().replace('+00:00', 'Z')
            except Exception:
                date_utc = parts[3]  # fallback to original if parsing fails
            diff = subprocess.check_output(
                ["git", "show", h, "--format=", "--patch"],
                text=True
            )
            commit = {
                "hash": parts[0],
                "parents": parents,
                "author": parts[1],
                "email": parts[2],
                "date": date_utc,
                "subject": parts[4],
                "diff": diff,
            }
            f.write(json.dumps(commit, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export git commit history with diffs.")
    parser.add_argument("--output", default="git_history_with_diff.jsonl", help="Output file name")
    parser.add_argument("--author", help="Filter by author (name or email)")
    parser.add_argument("--limit", type=int, help="Limit to last N commits")
    parser.add_argument("--start", help="Start commit (inclusive)")
    parser.add_argument("--end", help="End commit (inclusive, e.g. HEAD)")
    args = parser.parse_args()
    export_git_history_with_diff(args.output, args.author, args.limit, args.start, args.end)
