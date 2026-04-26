# Event Game Framework — Application Design

> **For agentic workers:** Use `superpowers:brainstorming` before any implementation. Each phase below becomes its own spec → plan → implementation cycle.

**Goal:** A self-hosted event platform for escape rooms, CTF events, and team challenges. Operators run events via YAML files. Players log in, solve games, chat with an AI hint assistant, and watch a real-time leaderboard. Community contributors publish games, themes, and language packs.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / PostgreSQL / Redis / structlog; React 19 / TypeScript / Vite / Tailwind CSS / shadcn/ui / React Router v6; Docker Swarm / Traefik / Nginx

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Active events | One active event at a time (`is_active` flag) | Simplicity; operators swap events by changing YAML |
| Users/teams scoping | Decoupled from events — connected only via `game_progress` | Teams persist across events; leaderboard scoped by `game.event_id` |
| Player seeding | Dedicated `players.yml` (not embedded in event YAML) | Event YAMLs are shareable with zero personal data |
| Game start/stop | Docker SDK from backend API; admin UI triggers via HTTP | Frontend never touches Docker socket |
| Event/game matching | Startup health-check all game `/health` URLs; unhealthy events blocked | Prevents loading a 6-game event when only 4 containers are running |
| Scoring mode | Per event: `points` (sum of game points) or `completion` (games solved count) | Supports competitive and social events |
| Player mode | Per event: `team` or `individual`; individual auto-creates solo team named after player | Minimal data model change |
| AI chat | Yes — context-aware hints using team game progress milestones | Key differentiator |
| Game ratings | Yes — 1–5 stars after completion | Community feedback for operators |
| Real-time | WebSocket for AI chat (bidirectional); SSE for leaderboard + admin feeds | Right tool per direction of data flow |
| React patterns | `useActionState`, `useOptimistic`, `use()` + Suspense, `useTransition`, native metadata | React 19 throughout, no legacy patterns |

---

## Data Model

Ten tables. Users and teams are system-level and decoupled from events. The `game_progress` table is the natural connector between teams and events (via `game.event_id`).

### `users`
```
id, username, email, password_hash, azure_id (nullable),
role (admin|team_captain|player), is_active,
team_id (nullable FK → teams) — null = unassigned pool
```

### `refresh_tokens`
```
id, user_id (FK), token_hash, expires_at, is_revoked
```

### `teams`
```
id, name, invite_code, is_solo (bool — true for individual mode solo teams)
```
No `event_id` — teams persist across events.

### `events`
```
id, slug, title, year, description, author,
scoring_mode (points|completion), mode (team|individual),
theme, language, ui_text (JSON — locale → key → value),
is_active, health_ok (bool — set by startup health checker)
```

### `games`
```
id, event_id (FK), slug (unique, indexed), title, description,
category, points, image, solution_answer (nullable),
url, milestones (JSON), hints (JSON), dependencies (JSON)
```

### `game_progress`
```
id, game_id (FK), team_id (FK),
milestone (nullable), is_completed, completed_at (nullable),
submitted_answer (nullable)
UNIQUE (game_id, team_id)
```

### `game_ratings`
```
id, game_id (FK), user_id (FK), rating (1–5), created_at
UNIQUE (game_id, user_id)
```

### `chat_sessions`
```
id, team_id (FK), game_id (nullable FK — provides hint context), created_at
```

### `chat_messages`
```
id, session_id (FK), role (user|assistant),
content (AES-256-GCM encrypted, unique nonce per message), created_at
```

### `system_config`
```
id, key (unique), value, updated_at
```
Stores AI provider, model name, system prompt, and other operator settings.

### Leaderboard query (points mode)
```sql
SELECT teams.name, SUM(games.points) AS score, COUNT(*) AS solved
FROM game_progress
JOIN games ON games.id = game_progress.game_id
JOIN teams ON teams.id = game_progress.team_id
WHERE games.event_id = (SELECT id FROM events WHERE is_active = true)
  AND game_progress.is_completed = true
GROUP BY teams.id
ORDER BY score DESC
```

---

## Backend Architecture

### Layer structure
```
Routes (api/)  →  validate input, call service, return response
Services       →  all business logic, no HTTP concerns
Models         →  SQLAlchemy ORM, no logic
Schemas        →  Pydantic for every endpoint input and output
Seeds          →  YAML loaders (events/*.yml, players.yml)
```

### API modules
```
backend/app/api/
├── auth/
│   ├── login.py          POST /v1/auth/login, POST /v1/auth/logout
│   ├── refresh.py        POST /v1/auth/refresh
│   ├── oauth.py          GET  /v1/auth/azure, GET /v1/auth/azure/callback
│   └── me.py             GET  /v1/auth/me  ← game containers call this
├── users/
│   ├── profile.py        GET/PATCH /v1/users/me
│   └── management.py     Admin CRUD /v1/admin/users
├── teams/
│   ├── membership.py     POST /v1/teams/join, GET /v1/teams/me
│   └── management.py     Admin CRUD + assign + randomize /v1/admin/teams
├── events/
│   ├── current.py        GET /v1/events/current
│   └── management.py     Admin activate/edit /v1/admin/events
├── games/
│   ├── list.py           GET /v1/games
│   ├── progress.py       POST /v1/games/{slug}/progress
│   ├── submission.py     POST /v1/games/{slug}/submit
│   ├── ratings.py        POST /v1/games/{slug}/rating
│   └── docker.py         POST /v1/admin/games/{slug}/start|stop
├── leaderboard/
│   └── current.py        GET /v1/leaderboard
├── ai/
│   └── chat.py           (WebSocket handler — see websocket/)
├── sse/
│   ├── leaderboard.py    GET /v1/sse/leaderboard
│   ├── admin_progress.py GET /v1/sse/admin/progress
│   ├── admin_security.py GET /v1/sse/admin/security
│   └── admin_broadcast.py GET /v1/sse/admin/broadcast
└── websocket/
    └── chat.py           WS /ws/chat — bidirectional AI chat stream
```

### Service modules
```
backend/app/services/
├── auth_service.py          JWT issue/verify, refresh token rotation
├── azure_oauth_service.py   Token validation, required claim mapping
├── user_service.py          CRUD, role checks, unassigned pool query
├── team_service.py          Create, join, randomize, move players
├── event_service.py         Load active event, health-check games
├── game_service.py          Slug lookup, progress, answer check
├── docker_service.py        Start/stop Swarm services via Docker SDK
├── leaderboard_service.py   Score calculation, ranking, SSE broadcast
├── ai_chat_service.py       Provider routing, context building, hint generation
├── ai_provider_factory.py   Pluggable: Ollama / Claude / OpenAI
├── ai_context_builder.py    Reads game_progress milestones → shapes prompt
├── ai_prompt_security.py    Injection detection before any LLM call
├── rating_service.py        Store + aggregate game ratings
└── websocket_manager.py     Manage connected clients, broadcast updates
```

### Seed modules
```
backend/app/seeds/
├── event_loader.py     Parse events/*.yml, validate structure, seed events + games
├── player_loader.py    Parse players.yml, seed users + teams + assignments
└── health_checker.py   Ping all game /health URLs; set event.health_ok
```

### Startup sequence
1. Connect PostgreSQL + Redis
2. Run Alembic migrations
3. Load `players.yml` → seed users and teams (idempotent — skip existing)
4. Load all `events/*.yml` → seed events and games (idempotent)
5. Health-check all game container URLs for every event
6. Set `event.health_ok = true|false` per event
7. Start FastAPI application, WebSocket server, SSE

### Real-time architecture
| Channel | Protocol | Direction | Consumers |
|---|---|---|---|
| `/ws/chat` | WebSocket | bidirectional | Player AI chat |
| `/v1/sse/leaderboard` | SSE | server → client | Player leaderboard page |
| `/v1/sse/admin/progress` | SSE | server → client | Admin progress dashboard |
| `/v1/sse/admin/security` | SSE | server → client | Admin security dashboard |
| `/v1/sse/admin/broadcast` | SSE | server → client | Player notification area |

---

## Frontend Architecture

### Routes
```
/login                    public
/dashboard                player home
/games                    game cards with play buttons
/leaderboard              real-time (SSE)
/team                     members, progress, captain controls
/profile                  password change, ratings given
/admin/events             list, edit, activate/deactivate, health status
/admin/games              container health, Docker start/stop
/admin/teams              unassigned pool, drag-assign, randomize
/admin/users              CRUD, role, team assignment
/admin/ai                 provider, model, system prompt
/admin/progress           live milestone feed (SSE)
/admin/security           failed logins, rate limits, injection attempts (SSE)
/admin/ips                banned IPs, manual unban
```

Admin routes are lazy-loaded (`React.lazy`) — admin code never ships to player browsers.

### Folder structure
```
frontend/src/
├── pages/
│   ├── Login/
│   ├── Dashboard/
│   ├── Games/
│   ├── Leaderboard/
│   ├── Team/
│   ├── Profile/
│   └── admin/
│       ├── AdminEvents/
│       ├── AdminGames/
│       ├── AdminTeams/
│       ├── AdminUsers/
│       ├── AdminAI/
│       ├── AdminProgress/
│       ├── AdminSecurity/
│       └── AdminIPs/
├── components/
│   ├── layout/
│   │   ├── Header/
│   │   ├── Footer/
│   │   └── AdminLayout/
│   ├── GameCard/
│   ├── LeaderboardTable/
│   ├── TeamMemberList/
│   ├── StarRating/
│   ├── GameHealthBadge/
│   └── AIChat/
│       ├── ChatWidget/
│       ├── ChatMessage/
│       └── ChatInput/
├── hooks/
│   ├── useAuth.ts
│   ├── useSSE.ts           generic SSE hook (url → stream of events)
│   ├── useLeaderboard.ts   wraps useSSE
│   ├── useWebSocket.ts     chat WebSocket + reconnect logic
│   ├── useTheme.ts         (already spec'd)
│   └── useLang.ts          (already spec'd)
├── services/
│   ├── api.ts              fetch client, attaches cookies, handles 401
│   ├── extensionApi.ts     (already spec'd)
│   └── websocketClient.ts  WebSocket factory
├── providers/
│   ├── AuthProvider/       user context, protected route wrapper
│   ├── ExtensionProvider/  (already spec'd)
│   └── WebSocketProvider/  chat socket context
└── router.tsx              React Router v6
```

### React 19 patterns used throughout

| Pattern | Where used |
|---|---|
| `useActionState` | Login, game submission, team join, password change, all forms |
| `useOptimistic` | Star ratings, game submission feedback |
| `use()` + Suspense | Data fetching on Dashboard, Games, Team pages |
| `useTransition` | Leaderboard SSE updates, Docker start/stop in admin |
| Native `<title>` | Each page sets its own — no react-helmet |
| `ref` as prop | ChatInput, StarRating — no forwardRef |

### State management
React Context only — no Redux or Zustand needed.
- `AuthContext` — current user, login/logout
- `ExtensionContext` — lang data (from useLang)
- `WebSocketContext` — chat socket connection, message queue

---

## Implementation Phases

Eight phases. Each phase delivers working, testable software and maps to one Jira epic.

| Phase | Epic | Delivers | Depends on |
|---|---|---|---|
| 1 | Core Backend & Auth | Running API, JWT login, Azure OAuth, all migrations | DEV-1 (Setup Environment) |
| 2 | Seeding System & Docker Manager | YAML loading, health checker, team randomizer, Docker start/stop | Phase 1 |
| 3 | Frontend Foundation | Login page, routing, AuthProvider, ExtensionProvider, layout | Phase 1 |
| 4 | Player Gameplay Loop | Games list, progress, submission, SSE leaderboard, all player pages | Phases 2 + 3 |
| 5 | AI Chat | WebSocket chat, provider factory, context builder, prompt security | Phase 4 |
| 6 | Game Ratings | Rating endpoint, aggregation, StarRating component | Phase 4 |
| 7 | Admin Dashboard | All admin pages, SSE feeds, Docker UI, IP management | Phases 4 + 5 |
| 8 | Community Extensions | Themes, lang packs, game templates, validation CI | Phases 2 + 3 (already spec'd) |

---

## Future Features (Backlog)

- Player self-registration via WhatsApp
- Player self-registration via Microsoft Teams
- Analytics dashboard (game completion time, drop-off rates per milestone)
- Event archive / history browser (past events + scores)
