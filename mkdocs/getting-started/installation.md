# Installation

Install the latest release from PyPI.

```bash
pip install lupaxa-github-intel
```

Verify the installation.

```bash
github-intel --version
```

Upgrade an existing install with the same command:

```bash
pip install --upgrade lupaxa-github-intel
```

## GitHub CLI

Private repositories and alert counts need a token. GitHub Intel runs `gh auth token` and uses that token for the request. It does not write the token into configuration, the cache, reports, or logs.

```bash
gh auth login
```

When `gh` is not logged in, public repositories are requested without credentials.

## Development Install

From a checkout:

```bash
make init
make python-install-dev
```

Lint, type-check, and test:

```bash
make python-check
```

Serve this documentation site locally:

```bash
make mkdocs-serve
```
