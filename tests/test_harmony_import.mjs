// node --test tests/test_harmony_import.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const H = require('../docs/harmony-import.js');

const samsung = {
  manufacturer: 'Samsung', model: ' UE48H6200', globalDeviceId: 261647, deviceType: 1,
  codeset: 'codesets/89/x.json',
  power: { type: 'discrete', on: ['PowerOn'], off: ['PowerOff'] },
  inputs: { type: 1, list: [
    { name: 'HDMI 1', commands: ['InputHdmi1', 'Exit', { delayMs: 2500 }, 'InputHdmi1'] },
    { name: 'Empty', commands: [] }
  ] },
  timing: { powerOnDelay: 5000, interKeyDelay: 100, interDeviceDelay: 500, inputDelay: 0, pressMinRepeats: 3 }
};
const codeset = { commands: [
  { name: 'PowerOn', pronto: '0000 006D 0002 0000 0010 0010 0010 0010' },
  { name: 'PowerOff', pronto: '0000 006D 0002 0000 0010 0010 0010 0020', prontoRepeat: '0000 006D 0001 0000 0010 0100' },
  { name: 'InputHdmi1', pronto: '0000 006D 0002 0000 0010 0030 0010 0030' },
  { name: 'Exit ', pronto: '0000 006D 0002 0000 0010 0040 0010 0040' },
  { name: 'Netflix', keycode: 'x' }
] };

test('converts a discrete device into an ir-database model entry with a profile', () => {
  const r = H.convertDevice(samsung, codeset);
  assert.equal(r.brand, 'Samsung');
  assert.equal(r.entry.model_name, 'UE48H6200');
  assert.deepEqual(Object.keys(r.entry.commands), ['PowerOn', 'PowerOff', 'InputHdmi1', 'Exit']);
  assert.equal(r.entry.commands.PowerOff.pronto_repeat, '0000 006D 0001 0000 0010 0100');
  assert.deepEqual(r.entry.profile.power, { type: 'discrete', on: ['PowerOn'], off: ['PowerOff'] });
  assert.deepEqual(r.entry.profile.timing, {
    power_on_delay_ms: 5000, inter_key_delay_ms: 100, inter_device_delay_ms: 500, input_delay_ms: 0, repeats: 3
  });
  assert.deepEqual(r.entry.profile.inputs, [
    { name: 'HDMI 1', steps: ['InputHdmi1', 'Exit', { delay_ms: 2500 }, 'InputHdmi1'] }
  ]);
  assert.match(r.warnings.join(' '), /1 non-IR/);
});

test('toggle power, hold and state steps', () => {
  assert.deepEqual(H.convertPower({ type: 'toggle', toggle: ['PowerToggle'] }), { type: 'toggle', toggle: ['PowerToggle'] });
  assert.deepEqual(H.convertStep({ command: 'VolumeUp', durationMs: 800 }), { hold: 'VolumeUp', duration_ms: 800 });
  assert.deepEqual(H.convertStep({ hold: 'Menu' }), { hold: 'Menu', duration_ms: 0 });
  assert.equal(H.convertStep({ set: 'Power', to: 'On' }), null);
  assert.equal(H.convertPower(undefined).type, 'unknown');
});

test('repeats default to 1 and are clamped', () => {
  assert.equal(H.convertTiming({}).repeats, 1);
  assert.equal(H.convertTiming({ minRepeats: 2 }).repeats, 2);
  assert.equal(H.convertTiming({ pressMinRepeats: 99 }).repeats, 10);
});

test('flags macros referencing a command the codeset lacks', () => {
  const r = H.convertDevice({ ...samsung, inputs: { list: [{ name: 'AUX', commands: ['InputAux'] }] } }, codeset);
  assert.match(r.warnings.join(' '), /InputAux/);
});

test('inputs defined as a device state follow the state select route (e.g. LG TVs)', () => {
  const lg = {
    manufacturer: 'LG', model: 'OLED65B8', globalDeviceId: 480369, deviceType: 1,
    power: { type: 'discrete', on: ['PowerOn'], off: ['PowerOff'] },
    inputs: { list: [
      { name: 'HDMI 2', commands: [{ set: 'Screen', to: 'HDMI2' }] },
      { name: 'TV', commands: [{ set: 'Screen', to: 'Antenna' }, { set: 'TVInput', to: 'TV' }] },
      { name: 'Ghost', commands: [{ set: 'Screen', to: 'Nowhere' }] }
    ] },
    states: {
      Screen: { values: [
        { name: 'Antenna', select: [{ commands: ['InputTv', { delayMs: 2000 }], setType: 1 }] },
        { name: 'HDMI2', select: [{ commands: ['InputHdmi2'], setType: 1 }] }
      ] },
      TVInput: { next: ['InputTv'], values: [{ name: 'TV' }] }
    }
  };
  const cs = { commands: ['InputHdmi2', 'InputTv', 'PowerOn', 'PowerOff'].map(n => ({ name: n, pronto: '0000 006D 0001 0000 0010 0010' })) };
  const r = H.convertDevice(lg, cs);
  assert.deepEqual(r.entry.profile.inputs, [
    { name: 'HDMI 2', steps: ['InputHdmi2'] },
    { name: 'TV', steps: ['InputTv', { delay_ms: 2000 }] }
  ]);
});
