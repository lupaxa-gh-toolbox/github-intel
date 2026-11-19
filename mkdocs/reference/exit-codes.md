# Exit Codes

Scripts should use the process exit status. Human tables are on stdout. Errors are on stderr.

| Code | Meaning                                                          |
| ---- | ---------------------------------------------------------------- |
| 0    | The command finished                                             |
| 1    | A general error                                                  |
| 2    | Configuration or usage is invalid, or a confirmation was refused |
| 3    | GitHub rejected the credentials and nothing was synchronised     |
| 4    | Synchronisation was cancelled or a repository failed             |
| 5    | The named repository is not configured                           |
| 6    | `--fail-on-checks` found failing checks                          |

**N Ahead** and **No releases** are not failures.

Exit 2 is also used when a sync starts inside `sync.interval`. `--force` overrides that wait. `config init` exits 2 when `config.yml`, `profiles.yml`, and `repositories.yml` already exist and `--force` was not passed.
