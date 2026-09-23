#!/usr/bin/env python3
"""Deterministically regenerate the owned GitHub profile badge row."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCHEMA = "yurei-so/profile-badges/v1"
START = "<!-- profile-badges:start -->"
END = "<!-- profile-badges:end -->"
COLOR = re.compile(r"^[A-Fa-f0-9]{6}$")
KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class BadgeConfigError(ValueError):
    pass


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema") != SCHEMA:
        raise BadgeConfigError(f"config schema must be {SCHEMA}")
    if not isinstance(config.get("style"), str) or not config["style"]:
        raise BadgeConfigError("style must be non-empty text")
    for group in (config.get("static"), config.get("dynamic")):
        if not isinstance(group, list):
            raise BadgeConfigError("badge groups must be arrays")
        for badge in group:
            if not isinstance(badge, dict):
                raise BadgeConfigError("each badge must be an object")
            if not isinstance(badge.get("label"), str) or not badge["label"]:
                raise BadgeConfigError("badge label must be non-empty text")
            if not isinstance(badge.get("color"), str) or not COLOR.fullmatch(badge["color"]):
                raise BadgeConfigError("badge color must be a six-digit hex value")
            logo_color = badge.get("logoColor")
            if logo_color is not None and (
                not isinstance(logo_color, str) or not COLOR.fullmatch(logo_color)
            ):
                raise BadgeConfigError("badge logoColor must be a six-digit hex value")
    keys = [badge.get("key") for badge in config["dynamic"]]
    if any(not isinstance(key, str) or not KEY.fullmatch(key) for key in keys):
        raise BadgeConfigError("dynamic badge keys must be bounded snake_case identifiers")
    if len(keys) != len(set(keys)):
        raise BadgeConfigError("dynamic badge keys must be unique")
    return config


def safe_aggregate_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value) if abs(value) <= 999_999_999 else None
    if isinstance(value, str) and 0 < len(value) <= 40 and re.fullmatch(r"[A-Za-z0-9 ._+:/-]+", value):
        return value
    return None


def load_values(raw: str | None, allowed: set[str]) -> dict[str, str]:
    if raw is None:
        return {}
    if len(raw.encode("utf-8")) > 4096:
        raise BadgeConfigError("dynamic badge values exceed 4096 bytes")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise BadgeConfigError("dynamic badge values must be a JSON object")
    result: dict[str, str] = {}
    for key in sorted(allowed):
        value = safe_aggregate_value(payload.get(key))
        if value is not None:
            result[key] = value
    return result


def badge_markdown(
    label: str,
    value: str | None,
    color: str,
    style: str,
    logo: str | None = None,
    logo_color: str | None = None,
) -> str:
    alt = label if value is None else f"{label}: {value}"
    segments = [quote(label, safe=""), quote(value, safe="") if value is not None else ""]
    path = "-".join(segments).rstrip("-")
    query = f"style={quote(style, safe='')}"
    if logo:
        query += f"&logo={quote(logo, safe='')}"
    if logo_color:
        query += f"&logoColor={logo_color}"
    return f"![{alt}](https://img.shields.io/badge/{path}-{color}?{query})"


def render(config: dict[str, Any], aggregates: dict[str, str] | None = None) -> str:
    style = config["style"]
    lines = [START, '<div align="center">', ""]
    lines.extend(badge_markdown(
        badge["label"], None, badge["color"], style, badge.get("logo"), badge.get("logoColor"),
    ) for badge in config["static"])
    if aggregates:
        lines.append("")
        for badge in config["dynamic"]:
            if badge["key"] in aggregates:
                lines.append(badge_markdown(
                    badge["label"], aggregates[badge["key"]], badge["color"], style,
                ))
    lines.extend(["", "</div>", END])
    return "\n".join(lines)


def replace_owned_block(readme: str, block: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise BadgeConfigError("README must contain exactly one ordered profile badge marker pair")
    start = readme.index(START)
    end_start = readme.index(END)
    if end_start < start:
        raise BadgeConfigError("README must contain exactly one ordered profile badge marker pair")
    end = end_start + len(END)
    return readme[:start] + block + readme[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("profile-badges.json"))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--values-json", help="optional allowlisted dynamic badge values")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    aggregates = load_values(args.values_json, {badge["key"] for badge in config["dynamic"]})
    before = args.readme.read_text(encoding="utf-8")
    after = replace_owned_block(before, render(config, aggregates))
    if args.check:
        if before != after:
            print("README badge row is stale; run scripts/generate_profile_badges.py", file=sys.stderr)
            return 1
        return 0
    if before != after:
        args.readme.write_text(after, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
