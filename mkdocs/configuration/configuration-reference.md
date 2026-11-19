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
  releases: false
  workflows: false
  issues: false
  pull_requests: true
  quality: true

display:
  date_format: DD/MM/YYYY HH:mm UTC
  view: default
  views:
    popularity:
      list:
        - Organisation
        - Repository
        - Stars
        - Watchers
        - Forks

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

logging:
  level: INFO
```

| Key                         | Meaning                                                                            |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `github.api_url`            | HTTPS GitHub API root                                                              |
| `files.profiles`            | Profile file, relative to `config.yml` unless absolute                             |
| `files.repositories`        | Repository file                                                                    |
| `defaults.profile`          | Profile used when a repository omits `profile`                                     |
| `defaults.releases`         | Release check when no profile sets `releases`                                      |
| `defaults.workflows`        | Workflow check when no profile sets `workflows`                                    |
| `defaults.issues`           | Issue count when no profile sets `issues`                                          |
| `defaults.pull_requests`    | Pull requests when no profile sets `pull_requests`                                 |
| `defaults.quality`          | Quality check when no profile sets `quality`                                       |
| `display.date_format`       | `YYYY`, `MM`, and `DD` once each. `HH` and `mm` together are optional              |
| `display.view`              | Saved view name. Omitted, it is `default`                                          |
| `display.views`             | Maps a name to `list`, `detail`, or both. A missing side stays hardcoded           |
| `sync.concurrency`          | Simultaneous repository requests. Minimum 1. Default 10                            |
| `sync.timeout`              | HTTP timeout in seconds                                                            |
| `sync.retries`              | Retries for rate limits and server errors                                          |
| `sync.interval`             | Seconds after a sync before another is allowed. 0 disables it. `--force` overrides |
| `sync.cache.enabled`        | When false, synchronisation always fetches                                         |
| `sync.cache.*_ttl`          | Freshness window in seconds for that category                                      |
| `logging.level`             | `CRITICAL`, `ERROR`, `WARNING`, `INFO`, or `DEBUG`                                 |

`display.date_format` is used for human output. Leave out `HH` and `mm` to show the date only. The first `MM` is the month. When the clock is included, the second `MM` is the minute. `ss` and `UTC` are optional with the time.

JSON, CSV, and Markdown use the selected view's labels and the same cell text as the table. Dates follow `display.date_format`. A cached value that has no time shows `--` for a clock the pattern asks for.

`display.view` selects the saved view. Omitted, it is `default`. `display.views` maps a name to `list`, `detail`, or both. The missing side stays the hardcoded layout.

The default list is Organisation, Repository, Visibility, Language, Status, Version, Release date, and Enabled.

The generated file also includes a Popularity list: Organisation, Repository, Stars, Watchers, and Forks. Select it with `--view popularity`.

A written list shows every name, including a check that is off. Pull requests, Issues, and Quality are blank on a list when that check is off.

`--view` overrides the saved name for one command and does not write the file. An unknown name exits 2. `tui --view` follows the same rule.

## View Fields

A `list` or `detail` entry names these fields, in the order you want them shown:

- Organisation
- Repository
- Visibility
- Description
- Homepage
- Language
- Topics
- Group
- Profile
- Tags
- Enabled
- Status
- Cache
- Archived
- Fork
- Forks
- Last push
- Created
- Updated
- Synchronised
- Default branch
- Size
- Stars
- Watchers
- Licence
- Version
- Release date
- Ahead
- Pull requests
- Issues
- Quality
- Workflows
- Dependabot Alerts

These names are accepted on either `list` or `detail`. They are matched without regard to case. An unknown name or a duplicate is a config error.

Size, Stars, Watchers, Forks, Ahead, Pull requests, Issues, Quality, and Dependabot Alerts are right-aligned.

[Examples](examples.md) shows a Popularity list and a Releases list.

## profiles.yml

```yaml
profiles:
  base:
    releases: true
    workflows: false
    issues: false

  maintained:
    extends: base
    workflows: true
    issues: true
```

| Key             | Meaning                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| `extends`       | Single parent. Cycles are rejected                                      |
| `releases`      | Compare the default branch with the newest published release            |
| `workflows`     | The workflow list, and whether each workflow is active or disabled      |
| `issues`        | GitHub's open issue count. Pull requests stay in the total              |
| `pull_requests` | Open pull requests. A written list leaves the cell blank when off       |
| `quality`       | Open CodeQL alerts. The cell names why a count is missing               |

Omitted flags are inherited from the parent profile. When no profile in the chain sets a flag, `defaults` in `config.yml` supplies it. An explicit false overrides an inherited true.

## repositories.yml

Each entry is a GitHub organisation or user, then the repository names inside it.

```yaml
organisations:
  - name: owner
    group: examples
    profile: upstream
    repositories:
      - demo
      - name: other
        enabled: false
        checks:
          issues: false
```

| Key            | Meaning                                                      |
| -------------- | ------------------------------------------------------------ |
| `name`         | GitHub organisation or user                                  |
| `group`        | Collection label for every repository under that owner       |
| `profile`      | Profile for every repository under that owner                |
| `repositories` | Repository names                                             |

A repository can be a name, or an object when it differs from the owner.

| Key       | Meaning                                                      |
| --------- | ------------------------------------------------------------ |
| `name`    | Repository name                                              |
| `group`   | Overrides the owner's group                                  |
| `profile` | Overrides the owner's profile                                |
| `tags`    | Labels for `--tag` filters                                   |
| `enabled` | `false` keeps the row and skips synchronisation              |
| `checks`  | Per-repository on/off overrides, applied last                |

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
