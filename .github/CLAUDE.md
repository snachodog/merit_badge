# .github Template Repo

This repo is a GitHub [community health files](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file) template. Files here (issue templates, workflow stubs, etc.) are inherited by other repos in the organization/account that don't define their own versions.

## Purpose

- `ISSUE_TEMPLATE/` — default issue templates (GitHub auto-applies to all repos)
- `workflows/` — reusable workflow stubs (called via `workflow_call`)
- `templates/` — files to copy into other repos; not auto-applied by GitHub
- `ai/claude/` — shared AI/Claude instructions, imported locally via `CLAUDE.local.md`
- Community health files (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `FUNDING.yml`) — GitHub auto-applies to repos that don't define their own

Changes to community health files and `ISSUE_TEMPLATE/` propagate downstream. Be deliberate.

## Commits

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) spec:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**

| Type | Use for |
|------|---------|
| `feat` | new template, workflow, or file |
| `fix` | correction to existing template or workflow |
| `docs` | documentation only |
| `refactor` | restructure without behavior change |
| `chore` | repo hygiene (rename, move, gitignore) |
| `ci` | changes to workflows themselves |

**Rules:**
- Description is lowercase, imperative mood, no trailing period
- Breaking changes get `!` after type: `feat!: rename issue template fields`
- Scope is the affected area: `feat(workflows): add docker-build stub`

**Examples:**
```
feat(issue-template): add security vulnerability report template
fix(workflows): correct docker-build trigger condition
chore: update .gitignore
```

## Shared AI Instructions

This repo is the committed home for AI/Claude instructions that are shared across projects. Individual repos may have local (uncommitted) instruction files — when those instructions are general enough to reuse, they get gathered here and committed so they can serve as templates.

### Folder structure

```text
ai/
  claude/
    conventions/      # commit style, code style, naming rules
    workflows/        # how to approach common tasks (PR review, debugging, etc.)
    context/          # org/project background that any repo can import
  prompts/            # reusable prompt fragments

templates/            # copy-paste these into other repos (.github/ subfolder)
  PULL_REQUEST_TEMPLATE.md
  dependabot.yml
  CODE_OF_CONDUCT_PUBLIC.md   # civic/gov-adjacent repos (Montana sunshine law)
```

### Gathering instructions from local repos

When you have an uncommitted instruction file in a local repo that belongs here:

1. Copy the file into the appropriate `ai/` subfolder
2. Strip anything repo-specific (paths, project names, credentials)
3. Commit with `feat(ai): add <description>` — e.g. `feat(ai): add conventional commit instructions`

### Using these instructions in other repos

In each repo's local (uncommitted) `CLAUDE.local.md`, import from this repo's checked-out path:

```markdown
@~/OneDrive/Documents/GitHub/.github/ai/claude/conventions/commits.md
@~/OneDrive/Documents/GitHub/.github/ai/claude/context/org.md
```

This keeps one committed source of truth, referenced locally — no duplication, no sensitive data committed elsewhere.
