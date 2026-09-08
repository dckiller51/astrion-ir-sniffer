# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] 2026-09-08

### Fixed

- **Harmony bulk capture sent the wrong command to the hub, silently producing an empty `pronto` for any button whose display name doesn't match its real IR command.** `start_capture()` built each capture target from `cmd["name"]`/`cmd["label"]` and passed it straight to `send_harmony_cmd()` → `aioharmony`'s `send_command`. On Harmony device profiles where the real IR command differs from the function's display name — e.g. a button named `"Select"` whose actual command is `"OK"`, nested inside `cmd["action"]` as a stringified JSON — the hub silently ignored the command, the ESP32 never saw an IR burst, and `parse_pronto_capture()` returned an empty string; the affected command landed in the export with a blank `"pronto"` field and no error anywhere. New `_real_command()` extracts `action.command` when present, falling back to `cmd["name"]` otherwise; `cmd_label` (display only) is unaffected. Learning Mode (`/api/learn/*`) was never affected — it captures from a real remote pointed at the ESP32 and never talks to the Harmony hub.
  - If resuming from an `export_telecommandes_partial.json` produced before this fix: affected commands were saved under the old (wrong) key and won't match the new one on resume, so they'll simply get re-captured rather than staying silently blank. Delete the partial file first for a clean re-run if you'd rather not wait for that.

### Added

- `pyproject.toml` — `ruff` lint + format configuration.
- `requirements-dev.txt` — adds `ruff` and `pytest` on top of the runtime `requirements.txt`.
- `.github/workflows/ci.yml` — runs `ruff check`, `ruff format --check`, and `pytest` on every push/PR.
- `tests/test_app.py` — regression tests for `_real_command()` (locks in the fix above) and `parse_pronto_capture()`.

### Known issues

- **`parse_pronto_capture()` can strip a captured code's header when the code has no distinct repeat burst.** Its heuristic splits the raw log text on every literal `"0000"` token — intended to separate a "once" burst from a "repeat" burst — but a Pronto code's own repeat-length header field is `"0000"` whenever the code has *no* repeat burst, which is the shape of most captures currently in `ir-database/` (e.g. `"0000 006D 0027 0000 00AD..."`). Fed that shape directly, the function splits at that field and returns a `main` burst missing its type + carrier-frequency header (`006D`), which would not be a valid Pronto code. Reproduced with synthetic input matching real capture shapes (see the `xfail` test in `tests/test_app.py`); **not yet fixed**, because the exact raw text `esphome logs` produces (line prefixes, whether "once"/"repeat" arrive as one line or two, etc.) wasn't available to verify a fix against without risking silently corrupting future captures. The existing entries in `ir-database/` are unaffected by this (they already have intact headers), so whatever the real raw log shape is, it must avoid hitting this path in practice — worth confirming with a real `esphome logs` sample before touching this function.

## [0.1.0] - unreleased history not tracked before this changelog

Everything up to and including the Harmony bulk-export flow, Learning Mode, the visual form/JSON editor, and the online IR database selector (`docs/`) predates this changelog. Future entries start from here.
