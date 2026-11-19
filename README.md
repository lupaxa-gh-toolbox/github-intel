<p align="center">
  <a href="https://github.com/lupaxa-gh-toolbox">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/organisations/gh-toolbox/readme-logo.png" alt="The Lupaxa Project: GitHub Toolbox" />
  </a>
</p>

<h1 align="center">GitHub Intel</h1>

**GitHub Intel** monitors an explicit list of GitHub repositories. It stores the results locally and can show them without a network connection. Groups organise the list. Profiles decide which checks run.

## Features

- An explicit repository list. Nothing is discovered.
- Profiles for releases, workflows, issues, pull requests, and quality.
- Profile inheritance. An explicit false overrides an inherited true.
- A local SQLite cache, so lists and reports work offline.
- Release and workflow checks, without a file inventory or an issues list.
- Human tables, JSON, CSV, and Markdown.
- A terminal interface for the same cached view.
- Dates in a configurable pattern. The default is `DD/MM/YYYY HH:mm UTC`.
- Authentication through the GitHub CLI. The token is not stored.

## Installation

Install the latest release from PyPI.

```bash
pip install lupaxa-github-intel
```

Verify the installation.

```bash
github-intel --version
```

Private repositories use the GitHub CLI login:

```bash
gh auth login
```

## Quick Start

The first `repo add` creates `~/.config/github-intel/`.

```bash
github-intel repo add owner/name --group examples --profile upstream
github-intel config validate
github-intel sync
github-intel repo list
github-intel repo show owner name
```

`github-intel` with no arguments opens the terminal interface when the terminal is interactive.

## Command-Line Interface

`github-intel repo list` reads the cache. `github-intel sync` is the command that calls GitHub.

### Repositories

| Command                                            | Description                                      |
| -------------------------------------------------- | ------------------------------------------------ |
| `github-intel repo add OWNER/NAME`                 | Add a repository. This does not call GitHub      |
| `github-intel repo list`                           | Show the cached table                            |
| `github-intel repo show ORG REPO`                  | Show one repository                              |
| `github-intel repo set-profile OWNER/NAME PROFILE` | Choose the checks for one repository             |

### Synchronisation and Reports

| Command                          | Description                                      |
| -------------------------------- | ------------------------------------------------ |
| `github-intel sync`              | Refresh stale or missing information             |
| `github-intel sync --force`      | Ignore cache freshness and `sync.interval`       |
| `github-intel report`            | Write a Markdown report                          |
| `github-intel audit`             | Show repositories with failing checks            |

### Configuration

| Command                          | Description                                      |
| -------------------------------- | ------------------------------------------------ |
| `github-intel config init`       | Write the default files. `--force` overwrites    |
| `github-intel config validate`   | Load the files and report the repository count   |
| `github-intel config paths`      | Print configuration and cache paths              |
| `github-intel profile show NAME` | Show the effective checks                        |

> **Note:** `--config FILE` selects a different main file. Without it, the files are `config.yml`, `profiles.yml`, and `repositories.yml` in `~/.config/github-intel/`.

## Documentation

Online documentation:

[https://github-intel.thelupaxaproject.org/](https://github-intel.thelupaxaproject.org/)

Serve the docs locally:

```bash
make init
make python-install-dev
make mkdocs-serve
```

## Development

Install makefile skills, then the development extra:

```bash
make init
make python-install-dev
```

Lint, type-check, and test:

```bash
make python-check
```

<a href="https://github.com/the-lupaxa-project">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/components/footer-for-child-orgs.svg" alt="The Lupaxa Project Footer" width="100%" />
</a>
