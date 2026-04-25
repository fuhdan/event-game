"""Validate community event YAML structure."""
import sys
import os

import yaml

REQUIRED_FIELDS = [
    "name", "description", "difficulty", "min_teams",
    "max_teams", "estimated_duration_minutes", "games",
]

VALID_DIFFICULTIES = ["easy", "medium", "hard"]
errors = []

events_dir = "events"
if not os.path.isdir(events_dir):
    print("✅ No events directory — nothing to validate")
    sys.exit(0)

for event_dir in os.listdir(events_dir):
    path = f"{events_dir}/{event_dir}"
    if not os.path.isdir(path):
        continue

    yaml_path = f"{path}/event.yml"
    if not os.path.exists(yaml_path):
        errors.append(f"{event_dir}: missing event.yml")
        continue

    with open(yaml_path) as f:
        try:
            event = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"{event_dir}: invalid YAML — {e}")
            continue

    for field in REQUIRED_FIELDS:
        if field not in event:
            errors.append(f"{event_dir}: event.yml missing required field '{field}'")

    if "difficulty" in event and event["difficulty"] not in VALID_DIFFICULTIES:
        errors.append(f"{event_dir}: difficulty must be one of {VALID_DIFFICULTIES}")

    if "games" in event and not isinstance(event["games"], list):
        errors.append(f"{event_dir}: 'games' must be a list")

    if not os.path.exists(f"{path}/manifest.json"):
        errors.append(f"{event_dir}: missing manifest.json")

if errors:
    print("❌ Event validation failed:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("✅ All events valid")
