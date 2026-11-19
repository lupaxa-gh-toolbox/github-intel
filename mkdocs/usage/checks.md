# Checks

A profile decides which checks run.
The Status column prefers the release result.
A missing release stays **No releases** even when another check failed.
Any other failure replaces the release result.
With no failure and no release check, Status is **Healthy**.

## Releases

| Status      | Meaning                                                          |
| ----------- | ---------------------------------------------------------------- |
| Current     | The default branch is not ahead of the newest published tag      |
| N Ahead     | The default branch is N commits ahead of that tag. Not a failure |
| No releases | There is no published release                                    |
| Unknown     | The compare could not be interpreted                             |
| Error       | The releases request failed                                      |

The release date is the publish date of that tag. Drafts are skipped.

## Workflows

The check uses the newest of the per-workflow runs on the default branch.

| Status       | Meaning                                                                 |
| ------------ | ----------------------------------------------------------------------- |
| Success      | The newest run completed without a failure conclusion                   |
| Failure      | The conclusion is failure, timed out, or startup failure                |
| In progress  | The newest run has not completed                                        |
| Never run    | The repository has no matching run                                      |
| Error        | The workflow list could not be read                                     |

The repository detail lists every workflow and the state of its latest run on the default branch. When the profile has workflows turned off, that row is `SKIPPED — Workflow checks are disabled.`

## Issues

When the profile sets `issues` false, the Issues column is left out of the list and the detail says `SKIPPED — Issue checks are disabled.`

Open pull requests are not counted as issues. **Open** means the first page contained an issue. It is not a failure. The Issues column is the open-issue count from the repository record minus the open pull-request count.

## Pull Requests and Quality

`pull_requests` and `quality` are on unless a profile sets them false. Off leaves that column out of the list. The detail says the check is skipped. `quality` is the open CodeQL alert count.

## Standards

Each enabled rule is **PASS**, **FAIL**, or **ERROR**. A rule left off is **SKIPPED**. **FAIL** and **ERROR** change Status unless the release result is **No releases**.

## Security

The security check is always skipped. Disabled profiles say `Security checks are disabled.` Enabled profiles say `Security checks are not implemented yet.` A skip is not a claim that the repository is secure.

## Status Before Any Check

| Status             | Meaning                                         |
| ------------------ | ----------------------------------------------- |
| Disabled           | `enabled` is false                              |
| Not synchronised   | The cache has no repository record yet          |
| Unavailable        | GitHub returned 404                             |
| Error              | The repository record failed for another reason |
