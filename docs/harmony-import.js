// ---- Logitech Harmony archive → Astrion ir-database model entry ----------
//
// Converts one device of the Logitech Harmony IR archive
// (https://github.com/dckiller51/logitech-harmony-ir-archive, a fork of
// pickysysadmin/logitech-harmony-ir-archive) into the exact model-entry
// shape Astrion's ir-database/<category>.json already uses:
//
//   { model_name, commands: { <id>: { label, pronto, pronto_repeat? } }, meta }
//
// plus one new, optional block the app reads for Harmony-style Activities:
//
//   profile: {
//     source: "harmony-archive", global_device_id,
//     power:  { type: "discrete"|"toggle"|"none"|"unknown",
//               on?: [step], off?: [step], toggle?: [step] },
//     timing: { power_on_delay_ms, inter_key_delay_ms, inter_device_delay_ms,
//               input_delay_ms, repeats },
//     inputs: [ { name, steps: [step] } ]
//   }
//
//   step = "CommandId"                       (send that command)
//        | { delay_ms: n }                   (wait, send nothing)
//        | { hold: "CommandId", duration_ms } (keep sending for n ms)
//
// Command ids are the archive's own Harmony command names ("PowerOn",
// "InputHdmi1", ...), trimmed — the macros above reference them by that
// exact name. An app that doesn't know "profile" just ignores it, so these
// files stay readable by older Astrion versions.
//
// Pure functions, no DOM: loaded by index.html in the browser, and by
// tests/test_harmony_import.mjs under Node.

(function (root) {
  'use strict';

  // Your fork, so the data can't move or disappear under you. Read through
  // raw.githubusercontent.com, which serves CORS headers — works straight
  // from GitHub Pages, no server needed. Nothing is bundled here: the IR
  // codes themselves are Logitech's (see the archive's README/licence).
  const ARCHIVE_BASE = 'https://raw.githubusercontent.com/dckiller51/logitech-harmony-ir-archive/main/';

  const MAX_REPEATS = 10;

  function cleanName(s) {
    return String(s == null ? '' : s).trim();
  }

  function intOr(v, fallback) {
    const n = Number(v);
    return Number.isFinite(n) && n >= 0 ? Math.round(n) : fallback;
  }

  /** One archive action-list step → an Astrion step, or null to drop it
   * ({set, to} only records a state value — nothing is transmitted). */
  function convertStep(step) {
    if (typeof step === 'string') {
      const id = cleanName(step);
      return id ? id : null;
    }
    if (!step || typeof step !== 'object') return null;
    if ('delayMs' in step) return { delay_ms: intOr(step.delayMs, 0) };
    if ('command' in step) {
      const id = cleanName(step.command);
      if (!id) return null;
      return 'durationMs' in step ? { hold: id, duration_ms: intOr(step.durationMs, 0) } : id;
    }
    if ('hold' in step) {
      const id = cleanName(step.hold);
      return id ? { hold: id, duration_ms: 0 } : null;
    }
    return null;
  }

  function convertSteps(list) {
    return (Array.isArray(list) ? list : []).map(convertStep).filter(s => s !== null);
  }

  /** Command ids a list of steps references — used to flag macros that
   * point at a command the codeset doesn't have. */
  function referencedIds(steps) {
    return steps
      .map(s => (typeof s === 'string' ? s : s.hold))
      .filter(Boolean);
  }

  function convertPower(power) {
    if (!power || typeof power !== 'object') return { type: 'unknown' };
    const type = ['discrete', 'toggle', 'none'].includes(power.type) ? power.type : 'unknown';
    const out = { type };
    if (power.on) out.on = convertSteps(power.on);
    if (power.off) out.off = convertSteps(power.off);
    if (power.toggle) out.toggle = convertSteps(power.toggle);
    return out;
  }

  function convertTiming(timing) {
    const t = timing || {};
    const repeats = Math.min(MAX_REPEATS, Math.max(1, intOr(t.pressMinRepeats, 0) || intOr(t.minRepeats, 0) || 1));
    return {
      power_on_delay_ms: intOr(t.powerOnDelay, 0),
      inter_key_delay_ms: intOr(t.interKeyDelay, 0),
      inter_device_delay_ms: intOr(t.interDeviceDelay, 0),
      input_delay_ms: intOr(t.inputDelay, 0),
      repeats
    };
  }

  function convertInputs(inputs) {
    const list = (inputs && Array.isArray(inputs.list)) ? inputs.list : [];
    return list
      .map(i => ({ name: cleanName(i.name), steps: convertSteps(i.commands) }))
      .filter(i => i.name && i.steps.length);
  }

  /**
   * device:  the archive's devices/<Manufacturer>/<Model>.json
   * codeset: the archive's codesets/<xx>/<hash>.json (or null)
   * Returns { brand, entry, warnings }.
   */
  function convertDevice(device, codeset) {
    const warnings = [];
    const commands = {};
    let skipped = 0;
    ((codeset && codeset.commands) || []).forEach(c => {
      const id = cleanName(c.name);
      if (!id) return;
      if (!c.pronto) { skipped++; return; } // radio / HID / network — not IR
      if (commands[id]) return; // first one wins on a duplicate name
      const cmd = { label: id, pronto: c.pronto };
      if (c.prontoRepeat) cmd.pronto_repeat = c.prontoRepeat;
      commands[id] = cmd;
    });
    if (skipped) warnings.push(`${skipped} non-IR command(s) skipped`);

    const profile = {
      source: 'harmony-archive',
      global_device_id: device.globalDeviceId,
      power: convertPower(device.power),
      timing: convertTiming(device.timing),
      inputs: convertInputs(device.inputs)
    };

    const allSteps = []
      .concat(profile.power.on || [], profile.power.off || [], profile.power.toggle || [])
      .concat(...profile.inputs.map(i => i.steps));
    const missing = [...new Set(referencedIds(allSteps).filter(id => !commands[id]))];
    if (missing.length) warnings.push(`macros reference missing command(s): ${missing.join(', ')}`);
    if (profile.power.type === 'toggle') warnings.push('toggle power: Astrion tracks on/off itself, use "Help" if it gets out of sync');

    const entry = {
      model_name: cleanName(device.model),
      commands,
      meta: { source: 'Logitech Harmony archive', global_device_id: device.globalDeviceId },
      profile
    };
    return { brand: cleanName(device.manufacturer), entry, warnings };
  }

  /** Best-effort Astrion category guess from the archive's (undecoded)
   * deviceType enum plus the input names — the person can always change
   * it in the import form. */
  function guessCategory(device) {
    const names = ((device.inputs && device.inputs.list) || []).map(i => String(i.name).toLowerCase()).join(' ');
    if (/hdmi|tv|antenna/.test(names) && device.deviceType === 1) return 'tv';
    if (/tuner|phono|cd|aux|optical|coax/.test(names)) return 'audio';
    if (device.deviceType === 1) return 'tv';
    return 'player';
  }

  async function fetchJson(path, fetchImpl) {
    const res = await (fetchImpl || fetch)(ARCHIVE_BASE + path);
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
    return res.json();
  }

  /** Manufacturer list: [{c: modelCount, n: displayName, s: folder}] */
  function loadManufacturers(fetchImpl) {
    return fetchJson('index.json', fetchImpl);
  }

  /** Models of one manufacturer: [{f: fileName, id, m: modelName}] */
  async function loadModels(folder, fetchImpl) {
    const idx = await fetchJson(`devices/${encodeURIComponent(folder)}/index.json`, fetchImpl);
    return Array.isArray(idx) ? idx : (idx.models || []);
  }

  /** Fetches device + codeset and converts them. */
  async function importDevice(folder, fileName, fetchImpl) {
    const device = await fetchJson(`devices/${encodeURIComponent(folder)}/${encodeURIComponent(fileName)}`, fetchImpl);
    const codeset = device.codeset ? await fetchJson(device.codeset, fetchImpl) : null;
    const result = convertDevice(device, codeset);
    result.category = guessCategory(device);
    return result;
  }

  const api = {
    ARCHIVE_BASE, convertStep, convertSteps, convertPower, convertTiming, convertInputs,
    convertDevice, guessCategory, loadManufacturers, loadModels, importDevice
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HarmonyImport = api;
})(typeof window !== 'undefined' ? window : globalThis);
