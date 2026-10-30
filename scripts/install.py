#!/usr/bin/env python3
"""Zero-dependency local installer for CBR Liquidity Intelligence across various coding agents."""
import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "cbr-liquidity-intelligence"

PROJECT_PATHS = {
    "universal": ".agents/skills",
    "claude-code": ".claude/skills",
    "codex": ".agents/skills",
    "cursor": ".agents/skills",
    "github-copilot": ".agents/skills",
    "gemini-cli": ".agents/skills",
    "opencode": ".opencode/skills",
    "cline": ".agents/skills",
    "windsurf": ".agents/skills",
    "continue": ".continue/skills",
    "goose": ".goose/skills",
    "roocode": ".roo/skills",
    "antigravity": ".agents/skills",
}

GLOBAL_PATHS = {
    "universal": ".agents/skills",
    "claude-code": ".claude/skills",
    "codex": ".agents/skills",
    "cursor": ".cursor/skills",
    "github-copilot": ".copilot/skills",
    "gemini-cli": ".gemini/skills",
    "opencode": ".config/opencode/skills",
    "cline": ".agents/skills",
    "windsurf": ".agents/skills",
    "continue": ".continue/skills",
    "goose": ".config/goose/skills",
    "roocode": ".roo/skills",
    "antigravity": ".gemini/antigravity/skills",
}


def install(target, agents, global_scope=False, force=False, dry_run=False):
    mapping = GLOBAL_PATHS if global_scope else PROJECT_PATHS
    folders = sorted({(target / mapping[a] / "cbr-liquidity-intelligence").resolve() for a in agents})
    operations = []
    source_status = []
    for dest in folders:
        if dest == SOURCE.resolve():
            source_status.append((str(dest), "source-present"))
            continue
        if dest.exists() and not force:
            raise FileExistsError(f"{dest} already exists; pass --force to replace")
        operations.append(dest)
    if dry_run:
        return source_status + [(str(dest), "dry-run") for dest in operations]
    for dest in operations:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SOURCE, dest)
    return [(str(dest), "installed") for dest in operations]


def main():
    parser = argparse.ArgumentParser(description="Install cbr-liquidity-intelligence agent skill.")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Target project path")
    parser.add_argument("--global", dest="global_scope", action="store_true", help="Install into global user config")
    parser.add_argument("--all", action="store_true", help="Install across all known agents")
    parser.add_argument("-a", "--agent", action="append", choices=list(PROJECT_PATHS.keys()), help="Target agent")
    parser.add_argument("--force", action="store_true", help="Overwrite existing install")
    parser.add_argument("--dry-run", action="store_true", help="Preview operations")
    args = parser.parse_args()

    agents = list(PROJECT_PATHS.keys()) if args.all or not args.agent else args.agent
    target = Path.home() if args.global_scope else args.project

    try:
        results = install(target, agents, args.global_scope, args.force, args.dry_run)
        for dest, status in results:
            print(f"[{status}] {dest}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
