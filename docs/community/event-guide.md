# Event Creation Guide

Community events define the games players play during a session — puzzles, point values, hints, and structure.

## Quick Start

1. Fork [event-game-event-template](https://github.com/event-game/event-game-event-template)
2. Edit `event.yml` with your game content
3. Add any assets (images, audio) to `assets/`
4. Update `manifest.json`
5. Validate: run the event validator (see template README)
6. Submit via GitHub Issue

## event.yml Schema

```yaml
name: "Escape the Lab"
description: "A science-themed escape room for teams of 4-6"
difficulty: medium        # easy | medium | hard
min_teams: 2
max_teams: 20
estimated_duration_minutes: 90
games:
  - id: puzzle-1
    title: "The Locked Door"
    type: code_input      # code_input | multiple_choice | image_puzzle
    points: 100
    hint: "Look at the periodic table"
    solution: "Au79"
```
