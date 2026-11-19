# Architecture

GitHub Intel is a local-first command-line tool. The terminal interface is another view of the same cache.

## Pieces

| Piece            | Role                                                                 |
| ---------------- | -------------------------------------------------------------------- |
| Configuration    | YAML files for defaults, profiles, and the repository list           |
| Profiles         | Single-parent inheritance, then repository `checks` overrides        |
| GitHub client    | One GET per call. Link headers are not followed                      |
| Synchroniser     | Bounded concurrency. One repository failure does not stop the run    |
| Cache            | SQLite, under `~/.local/share/github-intel/cache.sqlite` by default  |
| Views            | The Status column and the detail table, built from the cache         |

## Read and Write

`sync` is the writer. `repo list`, `repo show`, `report`, `audit`, and the terminal interface are readers. They do not call GitHub.

The client retries rate limits and `500`, `502`, `503`, and `504`. It does not store the token. Logs redact it.

## Freshness

Each category has its own window.
Metadata and releases can be fresh independently.
The summary row that feeds the list columns uses the issues window.
A change to stars or the workflow list waits for that window or for `--force`.
