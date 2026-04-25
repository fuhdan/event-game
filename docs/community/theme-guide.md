# Theme Creation Guide

Community themes let you change the visual appearance of the framework per event.

## Quick Start

1. Fork [event-game-theme-template](https://github.com/event-game/event-game-theme-template)
2. Rename your fork to `event-game-theme-<your-theme-name>`
3. Edit `theme.css` — replace all placeholder HSL values with your colors
4. Update `manifest.json` with your theme's details
5. Take a screenshot → save as `preview.png`
6. Push to your public repository
7. Submit via [GitHub Issue](https://github.com/event-game/event-game/issues/new?template=theme_submission.md)

## Required CSS Variables

See `.claude/design/design-system.md` in the core framework for the full list.

## Color Format

All colors use HSL without the wrapper: `221 83% 53%` (not `hsl(221, 83%, 53%)`).

## Dark Mode

Include a dark mode variant: `[data-theme="your-theme"][data-color-scheme="dark"] { ... }`
