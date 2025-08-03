
import json
import sys
import subprocess

def process_commit(commit):
    commit_content = commit.get('diff', '')
    prompt = f"can you summarize {commit_content}"
    try:
        result = subprocess.run([
            "ghccli", "--agent", "worker", "-p", prompt
        ], capture_output=True, text=True, check=True)
        summary = result.stdout.strip()
    except Exception as e:
        summary = f"[ERROR running ghccli: {e}]"
    print(f"Commit: {commit['hash']}")
    print(f"Author: {commit['author']} <{commit['email']}>")
    print(f"Date: {commit['date']}")
    print(f"Subject: {commit['subject']}")
    print("Summary:")
    print(summary)
    print("-" * 40)

def foreach_git_history(jsonl_file):
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            commit = json.loads(line)
            process_commit(commit)

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "git_history_with_diff.jsonl"
    foreach_git_history(input_file)
