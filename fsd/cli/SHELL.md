# FSD Interactive Shell

The FSD CLI includes a powerful interactive shell with bash-like features for power users.

## Features

### Command History
- **Up/Down Arrows**: Navigate through command history
- **Persistent History**: Commands are saved across sessions in `.fsd/shell_history` (project-local) or `~/.fsd/shell_history` (global)
- **Reverse Search**: Press `Ctrl+R` to search through history
- **Auto-Suggestions**: Gray text shows suggestions from history as you type

### Tab Completion
- **Command Completion**: Press `Tab` to complete FSD commands
- **Subcommand Completion**: Automatically suggests subcommands (e.g., `queue list`)
- **Option Completion**: Completes command options and flags (e.g., `--help`, `--text`)
- **Context-Aware**: Completion adapts based on what you've already typed

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `↑` / `↓` | Navigate command history |
| `Tab` | Auto-complete commands/options |
| `Ctrl+R` | Reverse search through history |
| `Ctrl+A` | Move cursor to beginning of line |
| `Ctrl+E` | Move cursor to end of line |
| `Ctrl+K` | Delete from cursor to end of line |
| `Ctrl+U` | Delete from cursor to beginning of line |
| `Ctrl+W` | Delete word before cursor |
| `Ctrl+C` | Cancel current input |
| `Ctrl+D` | Exit shell |
| `Ctrl+L` | Clear screen |

### Built-in Shell Commands
| Command | Description |
|---------|-------------|
| `help` | Show FSD command menu |
| `?` | Show shell features help |
| `clear` | Clear the terminal screen |
| `history` | Show recent command history (last 20) |
| `quit` / `exit` | Exit the shell |

## Usage

### Starting the Shell

```bash
# Default - start interactive shell
fsd

# Use simple mode (no history/completion)
fsd --simple-mode
```

### Example Session

```
$ fsd
╭─────────────────────────────────────────────────╮
│ FSD - Autonomous Overnight Coding Agent System  │
│ Interactive Mode                                │
╰─────────────────────────────────────────────────╯

Type 'help' for available commands, '?' for shell features

History: /path/to/project/.fsd/shell_history

fsd> queue list         # Tab completion works here
fsd> submit --text "Fix login bug"
fsd> status
fsd> ↑                  # Press up arrow to navigate history
fsd> Ctrl+R            # Reverse search
(reverse-i-search)`sta': status
fsd> history           # Show command history
fsd> quit
```

### Tab Completion Examples

```
fsd> su[Tab]           # Completes to: submit
fsd> submit --[Tab]    # Shows: --interactive --dry-run --text --ai --help
fsd> queue [Tab]       # Shows: list start stop clear retry
fsd> queue li[Tab]     # Completes to: queue list
```

### Reverse Search (Ctrl+R)

Press `Ctrl+R` and start typing to search backwards through your command history:

```
fsd> [Ctrl+R]
(reverse-i-search)`':
(reverse-i-search)`sub': submit --text "Fix bug"
```

Press `Ctrl+R` again to find the next match, or `Enter` to use the current match.

## History Files

Command history is saved in one of two locations:

1. **Project-local** (preferred): `.fsd/shell_history` in the current project
2. **Global fallback**: `~/.fsd/shell_history` in your home directory

The shell automatically uses the project-local history when a `.fsd` directory exists in the current working directory.

## Power User Tips

### Command Shortcuts
```bash
# Quick task submission
fsd> submit --text "HIGH: Fix auth bug. 30m"

# Chain commands (type directly)
fsd> queue list
fsd> queue start

# Use history search to find previous commands
fsd> Ctrl+R bug  # Finds "submit --text 'Fix bug'"
```

### Combining with Shell Features
```bash
# Clear screen and show status
fsd> clear
fsd> status

# Review recent commands before retrying
fsd> history
fsd> ↑↑↑  # Navigate to specific command

# Exit shortcuts
fsd> quit    # Type it out
fsd> Ctrl+D  # Quick exit
```

### Efficiency Tips

1. **Use Tab Completion**: Don't type full commands - let Tab do the work
2. **Use Ctrl+R**: Faster than pressing up arrow multiple times
3. **Review History**: `history` command shows what you've been doing
4. **Auto-Suggestions**: Watch the gray text - it might be what you want

## Comparison with Simple Mode

| Feature | Shell Mode (Default) | Simple Mode (`--simple-mode`) |
|---------|---------------------|------------------------------|
| Command History | ✓ Persistent, searchable | ✗ None |
| Tab Completion | ✓ Smart, context-aware | ✗ None |
| Reverse Search | ✓ Ctrl+R | ✗ None |
| Auto-Suggestions | ✓ From history | ✗ None |
| Line Editing | ✓ Full readline | ✗ Basic |
| Best For | Power users, daily use | Scripts, simple workflows |

## Troubleshooting

### History Not Saving
- Check that you have write permissions to `.fsd/` or `~/.fsd/`
- The history file is created automatically on first use

### Completions Not Working
- Make sure you're pressing `Tab` (not space)
- Completions only work for valid FSD commands
- Some completions are context-dependent

### Terminal Issues
- If you see strange characters, try `clear`
- If Ctrl+R doesn't work, your terminal might not support it
- Use `--simple-mode` as a fallback

## Technical Details

- **Built with**: [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)
- **Compatibility**: Works on Linux, macOS, and Windows
- **History Format**: Plain text file, one command per line
- **Completion Engine**: Custom FSD-aware completer with context sensitivity
