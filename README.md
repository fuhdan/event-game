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







docker stack deploy --compose-file docker-stack-traefik.yml traefik



networks:
  traefik-public:
  driver: overlay
  attachable: true

services:
  traefik:
    image: traefik:latest
    command:
      - --api=true
      - --providers.swarm=true
      - --providers.swarm.endpoint=unix:///var/run/docker.sock
      - --providers.swarm.exposedbydefault=false
      - --providers.swarm.network=traefik_traefik-public
      - --entrypoints.web.address=:80
      - --entrypoints.web.http.redirections.entryPoint.to=websecure
      - --entrypoints.web.http.redirections.entryPoint.scheme=https
      - --entrypoints.websecure.address=:443
      - --providers.file.filename=/etc/traefik/dynamic.yml
    ports:
      - "80:80"
      - "443:443"
    networks:
      - traefik-public
    secrets:
      - tls_cert
      - tls_key
    configs:
      - source: traefik_dynamic
        target: /etc/traefik/dynamic.yml
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role==manager
      labels:
        - "traefik.enable=true"
        - "traefik.docker.network=traefik_traefik-public"
        - "traefik.http.routers.dashboard.rule=Host(`traefik.danielf.local`)"
        - "traefik.http.routers.dashboard.entrypoints=websecure"
        - "traefik.http.routers.dashboard.tls=true"
        - "traefik.http.routers.dashboard.service=api@internal"
        - "traefik.http.services.dashboard.loadbalancer.server.port=8080"

secrets:
  tls_cert:
    external: true
  tls_key:
    external: true

configs:
  traefik_dynamic:
    file: ./dynamic.yml
