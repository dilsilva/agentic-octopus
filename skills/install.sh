#!/usr/bin/env bash
# Install skill templates into a Claude Code skills directory.
#
# Usage:
#   ./install.sh --user [--force] [skill ...]
#   ./install.sh --project <repo-path> [--force] [skill ...]
#
# With no skill names, installs all of them.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST=""
FORCE=0
SKILLS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      DEST="$HOME/.claude/skills"
      shift
      ;;
    --project)
      [[ $# -ge 2 ]] || { echo "error: --project needs a repo path" >&2; exit 1; }
      DEST="$2/.claude/skills"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "error: unknown flag $1" >&2
      exit 1
      ;;
    *)
      SKILLS+=("$1")
      shift
      ;;
  esac
done

[[ -n "$DEST" ]] || { echo "error: pass --user or --project <repo-path>" >&2; exit 1; }

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  for d in "$SRC_DIR"/*/; do
    [[ -f "$d/SKILL.md" ]] && SKILLS+=("$(basename "$d")")
  done
fi

mkdir -p "$DEST"
installed=0 skipped=0

for s in "${SKILLS[@]}"; do
  src="$SRC_DIR/$s"
  if [[ ! -f "$src/SKILL.md" ]]; then
    echo "skip: no such skill '$s'" >&2
    continue
  fi
  if [[ -e "$DEST/$s" && $FORCE -eq 0 ]]; then
    echo "skip: $DEST/$s exists (use --force to overwrite)"
    ((skipped++)) || true
    continue
  fi
  rm -rf "$DEST/$s"
  cp -R "$src" "$DEST/$s"
  echo "installed: $s -> $DEST/$s"
  ((installed++)) || true
done

echo "done: $installed installed, $skipped skipped."
