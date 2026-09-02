#!/usr/bin/env bash
# weekly-backup.sh — Sync ~/lancebarker projects to ~/Documents (iCloud) for local backup
# Runs weekly via cron. Excludes build artifacts and large regeneratable files.
# Last updated: 2026-03-16

set -uo pipefail

EXCLUDES=(
  --exclude='node_modules/'
  --exclude='venv/'
  --exclude='.git/'
  --exclude='.DS_Store'
  --exclude='__pycache__/'
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

FAILED_SYNCS=()

run_rsync() {
  local src="$1" dst="$2"
  local extra=()
  [[ $# -gt 2 ]] && extra=("${@:3}")

  if rsync -av --delete "${EXCLUDES[@]}" "${extra[@]+"${extra[@]}"}" "$src" "$dst"; then
    log "OK: $src → $dst"
    return 0
  fi

  log "WARN: rsync failed for $src — retrying in 10s..."
  sleep 10

  if rsync -av --delete "${EXCLUDES[@]}" "${extra[@]+"${extra[@]}"}" "$src" "$dst"; then
    log "RETRIED-OK: $src → $dst"
    return 0
  fi

  log "ERROR: $src → $dst (check Full Disk Access: System Settings → Privacy & Security)"
  FAILED_SYNCS+=("$src")
}

log "Starting weekly backup..."

run_rsync ~/AIPianoTeacher/       ~/Documents/Projects/code/AIPianoTeacher_backup/
run_rsync ~/memTrain/             ~/Documents/Projects/code/memTrain_backup/
run_rsync ~/PushbackJack/         ~/Documents/Projects/code/PushbackJack_backup/
run_rsync ~/lancefb.github.io/    ~/Documents/lancefb.github.io_backup/
run_rsync ~/howtobebetter.ai/     ~/Documents/howtobebetter.ai_backup/
run_rsync ~/Generative/           ~/Documents/Generative_backup/
run_rsync ~/PAI/                  ~/Documents/PAI_backup/
run_rsync ~/DCLTutor/		  ~/Documents/DCLTutor_backup/
run_rsync ~/MSTROptions/          ~/Documents/MSTROptions_backup/
run_rsync ~/ed-story/             ~/Documents/ed-story_backup/
run_rsync ~/self-evident-play/    ~/Documents/self-evident-play_backup/
run_rsync ~/.claude/              ~/Documents/claude_backup/         --exclude='projects/'

log "--- Backup Summary ---"
if [[ ${#FAILED_SYNCS[@]} -gt 0 ]]; then
  log "FAILED (${#FAILED_SYNCS[@]} destination(s)):"
  for f in "${FAILED_SYNCS[@]}"; do
    log "  ✗ $f"
  done
  osascript -e "display notification \"${FAILED_SYNCS[*]}\" with title \"Weekly Backup Failed\" subtitle \"${#FAILED_SYNCS[@]} destination(s) failed after retry\" sound name \"Basso\""
  exit 1
else
  log "All destinations backed up successfully."
fi
