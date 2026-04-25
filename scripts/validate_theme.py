"""Validate community theme structure and required CSS variables."""
import sys
import os
import json

REQUIRED_VARS = [
    "--background", "--foreground", "--card", "--card-foreground",
    "--primary", "--primary-foreground", "--secondary", "--secondary-foreground",
    "--muted", "--muted-foreground", "--accent", "--accent-foreground",
    "--destructive", "--destructive-foreground", "--border", "--input",
    "--ring", "--radius", "--score-gold", "--score-silver", "--score-bronze",
    "--team-active", "--team-finished", "--hint-used",
]

REQUIRED_MANIFEST_FIELDS = ["name", "identifier", "author", "version", "description"]

errors = []

themes_dir = "themes"
if not os.path.isdir(themes_dir):
    print("✅ No themes directory — nothing to validate")
    sys.exit(0)

for theme_dir in os.listdir(themes_dir):
    path = f"{themes_dir}/{theme_dir}"
    if not os.path.isdir(path):
        continue

    manifest_path = f"{path}/manifest.json"
    if not os.path.exists(manifest_path):
        errors.append(f"{theme_dir}: missing manifest.json")
        continue

    with open(manifest_path) as f:
        manifest = json.load(f)

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"{theme_dir}: manifest missing field '{field}'")

    css_path = f"{path}/theme.css"
    if not os.path.exists(css_path):
        errors.append(f"{theme_dir}: missing theme.css")
        continue

    with open(css_path) as f:
        css_content = f.read()

    for var in REQUIRED_VARS:
        if var not in css_content:
            errors.append(f"{theme_dir}: theme.css missing required variable '{var}'")

    if not os.path.exists(f"{path}/preview.png"):
        errors.append(f"{theme_dir}: missing preview.png")

if errors:
    print("❌ Theme validation failed:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("✅ All themes valid")
