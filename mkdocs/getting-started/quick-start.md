# Quick Start

Add a repository, synchronise it, then read the cache.

```bash
github-intel repo add the-lupaxa-project/brand-assets --group examples --profile upstream
github-intel config validate
github-intel sync
github-intel repo list
github-intel repo show the-lupaxa-project brand-assets
```

`upstream` checks releases only. A profile that turns more checks on is described in the [Configuration Guide](../configuration/configuration-guide.md).

## What the List Shows

`github-intel repo list` prints one row per configured repository. Dates use the pattern in `display.date_format`. The default is `DD/MM/YYYY`.

| Column         | Meaning                                                                 |
| -------------- | ----------------------------------------------------------------------- |
| Org            | GitHub organisation or user                                             |
| Repo           | Repository name                                                         |
| Visibility     | `public`, `private`, or `internal`                                      |
| Group          | Your collection group                                                   |
| Profile        | The profile that selected the checks                                    |
| Status         | The release result, unless a check failed                               |
| Version        | Newest published release tag                                            |
| Last push      | Calendar day of the last push, blank when the repository is empty       |
| Release date   | Publish date of that release                                            |
| Stars          | `stargazers_count`                                                      |
| Pull requests  | Open pull requests                                                      |
| Issues         | Open issues, excluding pull requests                                    |
| Quality        | Open CodeQL alerts, or `0` when GitHub does not share the count         |

The same fields are in `github-intel repo show ORG REPO`.
