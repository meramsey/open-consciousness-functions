"""Explicit private session entry point; public defaults are never modified."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from jsonschema import Draft7Validator

from .learning_session import render
from .paths import SCHEMAS_DIR
from .utils import OCFError


def load_defaults(path):
    path = Path(path).expanduser()
    data = json.loads(path.read_text())
    schema = json.loads((SCHEMAS_DIR / "private-session.schema.json").read_text())
    errors = list(Draft7Validator(schema).iter_errors(data))
    if errors:
        raise OCFError("invalid private session configuration")
    for name in ("mix_profile",):
        if name not in data:
            continue
        selected = Path(data[name]).expanduser()
        data[name] = str(selected if selected.is_absolute() else path.parent / selected)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "ocf/private-session.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice")
    parser.add_argument("--mix-profile", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_defaults(args.config)
    os.environ.update(config.get("environment", {}))
    result = render(
        output=args.output,
        voice=args.voice or config["voice"],
        mix_profile=args.mix_profile or config.get("mix_profile"),
        locale=config.get("locale", "en-US"),
        native_speed=config.get("native_speed", True),
        pacing_profile=config.get("pacing_profile"),
        backend_defaults=config.get("backend_defaults", True),
        enabled_stages=config.get("enabled_stages", []),
        affirmation=config.get("affirmation"),
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "status": "planned" if args.dry_run else result["status"],
                "human_listening_approved": False,
            }
        )
    )


if __name__ == "__main__":
    main()
