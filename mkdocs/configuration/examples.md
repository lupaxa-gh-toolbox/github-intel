# Examples

## One Upstream Repository

`config.yml` can stay at the shipped defaults. `defaults.profile` is `upstream`.

```yaml
repositories:
  - repo: octocat/Hello-World
    group: examples
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
    security: true
    standards:
      readme: true
      licence: true
      gitignore: true
      workflows: false
      python_packaging: false
      mkdocs: false
      tests: false
```

Attach it on the repository, not on the default:

```yaml
repositories:
  - repo: lupaxa-gh-toolbox/github-intel
    group: lupaxa-gh-toolbox
    profile: project
```

```bash
github-intel repo set-profile lupaxa-gh-toolbox/github-intel project
github-intel profile show project
```

## Dates

```yaml
display:
  date_format: YYYY-MM-DD
```

Tables, the terminal interface, and Markdown reports use that pattern. JSON and CSV stay on `YYYY-MM-DD` from the stored value.
