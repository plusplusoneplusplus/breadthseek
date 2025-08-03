import subprocess
import json
from datetime import datetime
import argparse

def run_git_cmd(cmd):
    return subprocess.check_output(cmd, text=True).strip()

def get_current_branch():
    return run_git_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])

def get_latest_commit():
    return run_git_cmd(["git", "rev-parse", "HEAD"])

def get_unpushed_commits():
    # Get upstream branch
    try:
        upstream = run_git_cmd(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    except subprocess.CalledProcessError:
        return []  # No upstream
    log = run_git_cmd(["git", "log", f"{upstream}..HEAD", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso-strict"])
    commits = []
    for line in log.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append({
                "hash": parts[0],
                "author": parts[1],
                "email": parts[2],
                "date": parts[3],
                "subject": parts[4]
            })
    return commits

def get_diff(cached=False):
    cmd = ["git", "diff"]
    if cached:
        cmd.append("--cached")
    return run_git_cmd(cmd)


def main():
    parser = argparse.ArgumentParser(description="Capture current git status and diffs to a JSON file.")
    parser.add_argument("--output", default="git_status_snapshot.json", help="Output file path (default: git_status_snapshot.json)")
    args = parser.parse_args()

    status = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "branch": get_current_branch(),
        "latest_commit": get_latest_commit(),
        "unpushed_commits": get_unpushed_commits(),
        "staged_diff": get_diff(cached=True),
        "unstaged_diff": get_diff(cached=False)
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
