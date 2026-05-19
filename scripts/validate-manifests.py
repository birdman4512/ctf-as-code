#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


REQUIRED_CHALLENGE_FIELDS = {
    "name": str,
    "category": str,
    "description": str,
    "value": int,
    "type": str,
    "state": str,
    "flags": list,
    "files": list,
}


def fail(errors, message):
    errors.append(message)


def load_json(path, errors):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        fail(errors, f"{path}: invalid JSON: {exc}")
    except OSError as exc:
        fail(errors, f"{path}: could not read file: {exc}")
    return None


def validate_challenge(path, errors):
    challenge = load_json(path, errors)
    if challenge is None:
        return

    for field, expected_type in REQUIRED_CHALLENGE_FIELDS.items():
        if field not in challenge:
            fail(errors, f"{path}: missing required field '{field}'")
            continue
        if not isinstance(challenge[field], expected_type):
            fail(errors, f"{path}: field '{field}' must be {expected_type.__name__}")

    if isinstance(challenge.get("value"), int) and challenge["value"] < 0:
        fail(errors, f"{path}: field 'value' must be greater than or equal to 0")

    for flag in challenge.get("flags", []):
        if isinstance(flag, str):
            continue
        if isinstance(flag, dict) and isinstance(flag.get("content"), str):
            continue
        fail(errors, f"{path}: flags must be strings or objects with a string 'content'")

    for relative in challenge.get("files", []):
        if not isinstance(relative, str):
            fail(errors, f"{path}: files entries must be strings")
            continue
        file_path = path.parent / relative
        if not file_path.exists():
            fail(errors, f"{path}: referenced file does not exist: {relative}")


def validate_load_manifest(path, errors):
    manifest = load_json(path, errors)
    if manifest is None:
        return

    if not isinstance(manifest.get("ctfd"), dict):
        fail(errors, f"{path}: missing object field 'ctfd'")

    challenges = manifest.get("challenges")
    if not isinstance(challenges, list):
        fail(errors, f"{path}: missing list field 'challenges'")
        return

    for entry in challenges:
        if not isinstance(entry, str):
            fail(errors, f"{path}: challenge entries must be paths")
            continue
        challenge_path = path.parent / entry
        if not challenge_path.exists():
            fail(errors, f"{path}: challenge manifest does not exist: {entry}")
            continue
        validate_challenge(challenge_path, errors)


def main():
    parser = argparse.ArgumentParser(description="Validate CTFd load and challenge manifests.")
    parser.add_argument("--challenges-dir", default="challenges")
    parser.add_argument("--load-manifest", default="ctfd-load.example.json")
    args = parser.parse_args()

    errors = []
    challenges_dir = pathlib.Path(args.challenges_dir)
    if not challenges_dir.exists():
        fail(errors, f"{challenges_dir}: directory does not exist")
    else:
        manifests = sorted(challenges_dir.glob("*/challenge.json"))
        if not manifests:
            fail(errors, f"{challenges_dir}: no challenge manifests found")
        for manifest in manifests:
            validate_challenge(manifest, errors)

    load_manifest = pathlib.Path(args.load_manifest)
    if load_manifest.exists():
        validate_load_manifest(load_manifest, errors)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Manifest validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
