# Configuration Guide

Configuration is explicit. GitHub Intel does not discover repositories. You add each `owner/name`, choose a group, and choose a profile.

## Where the Files Live

On macOS and Linux the default directory is `~/.config/github-intel/`.

| File               | Purpose                                         |
| ------------------ | ----------------------------------------------- |
| `config.yml`       | Defaults, display, sync limits, and log level   |
| `profiles.yml`     | Named check sets and optional standards rules   |
| `repositories.yml` | Repositories, groups, profiles, and tags        |

`github-intel config paths` prints the resolved paths, including the cache.

`GITHUB_INTEL_CONFIG` selects a different main file. `GITHUB_INTEL_CONFIG_DIR` selects a different directory when the main file is not set. `GITHUB_INTEL_DATA_DIR` moves the cache.

A command-line `--config` path is used before `GITHUB_INTEL_CONFIG`. Environment values for concurrency, the API URL, and the log level replace the values in the file.

## Groups and Profiles

A group is a label for the list. It does not change which checks run. One repository belongs to one group. A repository with no group is `ungrouped`.

A profile is the set of checks. A repository with no profile uses `defaults.profile`. The shipped default is `upstream`, which checks releases only.

## Shipped Profiles

| Profile      | Checks                                              |
| ------------ | --------------------------------------------------- |
| `base`       | Releases                                            |
| `upstream`   | Releases. This extends `base`.                      |
| `watchlist`  | Releases and issues. This extends `upstream`.       |
| `maintained` | Releases, workflows, issues, and standards          |
| `critical`   | The `maintained` checks, plus the security check    |

An explicit `false` overrides an inherited `true`. `github-intel profile tree` prints the chain. `github-intel profile show NAME --resolved` shows which profile set each flag.

## Standards Rules

`standards: true` runs the standards check with the inherited rules.
`standards: false` skips it.
A mapping turns the check on and replaces only the rules you list.
Anything omitted keeps the parent value.
A profile that never sets a rule uses `defaults.standards` in `config.yml`.

```yaml
lupaxa-project:
  releases: true
  workflows: true
  issues: true
  security: true
  standards:
    readme: true
    licence: true
    gitignore: true
    workflows: true
```

`workflows: true` beside the other checks is the Actions check. `standards.workflows` is a different setting: it asks whether `.github/workflows` exists.

## Repository Overrides

A repository can turn one check on or off without editing the profile:

```yaml
- repo: example/demo
  group: example
  profile: maintained
  checks:
    standards: false
```

`checks` does not change individual standards rules. It only enables or disables the whole check.

## What Is Not Stored

The GitHub token is not a configuration value. There is no `--token` option and no required `GITHUB_TOKEN`. Invalid settings are rejected. They are not replaced with a default.
