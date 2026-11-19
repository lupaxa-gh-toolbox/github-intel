# Examples

## One Upstream Repository

`config.yml` can stay at the shipped defaults. `defaults.profile` is `upstream`.

```yaml
organisations:
  - name: octocat
    group: examples
    repositories:
      - Hello-World
```

```bash
github-intel repo add octocat/Hello-World --group examples
github-intel sync --repo octocat/Hello-World
github-intel repo show octocat Hello-World
```

## A Project Profile

Add the profile to `profiles.yml`. It does not replace `defaults.profile`, so repositories that omit `profile` stay on `upstream`.

```yaml
  project:
    releases: true
    workflows: true
    issues: true
```

Attach it on the repository, not on the default:

```yaml
organisations:
  - name: octocat
    group: examples
    repositories:
      - name: Hello-World
        profile: project
```

```bash
github-intel repo set-profile octocat/Hello-World project
github-intel profile show project
```

## Dates

```yaml
display:
  date_format: YYYY-MM-DD HH:mm
```

Tables, the terminal interface, JSON, CSV, and Markdown use that pattern. Leave out `HH` and `mm` to show the date only. `ss` and `UTC` are optional with the time.

## A Saved View

```yaml
display:
  view: compact
  views:
    compact:
      list:
        - Repository
        - Status
      detail:
        - Status
        - Workflows
```

`display.view` selects the saved view. Omitted, it is `default`. `display.views` maps a name to `list`, `detail`, or both. The missing side stays the hardcoded layout. A written list shows every name, including a check that is off.

```bash
github-intel repo list --view compact
```

`--view` overrides the saved name for one command and does not write the file. An unknown name exits 2.

## List Views

A view can replace only the list. The detail stays the hardcoded layout.

### Default

When `default` does not set `list`, the columns are Organisation, Repository, Visibility, Language, Status, Version, Release date, and Enabled.

### Popularity

```yaml
display:
  views:
    popularity:
      list:
        - Organisation
        - Repository
        - Stars
        - Watchers
        - Forks
```

### Releases

```yaml
display:
  views:
    releases:
      list:
        - Organisation
        - Repository
        - Version
        - Release date
```

`Release date` is the field name. Stars, Watchers, and Forks are right-aligned.

```bash
github-intel repo list --view popularity
github-intel repo list --view releases
```
