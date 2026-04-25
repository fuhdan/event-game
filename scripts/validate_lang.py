"""Validate language pack has all required translation keys."""
import sys
import os
import json

errors = []

langs_dir = "langs"
if not os.path.isdir(langs_dir):
    print("✅ No langs directory — nothing to validate")
    sys.exit(0)

base_path = f"{langs_dir}/en/translations/en.json"
if not os.path.exists(base_path):
    print("⚠️  No base en.json found — skipping key validation")
    sys.exit(0)

with open(base_path) as f:
    base_keys = set(json.load(f).keys())

for lang_dir in os.listdir(langs_dir):
    if lang_dir == "en":
        continue
    path = f"{langs_dir}/{lang_dir}"
    if not os.path.isdir(path):
        continue

    manifest_path = f"{path}/manifest.json"
    if not os.path.exists(manifest_path):
        errors.append(f"{lang_dir}: missing manifest.json")
        continue

    trans_dir = f"{path}/translations"
    if not os.path.isdir(trans_dir):
        errors.append(f"{lang_dir}: missing translations/ directory")
        continue

    lang_files = [f for f in os.listdir(trans_dir) if f.endswith(".json")]
    if not lang_files:
        errors.append(f"{lang_dir}: no .json files in translations/")
        continue

    for lang_file in lang_files:
        with open(f"{trans_dir}/{lang_file}") as f:
            lang_keys = set(json.load(f).keys())
        for key in base_keys - lang_keys:
            errors.append(f"{lang_dir}/{lang_file}: missing translation key '{key}'")

if errors:
    print("❌ Language pack validation failed:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("✅ All language packs valid")
