#!/usr/bin/env bash
set -euo pipefail

# Symlink local .claude directory to ~/.claude

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -f, --force     Replace existing ~/.claude directory/symlink
  -n, --dry-run   Print actions without making changes
  -h, --help      Show this help
EOF
}

force=0
dryrun=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--force) force=1 ; shift ;;
    -n|--dry-run) dryrun=1 ; shift ;;
    -h|--help) usage ; exit 0 ;;
    *) echo "Unknown option: $1" >&2 ; usage ; exit 1 ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
local_claude="$repo_root"
target_claude="${HOME}/.claude"

run() { if [[ $dryrun -eq 1 ]]; then echo "DRY-RUN: $*"; else eval "$*"; fi; }

mkdirp() {
  if [[ ! -d "$1" ]]; then
    echo "Make dir: $1"
    run "mkdir -p \"$1\""
  fi
}

link_directory() {
  local src="$1"
  local dest="$2"
  local name="$(basename "$dest")"

  if [[ -e "$dest" || -L "$dest" ]]; then
    if [[ -L "$dest" ]]; then
      local current_target
      current_target="$(readlink "$dest")"
      if [[ "$current_target" == "$src" ]]; then
        echo "OK: $dest already links to $src"
        return
      fi
    fi
    if [[ $force -eq 1 ]]; then
      echo "Replace: $dest -> $src"
      run "rm -rf \"$dest\""
    else
      echo "Skip: $dest exists (use --force to replace)"
      return
    fi
  fi

  echo "Link: $dest -> $src"
  run "ln -s \"$src\" \"$dest\""
}

# Ensure parent directory exists
mkdirp "$(dirname "$target_claude")"

echo "Linking directory:"
link_directory "$local_claude" "$target_claude"

echo "Done."