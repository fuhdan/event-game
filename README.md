# Event Game Framework

A self-hosted, community-extensible platform for running team-based events — escape rooms, CTF challenges, quiz nights, and more.

## Features
- Multi-language support (community language packs)
- Dynamic theming per event (community themes)
- AI game master chatbot (Ollama / Claude / OpenAI)
- Real-time leaderboard (WebSockets + SSE)
- Team management with CSV import/export
- Admin dashboard with live event status
- Azure OAuth + custom JWT authentication

## Quick Start (Development)

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.dev.yml up
```

Open http://localhost:3000

## Documentation
- [User Guide](docs/userguide/)
- [Admin Guide](docs/adminguide/)
- [Developer Guide](docs/developerguide/)
- [Community Contributions](docs/community/)

## Community
- Themes: fork [event-game-theme-template](https://github.com/event-game/event-game-theme-template)
- Language packs: fork [event-game-lang-template](https://github.com/event-game/event-game-lang-template)
- Events: fork [event-game-event-template](https://github.com/event-game/event-game-event-template)

## License
MIT
