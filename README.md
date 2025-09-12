# BreadthSeek

## Claude Code Configuration

This repository includes [ccc (claude-code-config)](https://github.com/plusplusoneplusplus/ccc) as a submodule for enhanced Claude Code setup.

### Quick Setup

```bash
curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/ccc/main/install.sh | bash
```

### Clone with Submodules

```bash
git clone --recursive https://github.com/plusplusoneplusplus/breadthseek.git
cd breadthseek/claude
./setup.sh
```

### Updating Configuration

```bash
git submodule update --remote claude
```

**Repositories**: 
- Main: [plusplusoneplusplus/breadthseek](https://github.com/plusplusoneplusplus/breadthseek)
- Claude Config: [plusplusoneplusplus/ccc](https://github.com/plusplusoneplusplus/ccc)