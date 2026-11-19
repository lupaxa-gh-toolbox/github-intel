# Reports

`github-intel report` writes Markdown to stdout. `--output FILE` writes that text to a file.

| Format     | Dates                                     |
| ---------- | ----------------------------------------- |
| `markdown` | `display.date_format`                     |
| `json`     | `display.date_format`                     |
| `csv`      | `display.date_format`                     |
| `table`    | Human table, from `repo list` and `audit` |

```bash
github-intel report --format markdown --group examples
github-intel repo list --format json
github-intel repo show octocat Hello-World --format json
```

`audit` lists repositories that have a failing check. `--fail-on-checks` exits 6 when that list is not empty. The same flag on `sync` exits 6 when the run recorded check failures.

JSON, CSV, and Markdown use that view's labels and the same cell text as the table. Dates follow `display.date_format`. `Metadata error` stays the first detail row when the repository record failed.
