---
name: conventional-commits
description: Conventional Commits spec — commit message format rules for all repos
metadata:
  type: feedback
---

All commits must follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

## Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Types

| Type | Use for |
|------|---------|
| `feat` | new feature or file |
| `fix` | bug fix |
| `docs` | documentation only |
| `refactor` | restructure without behavior change |
| `test` | adding or updating tests |
| `chore` | repo hygiene (rename, move, gitignore) |
| `ci` | workflow or pipeline changes |
| `perf` | performance improvement |
| `revert` | revert a prior commit |

## Rules

- Description: lowercase, imperative mood, no trailing period
- Breaking changes: append `!` after type — `feat!: rename issue template fields`
- Scope: the affected subsystem in parentheses — `feat(auth): add magic link login`
- Body: wrap at 72 chars, explain *why* not *what*
- Footer: reference issues — `Closes #42`, `Refs #7`

## Examples

```
feat(issue-template): add security vulnerability report template
fix(workflows): correct docker-build trigger condition
docs: update contributing guide with branch naming convention
chore: update .gitignore for Python virtual envs
ci(python): pin ruff to 0.4.x
feat!: rename issue template fields for clarity
```
