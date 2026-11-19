# Terminal Interface

```bash
github-intel
```

The same view is `github-intel tui`. It opens only when stdin and stdout are both terminals. A pipe prints help instead.

The table matches `repo list`. Dates use `display.date_format`.

Status text is coloured on a terminal. Green is current or healthy. Yellow is ahead, no release, or unknown. Red is a failure. Dim is disabled, skipped, or never run. JSON and CSV stay plain.

| Key         | Action                                      |
| ----------- | ------------------------------------------- |
| Enter       | Open the repository detail                  |
| Escape      | Close the detail, or cancel a sync          |
| `/`         | Search the repository id and description    |
| `r`         | Synchronise                                 |
| `p`         | Profiles                                    |
| `c`         | Configuration paths                         |
| `Ctrl+Q`    | Quit                                        |

`q` alone does not quit, because the search field uses that key.

The detail is the same field and value table as `github-intel repo show`. Long values wrap.
