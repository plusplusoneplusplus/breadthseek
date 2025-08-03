#!/usr/bin/env python3
"""
Squash all commits in front of HEAD into a single commit.
This script will squash all commits in the current branch except the latest (HEAD) commit.
"""
import subprocess
import sys

def run(cmd, check=True, capture_output=True, text=True):
    result = subprocess.run(cmd, check=check, capture_output=capture_output, text=text)
    return result.stdout.strip()

def get_commit_count():
    return int(run(["git", "rev-list", "--count", "HEAD"]))

def get_first_commit_hash():
    return run(["git", "rev-list", "--max-parents=0", "HEAD"]).splitlines()[0]

def get_current_branch():
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"])

def get_upstream_branch():
    branch = get_current_branch()
    try:
        upstream = run(["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"])
        return upstream
    except subprocess.CalledProcessError:
        print(f"No upstream tracking branch for {branch}. Cannot squash ahead-of-origin commits.")
        sys.exit(1)

def get_commits_ahead():
    branch = get_current_branch()
    upstream = get_upstream_branch()
    ahead = run(["git", "rev-list", "--count", f"{upstream}..{branch}"])
    return int(ahead)

def get_oldest_ahead_commit(upstream, branch):
    # Get the oldest commit that is ahead of upstream
    commits = run(["git", "rev-list", f"{upstream}..{branch}"]).splitlines()
    if not commits:
        return None
    return commits[-1]  # last in list is oldest

def squash_all_commits():
    branch = get_current_branch()
    upstream = get_upstream_branch()
    ahead = get_commits_ahead()
    if ahead == 0:
        print(f"No commits ahead of {upstream}. Nothing to squash.")
        return
    if ahead == 1:
        print(f"Only one commit ahead of {upstream}. Nothing to squash.")
        return
    oldest_ahead_commit = get_oldest_ahead_commit(upstream, branch)
    print(f"Squashing {ahead} commits ahead of {upstream} into one...")
    try:
        # Reset to the parent of the oldest ahead commit, keeping changes staged
        parent = run(["git", "rev-parse", f"{oldest_ahead_commit}^"], check=True)
        run(["git", "reset", "--soft", parent])
        run(["git", "commit", "-m", f"Squashed {ahead} commits ahead of {upstream} into one"])
        print("Successfully squashed all commits ahead of upstream into one.")
    except subprocess.CalledProcessError as e:
        print(f"Error during squashing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    squash_all_commits()
