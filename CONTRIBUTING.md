# Contributing to Event Game Framework

Thank you for contributing! This guide covers core framework contributions.
For themes, language packs, and events see [docs/community/](docs/community/).

## Development Setup

```bash
git clone https://github.com/event-game/event-game
cd event-game
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.dev.yml up
```

## Branch Naming

| Prefix | Use for |
|---|---|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `hotfix/` | Emergency production fixes |
| `chore/` | Config, deps, docs |

## Pull Requests

1. Branch from `main`
2. CI must be green before review
3. One logical change per PR
4. Reference any related issue

## Code Standards

See `.claude/rules/` for all coding, design, security, logging, and testing rules.
These are enforced automatically by CI.

## Commit Messages

```
feat: add Azure OAuth provider
fix: correct team score calculation on tie
chore: update ruff to 0.4.0
```
