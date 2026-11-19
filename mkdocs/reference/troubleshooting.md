# Troubleshooting

## The Workflow Column Is Empty

The profile has workflows turned off, or the summary was stored before that field existed.
A profile with workflows off shows `SKIPPED — Workflow checks are disabled.` in the detail.
When workflows are on, run `github-intel sync --force` if the summary is still fresh.

## Status Says FAIL and There Is No Release Date

**FAIL** is a standards rule, usually a missing readme, licence, or `.gitignore`. A repository with no published release shows **No releases** in Status. The missing file remains in the detail.

## Last Push Is Blank

The GitHub repository size is 0, so nothing has been pushed. GitHub can leave the size at 0 for a while after the first push. The date appears on a later sync, after GitHub updates the size.

## Quality Is 0

Zero means there are no open CodeQL alerts, or GitHub did not share the count. The column does not stay blank.

## Sync Looks Slow

Each repository is a small set of requests, not a full history.
The number printed beside the current repository is the running total for the whole sync.
Standards uses one tree request.
Workflows use one page of recent runs, plus one request for each workflow missing from that page.
A GitHub rate limit does not freeze the display. The line says `waiting for GitHub rate limit, requests resume in` and the time until the next request is allowed. Ctrl+C cancels the sync instead of waiting that out.

## A Repository Is Unavailable

GitHub returned 404. The repository is missing, or the token cannot see it. `gh auth login` is required for private repositories.

## Configuration Will Not Load

`github-intel config validate` prints the invalid key. Unknown keys, a blank profile name, a date pattern that does not contain `DD`, `MM`, and `YYYY` once each, and a circular `extends` chain are rejected.
