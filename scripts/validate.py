#!/usr/bin/env python3
"""Offline Agent Skills spec preflight and repository reference validator."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "cbr-liquidity-intelligence"


def validate():
    failures = []
    skill_file = SKILL / "SKILL.md"
    if not skill_file.is_file():
        return ["SKILL.md not found in " + str(SKILL)]

    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        return ["SKILL.md missing valid YAML frontmatter"]

    front = parts[1]
    name = re.search(r"(?m)^name:\s*(.+?)\s*$", front)
    desc = re.search(r"(?m)^description:\s*(.+?)\s*$", front)

    if not name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name.group(1)):
        failures.append("Invalid skill name")
    elif name.group(1) != SKILL.name or len(name.group(1)) > 64:
        failures.append("name must match skill directory name and be <= 64 chars")

    if not desc or not 1 <= len(desc.group(1)) <= 1024:
        failures.append("description must be 1-1024 characters")

    # Check relative links inside SKILL.md
    for raw in re.findall(r"\]\(([^)]+)\)", content):
        if raw.startswith(("https://", "http://", "#")):
            continue
        path = (SKILL / raw.split("#", 1)[0]).resolve()
        if not path.is_relative_to(SKILL.resolve()) or not path.is_file():
            failures.append(f"Broken skill reference in SKILL.md: {raw}")

    # Check repository core files
    for req in ["README.md", "LICENSE", "AGENTS.md", "CHANGELOG.md"]:
        if not (ROOT / req).is_file():
            failures.append(f"Missing repository file: {req}")

    return failures


if __name__ == "__main__":
    errors = validate()
    if errors:
        print("\n".join("FAIL: " + e for e in errors), file=sys.stderr)
        sys.exit(1)
    print("PASS: offline structure, frontmatter and skill links valid")
