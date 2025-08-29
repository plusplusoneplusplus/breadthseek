#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract information from JSON
cwd="$(echo "$input" | jq -r '.workspace.current_dir')"
transcript_path="$(echo "$input" | jq -r '.transcript_path')"
model_display="$(echo "$input" | jq -r '.model.display_name')"
session_id="$(echo "$input" | jq -r '.session_id')"

# Change to the working directory
cd "$cwd" 2>/dev/null

# Get hostname and privilege indicator with emoji
hostname_part="💻$(hostname -s)"
privilege_part="$([ "$(id -u)" = '0' ] && echo '#' || echo '%')"

# Get shortened working directory path
cwd_part=""
if [ -n "$cwd" ]; then
    # Replace home directory with ~
    display_cwd="${cwd/#$HOME/~}"
    
    # If path is too long (>50 chars), shorten it
    if [ ${#display_cwd} -gt 50 ]; then
        # Keep the last 3 directory components
        display_cwd="...$(echo "$display_cwd" | rev | cut -d'/' -f1-3 | rev)"
    fi
    
    cwd_part=" 📁$display_cwd"
fi

# Get context length information
context_info=""
if [ -f "$transcript_path" ]; then
    # Count characters in the transcript file for context usage
    char_count=$(wc -c < "$transcript_path" 2>/dev/null || echo 0)
    # Convert to approximate token count (rough estimate: 4 chars per token)
    token_estimate=$((char_count / 4))
    
    # Format context info with appropriate units and emoji
    if [ $token_estimate -gt 1000 ]; then
        context_info="📊[$(echo "scale=1; $token_estimate/1000" | bc 2>/dev/null || echo "$((token_estimate/1000))")k]"
    else
        context_info="📊[${token_estimate}]"
    fi
fi

# Model information
model_part=""
if [ -n "$model_display" ] && [ "$model_display" != "null" ]; then
    # Extract a shorter model identifier from the display name
    model_short=$(echo "$model_display" | sed 's/Claude //' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
    model_part="🤖[$model_short]"
fi


# Enhanced git status with detailed symbols
git_part=""
if git rev-parse --git-dir >/dev/null 2>&1; then
    branch="$(git branch --show-current 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)"
    if [ -n "$branch" ]; then
        git_part=" 🌿(${branch}"
        
        # Check for different types of changes
        status_symbols=""
        
        # Check for staged changes
        if ! git diff --cached --quiet 2>/dev/null; then
            status_symbols="${status_symbols}✅"
        fi
        
        # Check for unstaged changes  
        if ! git diff --quiet 2>/dev/null; then
            status_symbols="${status_symbols}📝"
        fi
        
        # Check for untracked files
        if [ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then
            status_symbols="${status_symbols}❓"
        fi
        
        # Check for stashed changes
        if git stash list 2>/dev/null | grep -q .; then
            status_symbols="${status_symbols}💾"
        fi
        
        if [ -n "$status_symbols" ]; then
            git_part="${git_part}${status_symbols}"
        fi
        
        git_part="${git_part})"
    fi
fi

# Output the complete status line
printf '%s%s%s%s %s%s' "$hostname_part" "$privilege_part" "$cwd_part" "$git_part" "$model_part" "$context_info"