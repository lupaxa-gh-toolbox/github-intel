# Frequently Asked Questions

## Does it watch every repository I can see?

No. It watches `repositories.yml`. Adding a repository is a configuration change. `--validate` is optional and only checks that GitHub can see that one name.

## Does the default profile apply to every repository?

`defaults.profile` applies only where a repository omits `profile`. Set `profile` on the repositories that should use a different check set, and leave the default as `upstream`.

## Does a private repository work over SSH?

The GitHub API does not use an SSH key. The same GitHub account is used through `gh auth token`.

## Does a workflow run change Status?

No. The workflow check lists the workflow files and each file's own state. It does not read run history.
