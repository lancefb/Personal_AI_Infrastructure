# Plan: PAI v5.0.0 Full Install + Custom Content Re-Integration

## Context

PAI v5.0.0 ("Life Operating System") was officially tagged on `danielmiessler/PAI` upstream. This is not a patch — it is an architectural shift from scaffolding to a full Life OS with a named DA, the Pulse daemon (replaces voice server), a Life Dashboard at port 31337, Algorithm v6.3.0, and 45 skills. Lance has been waiting for this tag before migrating (per memory: `project_pai_upgrade_v5.md`). Current install is v4.0.2 at `~/.claude/`. Lance has ~30 custom skills (PBJ, EdPlays, Art, etc.) and USER/ content (TELOS, PROJECTS, BUSINESS) that must survive the upgrade.

**Trigger:** v5.0.0 tag confirmed on upstream, Lance approved "full install" approach.

---

## Migration Steps

### Phase 1 — Extract v5.0.0 to temp (safe, read-only)

Extract the release from git (already fetched in this session) to `/tmp/pai-v5-claude/`:

```bash
mkdir -p /tmp/pai-v5-claude
git -C ~/PAI archive upstream/main "Releases/v5.0.0/.claude/" | tar -x --strip-components=3 -C /tmp/pai-v5-claude
ls /tmp/pai-v5-claude/CLAUDE.md  # verify: should show file
```

### Phase 2 — Backup ~/.claude/ (critical gate)

```bash
cp -R ~/.claude ~/.claude.backup-20260526
ls ~/.claude.backup-20260526/ | wc -l  # verify: >200 files
```

**Do not proceed if backup count <200.**

### Phase 3 — Install v5.0.0 base

Copy v5.0.0 over ~/.claude/ **excluding** `projects/` (auto-memory) and `MEMORY/` (top-level MEMORY/ is not in v5.0.0 bundle — it lives at `~/.claude/MEMORY/` in current setup, v5.0.0 adds new dirs at `~/.claude/PAI/MEMORY/`):

```bash
rsync -av --delete \
  --exclude='projects/' \
  --exclude='MEMORY/' \
  /tmp/pai-v5-claude/ ~/.claude/
```

Verify:
```bash
grep "PAI 5.0.0" ~/.claude/CLAUDE.md  # must match
ls ~/.claude/PAI/PULSE/pulse-unified.ts  # must exist
```

### Phase 4 — Write DA identity files

Create `~/.claude/PAI/USER/DA_IDENTITY.md`:
```markdown
# DA Identity

- **Name:** budd
- **Role:** Lance's Personal Digital Assistant
- **Voice ID:** fTtv3eikoepIosk8dTZ5
- **Personality:** Direct, curious, warm. Thinks clearly. Loves good work.
```

Create `~/.claude/PAI/USER/PRINCIPAL_IDENTITY.md`:
```markdown
# Principal Identity

- **Name:** Lance Barker
- **Location:** Quincy, IL
- **Time Zone:** America/Chicago
```

Substitute `{{SECONDARY_VOICE_ID}}` in CLAUDE.md:
```bash
sed -i '' 's/{{SECONDARY_VOICE_ID}}/fTtv3eikoepIosk8dTZ5/g' ~/.claude/CLAUDE.md
```

Remove unresolved template placeholders from doc comments (cosmetic only — `{DA_IDENTITY.NAME}` and `{PRINCIPAL.NAME}` in comment lines, not in executable curl/code, are fine as-is since they're in `@file`-included context).

Create empty PRINCIPAL_TELOS.md so the `@PAI/USER/TELOS/PRINCIPAL_TELOS.md` include in CLAUDE.md doesn't fail:
```bash
touch ~/.claude/PAI/USER/TELOS/PRINCIPAL_TELOS.md
```

### Phase 5 — Re-integrate custom skills

These 23 skills are unique to Lance's install (not in v5.0.0) — copy from backup:

```bash
for skill in BlogPost ContentAnalysis CORE Dashboard EdAudio EdPlays EdStory \
  excalidraw-diagram Investigation Media notebooklm PBJ PDF Scraping \
  screenwriter Security Thinking Tlddr Utilities WastewaterCA Wisdom Wrap YouTube; do
  cp -R ~/.claude.backup-20260526/skills/$skill ~/.claude/skills/
done
```

For overlapping skills (Art, Telos, Research, Agents, CreateSkill, USMetrics) — v5.0.0 versions are used (they are newer). Lance's backup versions are preserved in `.backup-20260526/` if rollback needed.

**Special case — Art skill:** `~/PAI/Packs/pai-art-skill/src/skills/Art/Tools/Generate.ts` has uncommitted mods. After migration, verify `~/.claude/skills/Art/` is the v5.0.0 version, then evaluate if the Packs modification needs to be ported.

### Phase 6 — Restore USER/ content

Lance's USER/ directories contain real content; copy them back over the v5.0.0 template scaffolding:

```bash
for dir in ACTIONS BUSINESS FLOWS PIPELINES PROJECTS SKILLCUSTOMIZATIONS \
  STATUSLINE TELOS TERMINAL WORK Workflows; do
  [ -d ~/.claude.backup-20260526/PAI/USER/$dir ] && \
    cp -R ~/.claude.backup-20260526/PAI/USER/$dir ~/.claude/PAI/USER/
done
# Copy personal files
for f in AISTEERINGRULES.md OPINIONS.md ABOUTME.md; do
  [ -f ~/.claude.backup-20260526/PAI/USER/$f ] && \
    cp ~/.claude.backup-20260526/PAI/USER/$f ~/.claude/PAI/USER/
done
```

### Phase 7 — Restore custom TOOLS/

`~/.claude/MEMORY/` is preserved in-place (excluded from rsync). No restore needed.

Restore custom PAI Tools that may not exist in v5.0.0 (Inference.ts, PAILogo.ts, etc.):
```bash
# Restore only tools that DON'T exist in v5.0.0 (preserve newer upstream tools)
rsync -av --ignore-existing \
  ~/.claude.backup-20260526/PAI/Tools/ \
  ~/.claude/PAI/Tools/
```

### Phase 8 — Merge settings.json

v5.0.0 ships a baseline settings.json. Merge Lance's env vars and permissions on top:

Key env vars to ensure are present: `PAI_DIR`, `PROJECTS_DIR`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`, `BASH_DEFAULT_TIMEOUT_MS`, `PAI_CONFIG_DIR`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, `DA`, `TIME_ZONE`, `PAI_SOURCE_APP`.

Key custom hooks to keep registered (beyond v5.0.0 defaults): `RatingCapture.hook.ts`, `PRDSync.hook.ts`, `SkillGuard.hook.ts`, `SessionAutoName.hook.ts`.

Read both settings.json files, write merged version. Use Python/jq for the merge.

### Phase 9 — Port 8888 → 31337 in custom skills

166 references to `:8888` exist in skills. Update them:

```bash
grep -rl "8888" ~/.claude/skills/ | xargs sed -i '' 's|localhost:8888|localhost:31337|g'
grep -rl "8888" ~/.claude/PAI/Algorithm/ | xargs sed -i '' 's|localhost:8888|localhost:31337|g'
```

### Phase 10 — Rebuild skill index

```bash
bun ~/.claude/PAI/Tools/GenerateSkillIndex.ts
jq 'length' ~/.claude/skills/skill-index.json  # verify: ≥30
```

### Phase 11 — Stop voice server, start Pulse

```bash
# Stop old voice server
launchctl unload ~/Library/LaunchAgents/com.pai.voiceserver.plist

# Run Pulse setup wizard (interactive — Lance runs this himself)
# It reads DA_IDENTITY.md, creates PULSE.toml, installs com.pai.pulse launchd plist
bun ~/.claude/PAI/PULSE/setup.ts
```

**Note:** Pulse setup.ts is interactive and reads ElevenLabs key from `~/.env`. Lance runs this as a `!` command. After it completes:
```bash
curl http://localhost:31337/health     # must return 200
curl -X POST http://localhost:31337/notify \
  -H "Content-Type: application/json" \
  -d '{"message": "Pulse live", "voice_id": "fTtv3eikoepIosk8dTZ5", "voice_enabled": true}'
```

### Phase 12 — Sync fork to upstream

```bash
git -C ~/PAI merge upstream/main
git -C ~/PAI push origin main
```

---

## Files Modified

- `~/.claude/` — replaced with v5.0.0 base (entire directory)
- `~/.claude/PAI/USER/DA_IDENTITY.md` — written (new)
- `~/.claude/PAI/USER/PRINCIPAL_IDENTITY.md` — written (new)
- `~/.claude/PAI/USER/TELOS/PRINCIPAL_TELOS.md` — touched (empty placeholder)
- `~/.claude/CLAUDE.md` — `{{SECONDARY_VOICE_ID}}` substituted
- `~/.claude/skills/` — 23 custom skills re-added; overlapping skills from v5.0.0
- `~/.claude/skills/skill-index.json` — rebuilt
- `~/.claude/settings.json` — env vars + custom hooks merged in
- `~/Library/LaunchAgents/com.pai.voiceserver.plist` — unloaded (replaced by Pulse)
- `~/Library/LaunchAgents/com.pai.pulse.plist` — installed by Pulse setup.ts

## Not Modified

- `~/.claude/projects/` — auto-memory, never touched
- `~/PAI/` repo — fork merge is last step

---

## Verification

```bash
grep "PAI 5.0.0" ~/.claude/CLAUDE.md                             # v5.0.0 installed
ls ~/.claude/PAI/PULSE/pulse-unified.ts                           # Pulse present
grep "budd" ~/.claude/PAI/USER/DA_IDENTITY.md                    # DA identity written
curl http://localhost:31337/health                                # Pulse running
grep -c "" ~/.claude/skills/PBJ/SKILL.md                         # PBJ skill intact
grep -c "" ~/.claude/skills/EdPlays/SKILL.md                     # EdPlays intact
jq 'length' ~/.claude/skills/skill-index.json                    # ≥30 skills indexed
! grep -r "localhost:8888" ~/.claude/skills/                     # no old port refs
jq '.env.DA' ~/.claude/settings.json                             # "budd"
ls ~/.claude/projects/                                            # auto-memory intact
```

---

## Rollback

Full rollback if anything breaks:
```bash
rm -rf ~/.claude
cp -R ~/.claude.backup-20260526 ~/.claude
launchctl load ~/Library/LaunchAgents/com.pai.voiceserver.plist
```
