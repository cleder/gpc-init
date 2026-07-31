# Triage Labels

The skills speak in terms of five canonical triage roles.
This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                   |
| --------------------------- | --------------------- | ----------------------------------------- |
| `needs-triage`               | `needs-triage`         | Maintainer needs to evaluate this issue   |
| `needs-info`                 | `needs-info`           | Waiting on reporter for more information  |
| `ready-for-agent`            | `ready-for-agent`      | Fully specified, ready for an AFK agent   |
| `ready-for-human`            | `ready-for-human`      | Requires human implementation             |
| `wontfix`                    | `wontfix`              | Will not be actioned                      |

`wontfix` already exists as a label on `cleder/gpc-init`.
The other four (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`) don't exist yet — create them with `gh label create <name>` before a skill first tries to apply them, or let the skill create them on first use.
