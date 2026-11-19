# Frequently Asked Questions

## Does it watch every repository I can see?

No. It watches `repositories.yml`. Adding a repository is a configuration change. `--validate` is optional and only checks that GitHub can see that one name.

## Does the default profile apply to every repository?

`defaults.profile` applies only where a repository omits `profile`. Set `profile` on the repositories that should use a different check set, and leave the default as `upstream`.

## Can two profiles require different files?

Yes. Put a `standards` map on the profile. Omitted rules inherit the parent profile, then `defaults.standards`.

## Does a private repository work over SSH?

The GitHub API does not use an SSH key. The same GitHub account is used through `gh auth token`.

## Are cancelled workflow runs failures?

A cancelled, skipped, or neutral conclusion is reported as **Success**. **Failure** is `failure`, `timed_out`, or `startup_failure`.

## Why does the security check never pass?

It is not implemented. The row is always skipped, including when the profile turns security on. That skip does not mean the repository is secure.
