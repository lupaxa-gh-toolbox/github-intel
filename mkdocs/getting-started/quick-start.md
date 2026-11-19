# Quick Start

Add a repository, synchronise it, then read the cache.

```bash
github-intel repo add octocat/Hello-World --group examples --profile upstream
github-intel config validate
github-intel sync
github-intel repo list
github-intel repo show octocat Hello-World
```

`upstream` checks releases only. A profile that turns more checks on is described in the [Configuration Guide](../configuration/configuration-guide.md).

## What the List Shows

`github-intel repo list` prints one row per configured repository. Dates use the pattern in `display.date_format`. The default is `DD/MM/YYYY HH:mm UTC`. The saved view is `display.view`. Omitted, it is `default`.

A written list shows every name, including a check that is off. Pull requests, Issues, and Quality are blank on a list when that check is off.

| Column       | Meaning                                                 |
| ------------ | ------------------------------------------------------- |
| Organisation | GitHub organisation or user                             |
| Repository   | Repository name                                         |
| Visibility   | `public`, `private`, or `internal`                      |
| Language     | Primary language                                        |
| Status       | The short release result. The detail shows the sentence |
| Version      | Newest published release tag                            |
| Release date | Publish time of that release                            |
| Enabled      | `yes` or `no`. Disabled repositories are skipped        |

The same fields are in `github-intel repo show ORG REPO`. The detail also lists the rest of the cached record.
