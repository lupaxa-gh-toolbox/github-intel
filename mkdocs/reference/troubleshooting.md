# Troubleshooting

## The Workflow Column Is Empty

The profile has workflows turned off, or the summary was stored before that field existed.
A profile with workflows off shows `SKIPPED — Workflow checks are disabled.` in the detail.
When workflows are on, run `github-intel sync --force` if the summary is still fresh.

## Last Push Is Blank

The GitHub repository size is 0, so nothing has been pushed. GitHub can leave the size at 0 for a while after the first push. The date appears on a later sync, after GitHub updates the size.

## Quality Is Unknown

**0** means there are no open alerts. **No scanning** means GitHub has no code scanning analysis. **Forbidden** means the token cannot read the alerts. **Unknown** means the count could not be read for another reason.

## Sync Looks Slow

Each repository is a small set of requests, not a full history.
The number printed beside the current repository is the running total for the whole sync.
Workflows use one request for the workflow list. Run history is not requested.
A GitHub rate limit does not freeze the display. The line says `waiting for GitHub rate limit, requests resume in` and the time until the next request is allowed. Ctrl+C cancels the sync instead of waiting that out.

## A Repository Is Unavailable

GitHub returned 404. The repository is missing, or the token cannot see it. `gh auth login` is required for private repositories.

## Configuration Will Not Load

`github-intel config validate` prints the invalid key. Unknown keys, a blank profile name, a date pattern that does not contain `DD`, `MM`, and `YYYY` once each, and a circular `extends` chain are rejected.
