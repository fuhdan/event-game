# Community Extension Ecosystem Design

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this spec task-by-task.

**Goal:** Define the architecture for all four community extension types — games, themes, language packs, and events — so the framework can grow through community contributions without operator complexity.

**Architecture:** Four separate community repositories, each with a validated template. Extensions are drop-in: games deploy as Docker services in the operator's Swarm stack; themes and language packs are volume-mounted into Nginx at runtime; events are YAML files copied onto the server.

**Tech Stack:** Docker Swarm, Nginx volume mounts, CSS custom properties, FastAPI (main backend API contract), GitHub Actions (CI validation per community repo).

---

## Community Repositories

Four repositories, one per extension type:

| Repo | Extension type | Install mechanism |
|---|---|---|
| `event-game-games` | Docker game containers | Added as service in Swarm stack |
| `event-game-themes` | CSS theme files | Volume-mounted into Nginx container |
| `event-game-langs` | JSON language packs | Volume-mounted into Nginx container |
| `event-game-events` | Example event YAMLs | Copied into `events/` on the server |

Each repo:
- Contains a `template/` directory (annotated starting point for contributors)
- Has CI that validates every PR (schema, required fields, contract compliance)
- Is browsable on GitHub — operators discover extensions by browsing the repo

Operators install extensions by browsing the community repo, downloading what they want, and dropping it in the appropriate host directory. No package manager or registry needed.

---

## Extension Type 1: Games

### Design decisions

- **Games deploy inside the operator's Swarm stack** (not self-hosted by the game creator). This is required because auth uses HTTPOnly cookies — the game must share the Docker internal network with the main backend.
- **Operator defines all game config in the event YAML** — no per-game manifest file. The same game image can appear with different titles, descriptions, and narratives across different events.
- **Slug-based game identification** — avoids the chicken-and-egg problem of DB-assigned integer IDs at deploy time.
- **Progress milestone API** — game containers report intermediate milestones so the AI hint system knows where the player is. Web terminal is NOT mandated; players use real tools.

### API contract

Every game must implement:

```
GET /health → {"status": "healthy", "game": "<slug>"}
```

Every game receives these env vars:

| Var | Example | Purpose |
|---|---|---|
| `MAIN_BACKEND_URL` | `http://event-game-backend:8000` | Internal Docker address of main backend |
| `GAME_SLUG` | `slide-puzzle` | Stable game identifier |
| `SOLUTION_ANSWER` | `CALL ME ISHMAEL` | Expected answer string (omit if game self-validates) |
| `CORS_ORIGINS` | `https://events.example.com` | Comma-separated allowed origins |

Every game calls the main backend:

```
GET  /v1/auth/me
     Forward player's access_token cookie → {user_id, username, team_id, role} or 401

POST /v1/games/{GAME_SLUG}/progress
     Forward player's access_token cookie
     Body: {"milestone": "ssh_connected"}
     → Records progress for AI hint context

POST /v1/games/{GAME_SLUG}/submit
     Forward player's access_token cookie
     Body: {"solution": "CALL ME ISHMAEL"}
     → {correct: true, points: 100} or {correct: false}
```

### Event YAML game block

```yaml
games:
  - slug: command-injection
    title: "Breach the Vault"
    description: "Find and exploit the vulnerable endpoint to gain shell access."
    category: security
    points: 150
    image: ghcr.io/event-game-games/command-injection:2.1.0
    solution_answer: "FLAG{r3v3rs3_sh3ll}"
    url: https://events.example.com/games/command-injection
    milestones:
      - id: website_found
        ai_context: "Team located the vulnerable site. Do not hint about finding it."
      - id: ssh_connected
        ai_context: "Team has shell access. Hint only about privilege escalation."
      - id: flag_captured
        ai_context: "Team has the flag. Guide them to submit it."
    hints:
      - "The login form does not sanitise inputs."
      - "Think about what happens after you get a shell."
    dependencies:
      - git-forensics
```

### Docker Swarm stack service

```yaml
services:
  game-command-injection:
    image: ghcr.io/event-game-games/command-injection:2.1.0
    environment:
      MAIN_BACKEND_URL: http://event-game-backend:8000
      GAME_SLUG: command-injection
      SOLUTION_ANSWER: "FLAG{r3v3rs3_sh3ll}"
      CORS_ORIGINS: "https://events.example.com"
    networks:
      - event-game-internal
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.cmd-injection.rule=Host(`events.example.com`) && PathPrefix(`/games/command-injection`)"
```

Games are on the internal Docker network only — never publicly exposed directly.

### `event-game-games` repo structure

```
event-game-games/
├── template/                  # Annotated minimal game — fork this to start
│   ├── Dockerfile
│   ├── .env.example           # Documents all required env vars
│   ├── app/
│   │   ├── main.py            # GET /health + game routes
│   │   ├── auth.py            # Cookie forwarding to /v1/auth/me
│   │   ├── progress.py        # POST /v1/games/{slug}/progress helper
│   │   └── submit.py          # POST /v1/games/{slug}/submit helper
│   └── README.md              # Contract explanation + local dev guide
├── slide-puzzle/
├── command-injection/
├── git-forensics/
└── ...
```

### Optional: web terminal component

For games where a browser terminal makes sense (log analysis, PowerShell forensics), a pre-built `web-terminal/` component is provided in the repo. Game creators can embed it — it is not required.

### Operator install workflow

```bash
# 1. Add game service to docker-stack.prod.yml (copy from game README)
# 2. Add game block to event YAML
docker stack deploy --compose-file docker-stack.prod.yml event-game
```

---

## Extension Type 2: Themes

### Format

A single CSS file that overrides design tokens via CSS custom properties:

```css
/* themes/cyberpunk/theme.css */
[data-theme="cyberpunk"] {
  --primary: 280 100% 60%;
  --primary-foreground: 0 0% 100%;
  --background: 222 84% 5%;
  --accent: 142 76% 36%;
  --card: 222 47% 10%;
  --font-family: 'Share Tech Mono', monospace;
}
```

The frontend sets `data-theme="cyberpunk"` on `<html>` based on the active event config. No JavaScript processing — pure CSS cascade.

### How themes are served

Volume-mounted into the Nginx frontend container at runtime:

```yaml
# docker-stack.prod.yml
services:
  frontend:
    volumes:
      - ./themes:/usr/share/nginx/html/themes
      - ./langs:/usr/share/nginx/html/langs
```

The default theme is baked into the Docker image. Community themes are drop-in only — no image rebuild needed.

### `event-game-themes` repo structure

```
event-game-themes/
├── template/
│   └── theme.css       # Annotated with every required token + comments
├── cyberpunk/
│   └── theme.css
├── swiss-alpine/
│   └── theme.css
└── ...
```

CI validates: all required tokens present, valid CSS, no hardcoded hex values.

### Operator install workflow

```bash
# Download from event-game-themes repo
cp -r cyberpunk/ /opt/event-game/themes/
# Set in event YAML:
# theme: cyberpunk
# Nginx serves immediately — no restart needed
```

---

## Extension Type 3: Language Packs

### Format

JSON file with UI string keys. Covers only permanent UI chrome — not event-specific text:

```json
{
  "login": {
    "usernamePlaceholder": "Benutzername",
    "passwordPlaceholder": "Passwort",
    "submitButton": "Anmelden"
  },
  "nav": {
    "games": "Spiele",
    "leaderboard": "Rangliste",
    "profile": "Profil"
  },
  "chat": {
    "askAI": "KI um Hilfe fragen...",
    "sendButton": "Senden"
  }
}
```

Event-specific text (taglines, game titles, story text) stays in the event YAML under `ui_text.{locale}`. The frontend merges both at runtime: lang file provides base UI strings, event YAML overrides specific keys per locale.

### `event-game-langs` repo structure

```
event-game-langs/
├── template.json       # Every key documented with English defaults + comments
├── de.json
├── fr.json
├── it.json
└── ...
```

CI validates: all keys from `template.json` are present, valid JSON.

### Operator install workflow

```bash
cp de.json /opt/event-game/langs/
# Set in event YAML:
# language: de
```

---

## Extension Type 4: Events

### Format

YAML file defining the complete event. Operator drops into `events/` on the server; backend picks it up on startup. `is_active: true` selects which event runs.

Event YAML sections: `event` (metadata + `ui_text` per locale), `games` (full game blocks with milestones, hints, dependencies), `teams`, `users`, `dependencies`, `rewards`.

### `event-game-events` repo structure

```
event-game-events/
├── template.yml        # Annotated event YAML with every field explained
├── moby-dick-2026.yml  # Reference event (cybersecurity + puzzles)
├── halloween-2025.yml
└── ...
```

CI validates: required YAML sections present, game slugs valid, milestone IDs unique per game.

### Operator install workflow

```bash
cp halloween_2026.yml /opt/event-game/events/
# Set is_active: true in the YAML
# Restart backend to reseed PostgreSQL
```

---

## Security Notes

- `SOLUTION_ANSWER` in the event YAML is plain text. For security-focused events where players may gain filesystem access to the server, move it to a Docker Secret instead.
- Game containers are on the internal Docker network only — never exposed directly through Traefik.
- The main backend `/v1/auth/me` endpoint is the only auth source; game containers never handle credentials directly.
- CI in community repos validates structure but cannot guarantee game content safety — operators review game source before installing.
