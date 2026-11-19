# Configuration Reference

Unknown keys and invalid types are rejected.

## config.yml

```yaml
version: 1

github:
  api_url: https://api.github.com

files:
  profiles: profiles.yml
  repositories: repositories.yml

defaults:
  profile: upstream
  issues: false
  pull_requests: true
  quality: true
  standards:
    readme: true
    licence: true
    gitignore: true
    workflows: false
    python_packaging: false
    mkdocs: false
    tests: false

display:
  date_format: DD/MM/YYYY

sync:
  concurrency: 10
  timeout: 15
  retries: 3
  interval: 0
  cache:
    enabled: true
    metadata_ttl: 3600
    releases_ttl: 1800
    workflows_ttl: 900
    issues_ttl: 1800
    standards_ttl: 86400

logging:
  level: INFO
```

| Key                         | Meaning                                                                            |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `github.api_url`            | HTTPS GitHub API root                                                              |
| `files.profiles`            | Profile file, relative to `config.yml` unless absolute                             |
| `files.repositories`        | Repository file                                                                    |
| `defaults.profile`          | Profile used when a repository omits `profile`                                     |
| `defaults.issues`           | Issue column default when no profile sets `issues`                                 |
| `defaults.pull_requests`    | Pull request column default when no profile sets `pull_requests`                   |
| `defaults.quality`          | Quality column default when no profile sets `quality`                              |
| `defaults.standards.*`      | Rule defaults used when no profile sets that rule                                  |
| `display.date_format`       | Pattern for tables and the terminal. Must contain `DD`, `MM`, and `YYYY` once each |
| `sync.concurrency`          | Simultaneous repository requests. Minimum 1. Default 10                            |
| `sync.timeout`              | HTTP timeout in seconds                                                            |
| `sync.retries`              | Retries for rate limits and server errors                                          |
| `sync.interval`             | Seconds after a sync before another is allowed. 0 disables it. `--force` overrides |
| `sync.cache.enabled`        | When false, synchronisation always fetches                                         |
| `sync.cache.*_ttl`          | Freshness window in seconds for that category                                      |
| `logging.level`             | `CRITICAL`, `ERROR`, `WARNING`, `INFO`, or `DEBUG`                                 |

`display.date_format` is used for human output. JSON and CSV keep ISO dates.

## Standards Rules

| Rule                | Looks for                                                      |
| ------------------- | -------------------------------------------------------------- |
| `readme`            | `README.md`, `README.rst`, `README.txt`, or `README`           |
| `licence`           | `LICENCE`, `LICENSE`, `LICENCE.md`, `LICENSE.md`, or `COPYING` |
| `gitignore`         | `.gitignore`                                                   |
| `workflows`         | `.github/workflows`                                            |
| `python_packaging`  | `pyproject.toml`, `setup.py`, or `setup.cfg`                   |
| `mkdocs`            | `mkdocs.yml` or `mkdocs.yaml`                                  |
| `tests`             | `tests` or `test`                                              |

The shipped defaults require a readme, a licence, and `.gitignore`.

## profiles.yml

```yaml
profiles:
  base:
    releases: true
    workflows: false
    issues: false
    standards: false
    security: false

  maintained:
    extends: base
    workflows: true
    issues: true
    standards: true
```

| Key             | Meaning                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| `extends`       | Single parent. Cycles are rejected                                      |
| `releases`      | Compare the default branch with the newest published release            |
| `workflows`     | Latest run of each workflow on the default branch                       |
| `issues`        | Open issues, excluding pull requests. Off hides the Issues column       |
| `pull_requests` | Open pull requests. Omitted means on. Off hides the column              |
| `quality`       | Open CodeQL alerts. Omitted means on. Off hides the Quality column      |
| `standards`     | `true`, `false`, or a map of rule overrides                             |
| `security`      | Reserved. The result is always skipped                                  |

Omitted flags are inherited. A new profile starts from false for any flag no parent sets. `issues`, `pull_requests`, and `quality` instead use the values under `defaults` in `config.yml` when no profile sets them.

## repositories.yml

```yaml
repositories:
  - repo: owner/name
    group: owner
    profile: upstream
    tags:
      - example
    enabled: true
    checks:
      issues: false
```

| Key        | Meaning                                                      |
| ---------- | ------------------------------------------------------------ |
| `repo`     | `owner/name`. Required                                       |
| `group`    | Collection label. Default `ungrouped`                        |
| `profile`  | Profile name. Omitted repositories use `defaults.profile`    |
| `tags`     | Labels for `--tag` filters                                   |
| `enabled`  | `false` keeps the row and skips synchronisation              |
| `checks`   | Per-repository on/off overrides, applied last                |

## Environment

| Variable                    | Effect                                              |
| --------------------------- | --------------------------------------------------- |
| `GITHUB_INTEL_CONFIG`       | Main configuration file                             |
| `GITHUB_INTEL_CONFIG_DIR`   | Configuration directory                             |
| `GITHUB_INTEL_DATA_DIR`     | Cache directory                                     |
| `GITHUB_INTEL_CONCURRENCY`  | Replaces `sync.concurrency`                         |
| `GITHUB_INTEL_API_URL`      | Replaces `github.api_url`                           |
| `GITHUB_INTEL_LOG_LEVEL`    | Replaces `logging.level`                            |

`--config` is used before `GITHUB_INTEL_CONFIG`. `--concurrency` is used before `GITHUB_INTEL_CONCURRENCY`.
