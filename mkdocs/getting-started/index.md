# Getting Started

Install the package, add the repositories you want to watch, then synchronise them.

## Requirements

- Python 3.11 or later.
- The GitHub CLI for private repositories and authenticated checks.

[Installation](installation.md) covers install and upgrade.

## Configuration Files

The first `github-intel repo add` creates three files under `~/.config/github-intel/`:

| File                | Role                                              |
| ------------------- | ------------------------------------------------- |
| `config.yml`        | Defaults, cache windows, date format, and limits  |
| `profiles.yml`      | Named sets of checks                              |
| `repositories.yml`  | The repositories to monitor                       |

A different main file can be passed with `--config`. Paths and environment variables are in the [Configuration Guide](../configuration/configuration-guide.md).

## First Run

[Quick Start](quick-start.md) adds one repository, validates the files, synchronises, and lists the result.

```bash
github-intel repo add owner/name --profile upstream
github-intel config validate
github-intel sync
github-intel repo list
```

`github-intel` with no arguments opens the terminal interface when the terminal is interactive.
