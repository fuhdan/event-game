# Language Pack Guide

Language packs translate the player and admin interface into other languages.

## Quick Start

1. Fork [event-game-lang-template](https://github.com/event-game/event-game-lang-template)
2. Rename to `event-game-lang-<language-code>` (e.g. `event-game-lang-de`)
3. Copy `translations/en.json` → `translations/<code>.json`
4. Translate all values (keep all keys exactly as-is)
5. Update `manifest.json`
6. Validate: `python validate_lang.py`
7. Submit via GitHub Issue

## RTL Languages

For right-to-left languages (Arabic, Hebrew, etc.), set `"rtl": true` in `manifest.json`.
The framework applies `dir="rtl"` to the HTML element automatically.
