# Reports

`github-intel report` writes Markdown to stdout. `--output FILE` writes that text to a file.

| Format       | Dates                                              |
| ------------ | -------------------------------------------------- |
| `markdown`   | `display.date_format`                              |
| `json`       | ISO `YYYY-MM-DD`. Timestamps stay ISO              |
| `csv`        | ISO dates. The CSV columns are the original set    |
| `table`      | Human table, from `repo list` and `audit`          |

```bash
github-intel report --format markdown --group lupaxa-gh-toolbox
github-intel repo list --format json
github-intel repo show lupaxa-gh-toolbox github-intel --format json
```

`audit` lists repositories that have a failing check. `--fail-on-checks` exits 6 when that list is not empty. The same flag on `sync` exits 6 when the run recorded check failures.

JSON includes the workflow list, visibility, stars, and the other summary fields. A missing workflow list is `null`.
