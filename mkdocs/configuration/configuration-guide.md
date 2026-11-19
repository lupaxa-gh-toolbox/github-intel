# Configuration Guide

Configuration is explicit. GitHub Intel does not discover repositories. You add each `owner/name`, choose a group, and choose a profile.

## Where the Files Live

On macOS and Linux the default directory is `~/.config/github-intel/`.

| File               | Purpose                                         |
| ------------------ | ----------------------------------------------- |
| `config.yml`       | Defaults, display, sync limits, and log level   |
| `profiles.yml`     | Named check sets                                |
| `repositories.yml` | Repositories, groups, profiles, and tags        |

`github-intel config init` writes `config.yml`, `profiles.yml`, and `repositories.yml` filled with the defaults. A file that already exists is kept. `--force` replaces it with the default. When every file already exists, the command exits 2.

`github-intel config paths` prints the resolved paths, including the cache.

`GITHUB_INTEL_CONFIG` selects a different main file. `GITHUB_INTEL_CONFIG_DIR` selects a different directory when the main file is not set. `GITHUB_INTEL_DATA_DIR` moves the cache.

A command-line `--config` path is used before `GITHUB_INTEL_CONFIG`. Environment values for concurrency, the API URL, and the log level replace the values in the file.

## Groups and Profiles

A group is a label for the list. It does not change which checks run. One repository belongs to one group. A repository with no group is `ungrouped`.

A profile is the set of checks. A repository with no profile uses `defaults.profile`. The shipped default is `upstream`, which checks releases only.

Every check has a true or false value under `defaults`. A profile overrides the checks it sets. The shipped defaults leave releases and workflows off, leave issues off, and leave pull requests and quality on.

## Shipped Profiles

| Profile      | Checks                                              |
| ------------ | --------------------------------------------------- |
| `base`       | Releases                                            |
| `upstream`   | Releases. This extends `base`.                      |
| `watchlist`  | Releases and issues. This extends `upstream`.       |
| `maintained` | Releases, workflows, and issues                     |
| `critical`   | The same checks as `maintained`                     |

An explicit `false` overrides an inherited `true`. `github-intel profile tree` prints the chain. `github-intel profile show NAME --resolved` shows which profile set each flag.

## Repository Overrides

A repository can turn one check on or off without editing the profile:

```yaml
organisations:
  - name: example
    group: example
    profile: maintained
    repositories:
      - name: demo
        checks:
          issues: false
```

## What Is Not Stored

The GitHub token is not a configuration value. There is no `--token` option and no required `GITHUB_TOKEN`. Invalid settings are rejected. They are not replaced with a default.
