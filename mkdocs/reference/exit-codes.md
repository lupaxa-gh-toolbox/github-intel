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

A skipped security check is not a failure. **N Ahead** and **No releases** are not failures. **FAIL** and **ERROR** from an enabled standards rule are failures.
