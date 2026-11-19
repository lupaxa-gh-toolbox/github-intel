# Synchronisation

`github-intel sync` refreshes enabled repositories. A disabled repository is skipped. A failure on one repository is recorded and the run continues.

Repositories are visited in the same order as the default list: organisation, then repository name, ignoring case. Up to `sync.concurrency` repositories run at once.

A category is fetched again when it is missing, when its freshness window has passed, or when `--force` is set. The windows are the `sync.cache.*_ttl` values, in seconds.

`sync.interval` is the wait after one sync before another may start. `0` disables that wait. A sync inside the interval stops with an error. `--force` starts it anyway.

## What Is Requested

Each enabled repository gets the repository record, then only the data its profile and the summary need.

| Data              | Request                                                                                        |
| ----------------- | ---------------------------------------------------------------------------------------------- |
| Repository record | One request                                                                                    |
| Releases          | One page, the 20 newest. The check uses the newest published release                           |
| Compare           | One request, the release tag against the default branch                                        |
| Workflows         | One list of workflow files. Run history is not requested                                       |
| Pull requests     | One request. The count comes from the page link                                                |
| CodeQL            | One request. No scanning, Forbidden, or Unknown when there is no count                         |
| Dependabot        | One request for open alerts. A refusal is shown as Unknown                                     |

Release history is not paged. The workflow list is requested only when the profile has workflows enabled.

The summary, including stars, dates, and the workflow list, uses the issues freshness window. A sync inside that window leaves the summary as it is unless you pass `--force`.

## Progress

On a terminal, progress is a bar on stderr. Otherwise one line is printed when the completed count changes. The request count on that line is the total for the run, not the count for the repository named on the line.

`waiting for GitHub rate limit, requests resume in` is the time GitHub asked us to wait before sending another request.
Ctrl+C cancels the sync during that wait.
Repositories already stored stay in the cache, and the process exits with status 4.

## After a Profile Change

Turning a check on does not by itself refetch a summary that is still fresh. Use `github-intel sync --force` when you need the new fields immediately.
