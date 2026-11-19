# Terminal Interface

```bash
github-intel
```

The same interface is `github-intel tui`. It opens only when stdin and stdout are both terminals. A pipe prints help instead.

The table matches `repo list`. Dates use `display.date_format`.

The list and the detail use the same colours. JSON and CSV stay plain.

Green is current, healthy, enabled, a fresh cache, or a zero alert count. Cyan is no release, a fork, or an internal repository. Yellow is ahead, archived, stale, unknown, or a positive alert count.

Red is a failure, a metadata error, or a cache error. Dim is disabled, skipped, or not enabled. Public is green and private is magenta.

The Repository name is red in the list when the repository record failed. The detail title uses that same red.

List column headers and the field names in the detail are cyan.

| Key         | Action                                      |
| ----------- | ------------------------------------------- |
| Enter       | Open the repository detail                  |
| Escape      | Close the detail, or cancel a sync          |
| `/`         | Search the repository id and description    |
| `r`         | Synchronise                                 |
| `p`         | Profiles                                    |
| `c`         | Configuration paths                         |
| `v`         | Pick a saved view for this session          |
| `Ctrl+Q`    | Quit                                        |

`q` alone does not quit, because the search field uses that key. `v` picks a view for the session and does not write the file.

The detail is the same field and value table as `github-intel repo show`. `Metadata error` stays the first row when the repository record failed.

It lists the cached repository record, including language, topics, homepage, fork counts, dates, size, watchers, tags, and the synchronisation time.

Long values wrap.
