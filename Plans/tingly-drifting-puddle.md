# Lead Trainer & Harmony Trainer

## Context

AIPianoTeacher currently has four practice tabs (Note, Interval, Song, Ear Trainer), all built on rule-based/procedural note generation — no LLM or backend anywhere in the app. The user wants two new tabs that teach improvisation-adjacent skills over a chord progression:

1. **Lead Trainer** — practice playing melodic lead lines over a looping chord progression in a given style, first by learning a generated lick, then by free-playing with a live "safe notes" guide.
2. **Harmony Trainer** — practice playing a second, harmonizing melodic voice against the same kind of progression.

Both features stay procedural (chord-tone/scale-tone constrained generation), matching the existing `src/flows/` convention — no API key, no backend, consistent with how the rest of the app works. Confirmed with the user: Phase A of Lead Trainer pauses the backing loop at each chord until the user finishes echoing (untimed, forgiving), rather than running on strict tempo.

**Revision after initial build kickoff** — the user requested two changes before the build got underway, both incorporated below:
1. Target phrases (Lead Trainer's lick, Harmony Trainer's harmony line) are shown via **virtual keyboard highlighting**, not staff notation. This removes `phrase-staff-display.tsx` and the VexFlow multi-note rendering risk entirely.
2. The backing track needs a **live tempo/speed control** (slider), matching Song Trainer's existing BPM pattern but adjustable while the loop is playing, not just when stopped.

## New shared music-theory model — `src/lib/music-theory.ts`

Currently only exports `ALL_NOTES`/`Note`. Add:
- `ChordQuality = 'major' | 'minor' | 'dominant7' | 'major7' | 'minor7' | 'diminished'`
- `CHORD_QUALITY_INTERVALS: Record<ChordQuality, number[]>` (semitone offsets, e.g. `dominant7: [0,4,7,10]`)
- `ScaleType = 'ionian' | 'aeolian' | 'dorian' | 'mixolydian' | 'majorPentatonic' | 'minorPentatonic' | 'blues'`
- `SCALE_TYPE_INTERVALS: Record<ScaleType, number[]>`
- `DEFAULT_SCALE_FOR_QUALITY: Record<ChordQuality, ScaleType>` (e.g. `dominant7 → mixolydian`, `minor7 → dorian`)
- `ChordSpec { root: Note; quality: ChordQuality; durationBeats: number; scaleType?: ScaleType }`
- `ChordProgression { id: string; name: string; style: string; beatsPerBar: number; chords: ChordSpec[] }`
- `getChordTones(root, quality, octave): string[]`, `getScaleTones(root, quality, octaveLow, octaveHigh, scaleTypeOverride?): string[]`, `isChordTone(midi, root, quality): boolean`, `isScaleTone(...): boolean`

Also lift `KEY_ROOT_SEMITONE` and `midiToNoteName` (currently private to `src/flows/generate-melody-flow.ts`) into `music-theory.ts` as canonical exports; have `generate-melody-flow.ts` re-export them so Ear Trainer's existing import path is untouched.

New file `src/lib/chord-progression-presets.ts`: `CHORD_PROGRESSION_PRESETS: ChordProgression[]` with 4 presets — 12-bar blues in C (dominant7, blues-scale override), ii-V-I jazz in F (minor7/dominant7/major7), pop I-V-vi-IV in G (major/major/minor/major), minor blues in A (minor7, blues override) — plus `getPresetById(id)`.

## New flow files — `src/flows/`

`generate-lead-phrase-flow.ts`: `generateLeadPhrase({ chord, notesPerChord?, octave?, previousPhrase? })` — weighted random pick, mostly chord tones with occasional scale-tone passing notes, last note forced to a chord tone. `generateLeadProgressionPhrases(progression, previousPhrases?)` maps this across all chords — one phrase per chord, generated once per progression load (not regenerated every loop pass, so the user can repeat-practice the same lick). Reused by both trainers (Lead Trainer's target, Harmony Trainer's reference lead).

`generate-harmony-flow.ts`: `generateHarmonyLine({ leadNotes, chords, intervalType?: 'third'|'sixth', direction?: 'above'|'below' })` — steps ±2/±5 scale-degree positions within `getScaleTones(...)` per chord, so harmonization stays diatonic per-chord.

Both follow the existing convention: plain input/output interfaces, pure sync logic, optional `async` keyword for future-proofing.

## Shared hooks/utils

- **`src/hooks/use-midi-input.ts` — new.** `useMidiInput(selectedMidiInput, { onNoteOn?, onNoteOff? })` extracts the WebMidi wiring currently duplicated in `note-trainer.tsx`, `ear-trainer.tsx`, and `song-trainer/practice-keyboard.tsx`. Only the two new trainers use it — leave the 3 existing call sites untouched (zero regression risk to working trainers).
- **`src/lib/echo-grading.ts` — new.** `compareNoteSequences(target: string[], played: string[]): { correct: boolean; perNote: boolean[] }` (the `Tone.Frequency(...).toMidi()` equality check, currently duplicated twice inline in `ear-trainer.tsx`) plus a generic `PracticeStats { totalAttempts, correctAttempts, currentStreak, bestStreak }` and `recordAttempt(stats, correct)`. Lead/Harmony Trainer each keep their own local FSM but call into this shared pure comparison — doesn't touch ear-trainer's working internals.
- **`src/components/shared/progression-select.tsx` — new.** A `Select` over `CHORD_PROGRESSION_PRESETS`, since both new trainers need identical "pick a progression" UI immediately.

## Extended shared components

- **No new staff component.** Phrase display for both trainers is keyboard-only (see below) — `staff-display.tsx` is untouched and unused by these features.
- **`src/components/shared/piano-keyboard.tsx` — additive props only.** Add `chordToneNotes?: string[]` and `scaleToneNotes?: string[]` with new colors (amber / sky) in `isHighlighted()`, `renderBlackKeys()`, and the white-key map. Precedence: `correct > incorrect > chordTone > scaleTone > highlighted`. Existing 4 consumers pass none of these — unaffected. These same two props double as the phrase-highlighting mechanism: the *current* target note in a phrase is fed through `highlightedNotes` (or a dedicated `targetNote` if clearer), with `correctNote`/`incorrectNote` firing per-note exactly as `ear-trainer.tsx` already does for its echo-back grading — no new keyboard states needed beyond what's there.

## Looping backing-track playback — `src/hooks/use-progression-playback.ts` (new)

```
useProgressionPlayback({ progression, onChordChange?, bpm }):
  { isPlaying, start(), stop(), currentChordIndex }
```

Reuses the app-wide `Tone.getTransport()` singleton and the existing `transport.schedule(callback, timeInSeconds)` idiom (no `Tone.Part`/`Tone.Sequence` precedent in this repo). Computes total duration from `chords[].durationBeats` + `bpm`, sets `transport.loop = true`, `loopStart = 0`, `loopEnd = totalSeconds`. Chord voicings play via `sampler.triggerAttackRelease(chordTones, durationSeconds, time)`.

**Live tempo control**: `bpm` is a live value, not just an initial one — the hook's internal effect watches `bpm` and assigns `transport.bpm.value = bpm` whenever it changes, including while the loop is playing (Tone.js applies this immediately, no restart needed). Note this differs from Song Trainer's tempo slider, which disables while `practiceMode !== 'inactive'` (`song-trainer.tsx:385`) — for Lead/Harmony Trainer the slider stays enabled during playback since adjusting backing-track speed live is the point. UI: same `<input type="range">` pattern as `song-trainer.tsx:377-388` (`Label` + range input + `{bpm} BPM` readout), min/max matching Song Trainer's `30`-`130`, styled identically (`accent-[hsl(var(--primary))]`), but without the `disabled` binding. Because `transport.loopEnd` is duration-in-seconds and depends on `bpm`, a live bpm change also needs to recompute and reassign `loopEnd` so the loop point stays musically correct rather than drifting.

**Phase A pause-at-chord behavior** (per user's confirmed choice): the hook exposes a `holdAtCurrentChord()` / `advance()` pair instead of pure fire-and-forget looping — Lead Trainer's Phase A calls `holdAtCurrentChord()` in `onChordChange` and only calls `advance()` once `echo-grading` reports the phrase complete (correct or given-up), so the backing chord sustains untimed while the user echoes. Free-play (Phase B) and Harmony Trainer just let it run continuously without holding.

**Critical cleanup**: `stop()`/unmount must explicitly reset `transport.loop = false` and call `transport.cancel()` — `song-trainer.tsx`'s current cleanup never resets `loop` because nothing needed to before. Without this, switching Lead Trainer → Song Trainer would make song playback loop unexpectedly. Verify manually: play a song, switch to Lead Trainer, switch back, replay the song.

## New top-level trainers

**`src/components/lead-trainer/lead-trainer.tsx`** (single-file, mirrors `ear-trainer.tsx`'s style):
- `LeadPhase = 'learnLick' | 'freePlay'`, local `PracticeState = 'idle'|'playing'|'listening'|'revealed'`.
- Progression picked via `progression-select.tsx`; phrases generated once via `generateLeadProgressionPhrases`. A tempo slider (per above) controls `bpm`, passed into `useProgressionPlayback`.
- **Phase A**: `useProgressionPlayback` holds at each chord; the chord's phrase is played note-by-note against the keyboard: current target note fed into `PianoKeyboard`'s `highlightedNotes`, user's MIDI input compared via `echo-grading`'s `compareNoteSequences`, correct/incorrect fed into `correctNote`/`incorrectNote` for that instant (same visual mechanic `ear-trainer.tsx` already uses), advancing through the phrase array note-by-note; loop advances to the next chord once the full phrase is graded. MIDI via `useMidiInput`, with ref-mirroring for closures (same pattern as `ear-trainer.tsx`'s `userNotesRef`/`melodyRef`).
- **Phase B**: no phrase/grading; derives `chordToneNotes`/`scaleToneNotes` from the live chord via `getChordTones`/`getScaleTones`, feeds the extended `PianoKeyboard`, loop runs continuously, tempo slider still live.

**`src/components/harmony-trainer/harmony-trainer.tsx`**: reuses progression select, `generateLeadProgressionPhrases` (reference lead), `generateHarmonyLine`, `use-progression-playback` (continuous, backing chords + audible lead, same live tempo slider), `useMidiInput`, `echo-grading`. Harmony target notes are highlighted on the keyboard the same note-by-note way as Lead Trainer Phase A — no staff involved. No free-play phase. Built by copy-adapting Lead Trainer Phase A's echo/grading wiring rather than forcing a shared abstraction before two real consumers exist.

## App.tsx wiring

- `TabsList` className: `grid-cols-4` → `grid-cols-6`.
- New imports: `LeadTrainer`, `HarmonyTrainer`; icons `Guitar` and `Layers2` from `lucide-react` (confirmed available).
- New `TabsTrigger`/`TabsContent` pairs following the `NoteTrainer`/`SongTrainer`/`EarTrainer` pattern (MIDI-gated: `midiStatus === 'enabled' ? <LeadTrainer selectedMidiInput={selectedMidiInput} /> : renderMidiConnect()`).

## Build order

0. App.tsx stub wiring (grid-cols-6, both tabs → empty placeholders) — verify live in the running app from here on.
1. `music-theory.ts` additions + `chord-progression-presets.ts` (4 presets) — sanity-check standalone.
2. `generate-lead-phrase-flow.ts`, `generate-harmony-flow.ts` — sanity-check output standalone.
3. Extend `piano-keyboard.tsx` (chordToneNotes/scaleToneNotes props) + minimal LeadTrainer highlighting one static phrase note-by-node on the keyboard, no playback/MIDI yet.
4. `use-progression-playback.ts` — chords-only looping with hold/advance and live-tempo-slider support, verify no drift/leak, current-chord label, bpm changes take effect immediately without breaking the loop point.
5. `useMidiInput` + `echo-grading.ts` — full Lead Trainer Phase A loop with stats.
6. Wire Phase B free-play highlighting (chord/scale tone colors while the loop runs continuously).
7. Harmony Trainer — should be the fastest milestone, reusing steps 1-6.
8. Final App.tsx polish, remove stubs.

## Riskiest points to watch

1. **Transport hold/advance plus live tempo changes is new territory** — nothing in this codebase pauses the Transport mid-loop or re-tempos a running loop today. `loopEnd` is duration-in-seconds and depends on `bpm`; a live bpm change must recompute and reassign it or the loop point drifts. Build and verify this in isolation (milestone 4) before layering MIDI grading on top.
2. **Shared `Tone.getTransport()` singleton** — must not leak `loop = true` (or a leftover altered `bpm`) into `SongTrainer`. Manually verify song playback still behaves correctly, at its own tempo, after visiting Lead/Harmony Trainer.

## Verification

- Run `bun run dev`, open both new tabs, and for each milestone drive it live (per the `run` skill's "drive it, don't just launch it" standard): pick each of the 4 presets, complete a full Phase A echo loop with a MIDI keyboard (or the on-screen keyboard as a fallback), confirm Phase B highlighting changes as chords advance, complete a Harmony Trainer round.
- Explicitly re-test Song Trainer end-to-end after these changes exist, per risk #3.
- `bun run lint` and `tsc -b` (via `bun run build`) should stay clean throughout.

## Execution note

This is an E3 coding task — per operating rules, Forge (GPT-5.4) should be included in EXECUTE alongside Claude-family work.
