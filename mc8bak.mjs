// Offline editor for Morningstar MC8 Pro backup files (.json from Editor > Controller Backup).
// Usage: node mc8bak.mjs <cmd> ...
//   check <file>                              verify hash and shape
//   info <file>                               banks in use, non-default settings
//   bank <file> <bank>                        presets and messages of a bank (bank 1 = first)
//   preset <file> <bank> <A-X>                one preset in full
//   name <in> <out> <bank> <A-X> <short> [toggle]   rename a preset
//   bankname <in> <out> <bank> <name>
//   opt <in> <out> <bank> <A-X> key=value ...  preset fields (toToggle=true, ledColor=3...)
//   msg <in> <out> <bank> <A-X> <slot 1-32> <type> [key=value ...]   write a message
//        type = number or name (cc, pc, ...); keys: a=action, tg=pos, c=channel, d0..d17, plus named fields:
//        cc cc=20 value=64 | cc cc=7 exp=1 | pc pc=5 | realtime do=start | 'bank jump' bank=2 page=1 | 'toggle page' page=up
//        'set toggle' do=disengage presets=E,H | delay ms=50 | 'engage preset' preset=B do=press | relay port=A tip=tap-no
//        'cc value scroll' scroll=inc+send counter=0 cc=20 step=16 | utility outputs=din,3.5mm | 'axe fx tuner' model=fm3
//        'axe fx integration' mode=scene model=fm3 | 'clock tap menu' tap=1
//   clearmsg <in> <out> <bank> <A-X> <slot>
//   setting <in> <out> <section>.<key> <value>  controller setting, e.g. general.midiThru false
//   export <in> <out> <bank>                  single-bank file, quicker to restore
//   diff <a> <b>                              list every changed leaf
import { readFileSync, writeFileSync } from 'node:fs';
import { decode, decodeExp, encode } from './mc8msg.mjs';

export const TYPES = ['Empty', 'PC', 'CC', 'Note On', 'Note Off', 'Realtime', 'SysEx', 'Clock Tap Menu', 'PC Scroll Up', 'PC Scroll Down',
  'Bank Up', 'Bank Down', 'Bank Change Mode', 'Bank Jump', 'Toggle Page', 'Set Toggle', 'MIDI Thru', 'Select Exp', 'Looper Mode',
  'Strymon Bank Up', 'Strymon Bank Down', 'Axe FX Tuner', 'Toggle Preset', 'Delay', 'MIDI Clock Tap', 'Song Position', 'CC Waveform',
  'Engage Preset', 'Kemper Tuner', 'Song Select', 'Set Display', 'Sequence Generator', 'CC Value Scroll', 'PC Number Scroll',
  'PC Multi Channel', 'Keystrokes', 'Utility', 'Axe FX Integration', 'NRPN', 'ML10X', 'Relay Switching', 'MMC', 'Trigger Messages',
  'Focus Mode', 'Preset Rename', 'ML5R', 'Multi Engage/Bypass'];
export const ACTIONS = ['No Action', 'Press', 'Release', 'Long Press', 'Long Press Release', 'Double Tap', 'Double Tap Release',
  'Long Double Tap', 'Long Double Tap Release', 'Release All', 'Long Press Scroll', 'On Disengage', 'On First Engage', 'On First Engage Send Only This'];
export const POS = ['Pos 1', 'Pos 2', 'Both', 'Shift'];

// Java String.hashCode of JSON.stringify(data), as the editor writes it
export function hash(data) {
  const s = JSON.stringify(data); let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return h;
}
export const load = f => JSON.parse(readFileSync(f, 'utf8'));
export function save(d, f) { d.hash = hash(d.data); writeFileSync(f, JSON.stringify(d)); }

const banks = d => d.data.bankArray ?? [d.data.bank];
const bankOf = (d, n) => { const b = banks(d).find(x => x.bankNumber === n - 1) ?? (d.dumpType === 'singleBank' ? banks(d)[0] : null); if (!b) throw new Error('no bank ' + n); return b; };
const presetIdx = L => { const i = 'ABCDEFGHIJKLMNOPQRSTUVWX'.indexOf(L.toUpperCase()); if (i < 0 || L.length !== 1) throw new Error('preset A-X'); return i; };
const presetOf = (b, L) => b.presetArray[presetIdx(L)];
const isEmptyMsg = m => m.t === 0 && m.a === 0;
const LETTER = i => 'ABCDEFGHIJKLMNOPQRSTUVWX'[i];

function typeId(x) {
  if (/^\d+$/.test(x)) return +x;
  const n = { relay: 'relayswitching', scroll: 'ccvaluescroll', tuner: 'axefxtuner' }[x.toLowerCase()] ?? x.toLowerCase().replace(/[^a-z0-9]/g, '');
  const i = TYPES.findIndex(t => t.toLowerCase().replace(/[^a-z0-9]/g, '') === n);
  if (i < 0) throw new Error('unknown message type ' + x); return i;
}
function coerce(old, v) {
  if (typeof old === 'boolean') { if (v !== 'true' && v !== 'false') throw new Error('expected true/false: ' + v); return v === 'true'; }
  if (typeof old === 'number') { if (!/^-?\d+$/.test(v)) throw new Error('expected a number: ' + v); return +v; }
  return v;
}
export const fmtMsg = (m, i, isExp = false) => {
  const used = m.data.slice(); while (used.length && used.at(-1) === 0) used.pop();
  const what = (isExp ? decodeExp(m) : decode(m)) ?? `${TYPES[m.t] ?? 't' + m.t} ch${m.c} [${used.join(' ')}]`;
  return `  ${String(i + 1).padStart(2)} ${(ACTIONS[m.a] ?? 'a' + m.a).padEnd(12)} ${POS[m.tg].padEnd(5)} ${what}${m.mi ? ' mi=' + m.mi : ''}`;
};
const usedPreset = p => (p.shortName && p.shortName !== 'EMPTY') || p.toggleName || p.longName || p.shiftName || p.msgArray.some(m => !isEmptyMsg(m));
const usedBank = b => b.bankName || b.presetArray.some(usedPreset) || b.expPresetArray.some(p => p.msgArray.some(m => !isEmptyMsg(m))) || b.bankMsgArray.some(m => !isEmptyMsg(m));

function showPreset(p, full) {
  const names = [p.shortName, p.toggleName && 'toggle=' + p.toggleName, p.longName && 'long=' + p.longName, p.shiftName && 'shift=' + p.shiftName].filter(Boolean).join('  ');
  const flags = ['toToggle', 'toBlink', 'toMsgScroll'].filter(k => p[k]).join(' ') + (p.toggleGroup ? ` group=${p.toggleGroup}` : '');
  console.log(`${p.isExp ? 'EXP' + (p.presetNum + 1) : LETTER(p.presetNum)}: ${names} ${flags}`);
  if (full) for (const [k, v] of Object.entries(p)) if (k !== 'msgArray' && typeof v === 'number') console.log(`  ${k} = ${v}`);
  p.msgArray.forEach((m, i) => { if (!isEmptyMsg(m)) console.log(fmtMsg(m, i, p.isExp)); });
}
function leaves(a, b, path, out) {
  if (a === b) return;
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) { out.push(`${path}: ${JSON.stringify(a)} -> ${JSON.stringify(b)}`); return; }
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) leaves(a[k], b[k], path + '.' + k, out);
}
const SECTION = { general: d => d.data.controller_settings.data.controller_settings.data };

const [cmd, ...a] = process.argv.slice(2);
if (import.meta.url === 'file:///' + process.argv[1]?.split(String.fromCharCode(92)).join('/').replace(/ /g, '%20')) main();
function main() {
  const out = () => a[1];
  switch (cmd) {
    case 'check': {
      const d = load(a[0]); const ok = hash(d.data) === d.hash;
      console.log(`${d.dumpType} model ${d.deviceModel} ${d.downloadDate} banks ${banks(d).length} hash ${d.hash} ${ok ? 'OK' : 'BAD (computed ' + hash(d.data) + ')'}`);
      const raw = readFileSync(a[0], 'utf8');
      console.log(raw === JSON.stringify(d) ? 'round trip identical' : 'round trip differs');
      process.exit(ok ? 0 : 1); break;
    }
    case 'info': {
      const d = load(a[0]); const u = banks(d).filter(usedBank);
      console.log(`${banks(d).length} banks, ${u.length} in use`);
      for (const b of u) { console.log(`bank ${b.bankNumber + 1}: "${b.bankName}"`); b.presetArray.filter(usedPreset).forEach(p => showPreset(p)); }
      if (d.data.controller_settings) console.log(JSON.stringify(SECTION.general(d), (k, v) => k === 'midiThruMatrix' ? undefined : v));
      break;
    }
    case 'bank': {
      const b = bankOf(load(a[0]), +a[1]); console.log(`bank ${b.bankNumber + 1}: "${b.bankName}" clearToggle=${b.bankClearToggle} pageLimit=${b.pageLimit}`);
      b.bankMsgArray.forEach((m, i) => { if (!isEmptyMsg(m)) console.log('bank msg' + fmtMsg(m, i)); });
      b.presetArray.filter(usedPreset).forEach(p => showPreset(p));
      b.expPresetArray.filter(p => p.msgArray.some(m => !isEmptyMsg(m))).forEach(p => showPreset(p));
      break;
    }
    case 'preset': showPreset(presetOf(bankOf(load(a[0]), +a[1]), a[2]), true); break;
    case 'name': { const d = load(a[0]); const p = presetOf(bankOf(d, +a[2]), a[3]); p.shortName = a[4]; if (a[5] !== undefined) p.toggleName = a[5]; save(d, a[1]); break; }
    case 'bankname': { const d = load(a[0]); bankOf(d, +a[2]).bankName = a[3]; save(d, a[1]); break; }
    case 'opt': {
      const d = load(a[0]); const p = presetOf(bankOf(d, +a[2]), a[3]);
      for (const kv of a.slice(4)) { const [k, v] = kv.split('='); if (!(k in p) || k === 'msgArray') throw new Error('unknown field ' + k); p[k] = coerce(p[k], v); }
      save(d, a[1]); break;
    }
    case 'msg': case 'clearmsg': {
      const d = load(a[0]); const p = presetOf(bankOf(d, +a[2]), a[3]); const s = +a[4] - 1;
      if (!(s >= 0 && s < 32)) throw new Error('slot 1-32');
      const m = { data: Array(18).fill(0), m: s, c: 1, t: 0, a: 0, tg: 2, mi: '' };
      if (cmd === 'msg') {
        m.t = typeId(a[5]);
        const kvs = Object.fromEntries(a.slice(6).map(x => { const i = x.indexOf('='); return [x.slice(0, i), x.slice(i + 1)]; }));
        if (kvs.c) m.c = +kvs.c;
        const named = encode(m, kvs);
        for (const [k, v] of Object.entries(kvs)) {
          if (named.includes(k)) continue;
          const mm = /^d(\d+)$/.exec(k);
          if (mm) { if (+mm[1] > 17) throw new Error('d0-d17'); m.data[+mm[1]] = +v; }
          else if (k === 'a') { const i = /^\d+$/.test(v) ? +v : ACTIONS.findIndex(x => x.toLowerCase() === v.toLowerCase()); if (i < 0) throw new Error('action ' + v); m.a = i; }
          else if (k === 'c' || k === 'tg') m[k] = +v;
          else throw new Error('unknown key ' + k);
        }
      }
      p.msgArray[s] = m; save(d, a[1]); console.log(fmtMsg(m, s)); break;
    }
    case 'setting': {
      const d = load(a[0]); const [sec, key] = a[2].split('.'); const o = SECTION[sec]?.(d);
      if (!o || !(key in o)) throw new Error('unknown setting ' + a[2]);
      o[key] = coerce(o[key], a[3]); save(d, a[1]); break;
    }
    case 'export': {
      const d = load(a[0]); const bank = bankOf(d, +a[2]);
      const s = { schemaVersion: d.schemaVersion, dumpType: 'singleBank', deviceModel: d.deviceModel, downloadDate: d.downloadDate, hash: 0, data: { bank }, description: '' };
      save(s, a[1]); console.log('bank', a[2], 'hash', s.hash); break;
    }
    case 'diff': { const r = []; leaves(load(a[0]), load(a[1]), '', r); console.log(r.join('\n') || 'identical'); break; }
    default: console.log('check | info | bank | preset | name | bankname | opt | msg | clearmsg | setting | diff'); process.exit(1);
  }
}
