# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.1] 2026-10-09

### Fixed

- Inputs defined as a device *state* (e.g. LG TVs: input "HDMI 2" = set `Screen` to `HDMI2`) are expanded through the archive's `states` block into their key sequence (`InputHdmi2`); they used to be dropped, leaving such devices with no inputs.
- An imported device **replaces** an entry with the same brand+model in the category instead of being added as "<model> (Harmony)" — dashboards reference devices by brand+model, so the renamed copy broke every reference. Imports stored with that suffix in the browser are renamed on load.

### Added

- Converter test for state-based inputs (`tests/test_harmony_import.mjs`).

## [0.5.0] 2026-10-08

### Added

- **Online selector: "Import from Harmony…"** — search any of the ~276,000 devices of the Logitech Harmony IR archive (read live from the [dckiller51/logitech-harmony-ir-archive](https://github.com/dckiller51/logitech-harmony-ir-archive) fork through `raw.githubusercontent.com`, nothing bundled here), preview it (power type, power-on delay, repeats, inputs, data warnings), pick an Astrion category and add it to the selection. It then exports like any other model. Imports are kept in the browser (`localStorage`) and shown with a "Harmony" badge.
- **`profile` block** on imported model entries (`docs/harmony-import.js`): `power` (`discrete`/`toggle`/`none` with on/off/toggle key sequences), `timing` (`power_on_delay_ms`, `inter_key_delay_ms`, `inter_device_delay_ms`, `input_delay_ms`, `repeats`) and named `inputs` with their key sequences. Commands keep the Harmony names (`PowerOn`, `InputHdmi1`…) and carry `pronto_repeat` when the archive has a separate repeat burst. Astrion 1.2.2-beta+ uses the profile to run Activities the way Harmony did; older versions just ignore it.
- `tests/test_harmony_import.mjs` — converter tests (`node --test tests/test_harmony_import.mjs`).
- `test_database_pronto_codes_have_an_intact_header` — fails CI if a code with a broken header lands in `ir-database/` again; regression tests for the capture parser (frame + repeat in either order, log prefixes and line breaks, noise tokens).

### Fixed

- **Captured Pronto codes lost their header — 334 of the 489 commands in `ir-database/` were unusable.** `parse_pronto_capture()` (and its browser twin `cleanEsphomePronto()` in `templates/index.html`) split the captured text on every literal `0000` token to separate a "once" burst from a "repeat" burst. But `0000` is also a code's own repeat-length header field whenever it has no repeat section — the usual case — so the split happened *inside* the code: `pronto` became the header-less rest (`0000 015A 00AE …`, read as a ~12 kHz carrier with a wrong length) and `pronto_repeat` the cut-off header (`0000 006D 0022`). Both now walk the tokens using each code's own header lengths (`split_pronto_sequences()`), and the longest code is kept as `pronto`, the next one as `pronto_repeat`, whatever their order in the log. The previous "Known issues" note claiming existing entries were unaffected was wrong.
- **`ir-database/` repaired:** the 334 affected commands (Denon AVR-X3300W, LG UBK90, LG HU710PW-GL, Philips 55OLED805, Samsung TQ55LS03FAUXXC) are rejoined into their original code, `pronto_repeat` emptied. Regenerate and copy these categories (audio, player, tv) to the remote. Astrion 1.2.2-beta also repairs this shape on its own when reading older files.
- Three Xbox One X commands (`clear`, `last_channel`, `power_off`) have a correct header but one word missing from the capture — they need to be captured again.

## [0.4.0] 2026-09-23

### Added

- **TV**: Added **Philips 70PUS7805/12** model.

## [0.3.0] 2026-09-11

### Added

- **Player**: Added **LG UBK90** model (contributed by [@neturmel](https://github.com/neturmel)).
- **TV**: Added **Philips 55OLED805** model (contributed by [@neturmel](https://github.com/neturmel)).

## [0.2.0] 2026-09-08

### Fixed

- **Harmony bulk capture sent the wrong command to the hub, silently producing an empty `pronto` for any button whose display name doesn't match its real IR command.** `start_capture()` built each capture target from `cmd["name"]`/`cmd["label"]` and passed it straight to `send_harmony_cmd()` → `aioharmony`'s `send_command`. On Harmony device profiles where the real IR command differs from the function's display name — e.g. a button named `"Select"` whose actual command is `"OK"`, nested inside `cmd["action"]` as a stringified JSON — the hub silently ignored the command, the ESP32 never saw an IR burst, and `parse_pronto_capture()` returned an empty string; the affected command landed in the export with a blank `"pronto"` field and no error anywhere. New `_real_command()` extracts `action.command` when present, falling back to `cmd["name"]` otherwise; `cmd_label` (display only) is unaffected. Learning Mode (`/api/learn/*`) was never affected — it captures from a real remote pointed at the ESP32 and never talks to the Harmony hub.
  - If resuming from an `export_telecommandes_partial.json` produced before this fix: affected commands were saved under the old (wrong) key and won't match the new one on resume, so they'll simply get re-captured rather than staying silently blank. Delete the partial file first for a clean re-run if you'd rather not wait for that.

### Added

- `pyproject.toml` — `ruff` lint + format configuration.
- `requirements-dev.txt` — adds `ruff` and `pytest` on top of the runtime `requirements.txt`.
- `.github/workflows/ci.yml` — runs `ruff check`, `ruff format --check`, and `pytest` on every push/PR.
- `tests/test_app.py` — regression tests for `_real_command()` (locks in the fix above) and `parse_pronto_capture()`.

## [0.1.0] - unreleased history not tracked before this changelog

Everything up to and including the Harmony bulk-export flow, Learning Mode, the visual form/JSON editor, and the online IR database selector (`docs/`) predates this changelog. Future entries start from here.
