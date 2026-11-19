# Command Reference

The program name is `github-intel`.

## Global

```text
github-intel [--config FILE] [--verbose] [--debug] [--version] COMMAND
```

## Repository List and Show

```text
github-intel repo list [--group NAME] [--profile NAME] [--tag NAME]
                       [--status STATE] [--sort name|group|profile|updated]
                       [--format table|json|csv|markdown]

github-intel repo show ORG REPO [--format table|json]
github-intel repo show OWNER/NAME [--format table|json]
```

`github-intel list` is the same command as `github-intel repo list`.

## Repository Editing

```text
github-intel repo add OWNER/NAME [--group NAME] [--profile NAME]
                                 [--tag NAME]... [--validate]
github-intel repo remove OWNER/NAME
github-intel repo enable OWNER/NAME
github-intel repo disable OWNER/NAME
github-intel repo set-profile OWNER/NAME PROFILE
github-intel repo set-group OWNER/NAME GROUP
```

`repo add` creates the configuration directory on first use. `--validate` is the only form that calls GitHub.

## Synchronisation

```text
github-intel sync [--force] [--group NAME] [--profile NAME]
                  [--repo OWNER/NAME] [--concurrency N]
                  [--fail-on-checks]
```

`--force` ignores cache freshness and `sync.interval`. A sync inside `sync.interval` exits 2.

## Reports and Named Checks

```text
github-intel report [--format markdown|json|csv] [--group NAME]
                    [--profile NAME] [--output FILE]
github-intel audit [--format table|json] [--fail-on-checks]
github-intel releases
github-intel workflows
```

## Profiles, Configuration, and Cache

```text
github-intel profile list
github-intel profile show NAME [--resolved]
github-intel profile tree
github-intel profile validate
github-intel config init [--force]
github-intel config show
github-intel config validate
github-intel config paths
github-intel cache info
github-intel cache clear [--repo OWNER/NAME] [--yes]
github-intel cache vacuum
github-intel reset [--yes]
github-intel tui
```
