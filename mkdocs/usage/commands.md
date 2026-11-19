# Commands

`github-intel` with no arguments opens the terminal interface when both stdin and stdout are terminals. Otherwise it prints help.

Global options apply before the subcommand.

| Option            | Description                                      |
| ----------------- | ------------------------------------------------ |
| `--config FILE`   | Main configuration file                          |
| `--verbose`       | Debug logs on stderr                             |
| `--debug`         | Debug logs on stderr                             |
| `--version`       | Print the version and exit                       |

## Repositories

`list` is also available as `github-intel list`.

| Command                                      | Description                                      |
| -------------------------------------------- | ------------------------------------------------ |
| `repo add OWNER/NAME`                        | Add a repository. Does not call GitHub           |
| `repo add OWNER/NAME --validate`             | Add it after GitHub confirms it is visible       |
| `repo remove OWNER/NAME`                     | Remove it from configuration. The cache stays    |
| `repo enable OWNER/NAME`                     | Include it in synchronisation                    |
| `repo disable OWNER/NAME`                    | Keep it and skip synchronisation                 |
| `repo set-profile OWNER/NAME PROFILE`        | Assign a profile                                 |
| `repo set-group OWNER/NAME GROUP`            | Assign a group                                   |
| `repo list`                                  | Print the cached table                           |
| `repo show ORG REPO`                         | Print one repository                             |

`repo show` also accepts `owner/name` as a single argument.

`repo list` filters:

| Option           | Description                                              |
| ---------------- | -------------------------------------------------------- |
| `--group NAME`   | One group                                                |
| `--profile NAME` | One profile                                              |
| `--tag NAME`     | One tag, compared without case                           |
| `--status NAME`  | Cache state, such as `cached` or `not-synchronised`      |
| `--sort KEY`     | `name`, `group`, `profile`, or `updated`                 |
| `--format NAME`  | `table`, `json`, `csv`, or `markdown`                    |

`--status` matches the cache state. It does not match the Status column. `--status Healthy` matches nothing.

## Synchronise and Inspect

| Command                         | Description                                      |
| ------------------------------- | ------------------------------------------------ |
| `sync`                          | Refresh stale or missing information             |
| `sync --force`                  | Ignore freshness windows and `sync.interval`     |
| `sync --repo OWNER/NAME`        | One repository                                   |
| `sync --group NAME`             | One group                                        |
| `sync --profile NAME`           | One profile                                      |
| `sync --concurrency N`          | Override the request limit for this run          |
| `sync --fail-on-checks`         | Exit 6 when a check failed                       |
| `report`                        | Markdown export of the cache                     |
| `report --format json`          | JSON export                                      |
| `audit`                         | Repositories whose checks failed                 |
| `releases`                      | Cached release check rows                        |
| `workflows`                     | Cached workflow check rows                       |

`releases` and `workflows` print a row only when that check was stored. A profile that leaves the check off produces no line.

## Profiles, Configuration, and Cache

| Command                         | Description                                      |
| ------------------------------- | ------------------------------------------------ |
| `profile list`                  | Profile names                                    |
| `profile show NAME`             | Effective checks                                 |
| `profile show NAME --resolved`  | Include the profile that set each flag           |
| `profile tree`                  | Inheritance chains                               |
| `profile validate`              | Resolve every profile                            |
| `config init`                   | Write the default files. `--force` overwrites    |
| `config show`                   | Resolved settings as JSON                        |
| `config validate`               | Load the files and report the repository count   |
| `config paths`                  | Configuration and cache paths                    |
| `cache info`                    | Size and row counts                              |
| `cache clear`                   | Delete cached rows. Prompts unless `--yes`       |
| `cache clear --repo OWNER/NAME` | Delete one repository's cache                    |
| `cache vacuum`                  | Rebuild the SQLite file                          |
| `reset`                         | Delete the cache files. Configuration stays      |
| `tui`                           | Open the terminal interface                      |
