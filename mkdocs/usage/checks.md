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

The list shows that word. The detail shows the sentence, and it does not put the word in front of the sentence.

The release date is the publish date of that tag. Drafts are skipped.

## Workflows

The check lists workflow files. It does not read run history. A missing or expired run is not a status.

| Status             | Meaning                              |
| ------------------ | ------------------------------------ |
| No workflows found | The repository has no workflow files |
| Error              | The workflow list could not be read  |

The detail has one **Workflows** row. Each workflow is one line, and the states share a column: **Active**, **Manually Disabled**, **Inactivity Disabled**, **Fork Disabled**, or the state's own words.

A missing state is **Unknown**. **Active** is green, a disabled state is dim, and **Unknown** is yellow. An empty list is **No workflows found**. When the profile has workflows turned off, the row is `SKIPPED — Workflow checks are disabled.`

## Issues

The default list does not include Issues. A written list leaves the cell blank when the check is off. The detail says `SKIPPED — Issue checks are disabled.`

The Issues column is GitHub's `open_issues_count`. Open pull requests are not subtracted. The issues list is not requested.

## Pull Requests and Quality

`pull_requests` and `quality` are on unless a profile sets them false. The default list does not include those columns. A written list leaves the cell blank when the check is off. The detail says the check is skipped.

`quality` is the open CodeQL alert count. **0** means there are none.

**No scanning** means GitHub has no code scanning analysis, or Code Security is not enabled. **Forbidden** means the token cannot read the alerts. **Unknown** means the count could not be read for another reason.

Dependabot Alerts is the open Dependabot count. **0** means there are none.

**Disabled** means Dependabot alerts are turned off. **Forbidden** means the token cannot read them. **Unknown** means the count could not be read for another reason.

## Status Before Any Check

| Status             | Meaning                                         |
| ------------------ | ----------------------------------------------- |
| Disabled           | `enabled` is false                              |
| Not synchronised   | The cache has no repository record yet          |
| Unavailable        | GitHub returned 404                             |
| Error              | The repository record failed for another reason |
