#!/usr/bin/env python3
"""Deterministically regenerate the owned GitHub profile badge row."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA = "yurei-so/profile-badges/v1"
ROOST_SCHEMA = "runtime-roost/public-profile-aggregates/v1"
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
    for group in (config.get("static"), config.get("roost", {}).get("aggregates")):
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
    keys = [badge.get("key") for badge in config["roost"]["aggregates"]]
    if any(not isinstance(key, str) or not KEY.fullmatch(key) for key in keys):
        raise BadgeConfigError("Roost aggregate keys must be bounded snake_case identifiers")
    if len(keys) != len(set(keys)):
        raise BadgeConfigError("Roost aggregate keys must be unique")
    return config


def safe_aggregate_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value) if abs(value) <= 999_999_999 else None
    if isinstance(value, str) and 0 < len(value) <= 40 and re.fullmatch(r"[A-Za-z0-9 ._+:/-]+", value):
        return value
    return None


def fetch_roost(url: str, token: str, allowed: set[str], timeout: float = 5.0) -> dict[str, str]:
    if not url.startswith("https://"):
        raise BadgeConfigError("Roost profile stats URL must use HTTPS")
    request = Request(url, headers={
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "user-agent": "yurei-so-profile-badges/1",
    })
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("Roost profile stats returned a non-success status")
        body = response.read(65_537)
    if len(body) > 65_536:
        raise RuntimeError("Roost profile stats response exceeded 65536 bytes")
    payload = json.loads(body)
    if not isinstance(payload, dict) or payload.get("schema") != ROOST_SCHEMA:
        raise RuntimeError("Roost profile stats returned an unsupported schema")
    aggregates = payload.get("aggregates")
    if not isinstance(aggregates, dict):
        raise RuntimeError("Roost profile stats omitted aggregates")
    result: dict[str, str] = {}
    for key in sorted(allowed):
        value = safe_aggregate_value(aggregates.get(key))
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
        for badge in config["roost"]["aggregates"]:
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
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    aggregates: dict[str, str] = {}
    enabled = os.getenv("ROOST_PROFILE_STATS_ENABLED", "").lower() in {"1", "true", "yes"}
    url = os.getenv("ROOST_PROFILE_STATS_URL", "")
    token = os.getenv("ROOST_PROFILE_STATS_TOKEN", "")
    if enabled and url and token:
        try:
            aggregates = fetch_roost(
                url, token, {badge["key"] for badge in config["roost"]["aggregates"]},
            )
        except (BadgeConfigError, HTTPError, URLError, OSError, RuntimeError, json.JSONDecodeError):
            print("warning: Roost profile stats unavailable; using static badges", file=sys.stderr)
    elif enabled:
        print("warning: Roost profile stats are enabled but not configured; using static badges", file=sys.stderr)
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
