# GitHub Intel

`github-intel` monitors an explicit list of GitHub repositories. It stores the results in a local cache and can show them without a network connection. Groups organise the list. Profiles decide which checks run.

## Behaviour

- The repository list is configuration, not a search of every repository you can see.
- Profiles turn checks on or off. A repository without a profile uses `defaults.profile`.
- Synchronisation reads GitHub and writes the cache. Listing, reports, and the terminal interface read the cache.
- Authentication uses the GitHub CLI login. The token is not stored.
- One repository failure does not cancel the others.

## Requirements

- Python 3.11 or later.
- The GitHub CLI (`gh`) logged in, for private repositories and for checks that need a token.
- Public repositories can be read without a token. GitHub's unauthenticated rate limit still applies.
