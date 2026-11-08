// MC8 Pro preset message fields: data[] bytes <-> readable values. Layouts: research/mc8-backup-format.md section 3.
const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWX';
const SCROLL = ['send', 'inc+send', 'dec+send', 'update', 'reset', 'inc', 'dec'];
const SETTOGGLE = ['disengage', 'engage', 'toggle', 'shift', 'unshift', 'shift+', 'set', 'shift hold', 'engage last', 'disengage last'];
const RELAY = ['nothing', 'tap-no', 'tap-nc', 'engage', 'disengage', 'toggle', 'sync8'];
const PORT = ['Omni1', 'Omni2', 'Omni3', 'Omni4', 'RelayA', 'RelayB'];
const REALTIME = ['nothing', 'start', 'stop', 'continue'];
const FRACTAL = ['Axe-Fx III', 'FM3', 'FM9'];
const AXEINT = ['preset', 'scene', 'preset+scene', 'effect bypass'];
const OUTPUTS = ['DIN', 'USB1', 'Omni1', 'Omni2', 'Omni3', 'Omni4', '3.5mm', 'USB2', 'USB3', 'USB4', 'USBHost'];
const ENGAGE_ACTION = ['none', 'press', 'release', 'long press', 'long press release', 'double tap', 'double tap release', 'long double tap', 'long double tap release', 'release all', 'long press scroll'];
const UTILITY = ['set msg scroll counter', 'clear global toggles', 'bpm +1', 'bpm -1', 'set scroll counter', 'output mask', 'manage msg scroll', 'bank color', 'preset color', 'selected preset color', 'delay LCD refresh', 'fast step on', 'fast step off'];

// Set Toggle mask: 7 bits per byte, A = bit 0 of data[0], V..X in data[3]
const maskPresets = d => [...LETTERS].filter((_, i) => d[Math.floor(i / 7)] >> (i % 7) & 1);
const clockType = d => (d[2] & 1) | ((d[2] >> 4 & 3) << 1);

export function decode(m) {
  const d = m.data, ch = ` ch${m.c}`;
  switch (m.t) {
    case 1: return (d[2] === 127 ? `PC ${d[0]} all channels` : d[2] ? `PC last-sent mode ${d[2]}` : `PC ${d[0]}`) + ch;
    case 2: return (d[2] & 1 ? `CC ${d[0]} = exp${(d[2] >> 1 & 3) + 1}` : `CC ${d[0]} = ${d[1]}`) + ch;
    case 3: return `note on ${d[0]} vel ${d[1]}` + ch;
    case 4: return (d[2] ? 'note off all' : `note off ${d[0]} vel ${d[1]}`) + ch;
    case 5: return `realtime ${REALTIME[d[0]] ?? d[0]}`;
    case 6: return `sysex data [${d.join(' ')}]`;
    case 7: { const t = clockType(d); if (t === 5) return `clock load slot ${d[0]}`; if (t) return ['', 'clock menu', 'clock next slot', 'clock prev slot', 'clock tap'][t]; const b = d[0] * 100 + d[1]; return b || d[2] & 2 ? `clock start ${d[2] & 2 ? 'current' : b} bpm` : 'clock stop'; }
    case 13: return d[1] ? `bank jump last (${d[1]})` : `bank jump ${d[0] + 1} page ${((d[2] >> 3 & 1) << 1 | d[2] & 1) + 1}${d[2] & 2 ? '' : ' ignore-enter'}${d[2] & 4 ? '' : ' ignore-exit'}`;
    case 14: return d[0] === 1 ? 'page up' : d[0] === 2 ? 'page down' : `page ${d[0] - 2}`;
    case 15: return `set toggle ${SETTOGGLE[(m.c - 1) & 15] ?? m.c} [${maskPresets(d).join(',')}]`;
    case 16: return `midi thru ${d[0] ? 'on' : 'off'}`;
    case 17: return `select exp ${(d[0] & 3) + 1}`;
    case 18: return `looper mode ${['toggle', 'engage', 'disengage'][d[0] & 3]}`;
    case 21: return `tuner ${FRACTAL[d[0]] ?? d[0]}` + ch;
    case 23: return `delay ${d[0] * 10} ms`;
    case 25: return `song position ${d[0] << 7 | d[1]}`;
    case 26: case 31: return `${m.t === 26 ? 'waveform' : 'sequencer'} ${d[1] & 64 ? 'start' : 'stop'} engine ${d[4] === 15 ? 'all' : d[4]} cc ${d[0]}` + ch;
    case 27: return `engage ${LETTERS[d[1] & 31]}${d[1] & 64 ? '' : ` bank ${d[0] + 1}`} ${ENGAGE_ACTION[d[2]] ?? d[2]}`;
    case 29: return `song select ${d[0]}`;
    case 32: { const t = d[0] >> 4; return `cc scroll ${SCROLL[t]} counter ${d[0] & 15} ${t === 3 ? 'value' : 'cc'} ${d[1]} step ${(d[2] & 63) || 1}${d[2] & 64 ? ' wrap' : ''}` + ch; }
    case 33: { const t = d[0] >> 4; return `pc scroll ${SCROLL[t]} counter ${d[0] & 15}${t === 3 ? ` value ${d[1]}` : ''}${d[2] & 1 ? '' : ' wrap'}` + ch; }
    case 34: { const mask = d[1] | d[2] << 7 | ((m.c - 1) & 3) << 14, r = []; for (let i = 0; i < 16; i++) if (mask >> i & 1) r.push(i + 1); return `PC ${d[0]} channels ${r.join(',')}`; }
    case 36: {
      if (d[0] === 5) { const mask = d[3] << 7 | d[2]; return `output mask ${OUTPUTS.filter((_, i) => mask >> i & 1).join(',')}`; }
      return `utility ${UTILITY[d[0]] ?? d[0]} [${d.slice(1, 5).join(' ')}]`;
    }
    case 37: return `fractal integration ${FRACTAL[d[2] & 3]} ${AXEINT[d[0] & 3]} from ${(d[0] >> 5 & 3) << 7 | d[1]}` + ch;
    case 40: return `relay ${PORT[d[0]] ?? d[0]} tip ${RELAY[d[1]] ?? d[1]} ring ${RELAY[d[2]] ?? d[2]}`;
    case 41: return `mmc ${d[0]} device ${d[1]}`;
    case 42: return `trigger messages of ${LETTERS[d[0]]}`;
    case 43: return `focus ${['on', 'off', 'toggle'][d[0]]}`;
    case 44: return `rename to "${String.fromCharCode(...d.filter(x => x >= 32))}"`;
    default: return null;
  }
}

// Expression presets have their own type numbering (spec section 5).
export function decodeExp(m) {
  const d = m.data, ch = ` ch${m.c}`;
  switch (m.t) {
    case 1: return `expression CC ${d[0]} ${d[1]}..${d[2]}` + ch;
    case 13: return `expression CC ${d[0]} ${d[1]}..${d[2]} scaling ${d[3]}` + ch;
    case 2: case 3: return `${m.t === 2 ? 'toe down' : 'heel down'} CC ${d[0]} = ${d[1]}` + ch;
    case 6: case 7: return `on ${m.t === 6 ? 'engage' : 'disengage'} CC ${d[0]} = ${d[1]}` + ch;
    case 8: case 9: return `on ${m.t === 8 ? 'engage' : 'disengage'} PC ${d[0]}` + ch;
    default: return null;
  }
}

const pick = (list, v, what) => { const i = list.indexOf(String(v).toLowerCase()); if (i < 0) throw new Error(`${what}: ${v} (have: ${list.join(', ')})`); return i; };

// Named shortcuts for `msg`: fill m from readable keys and return the keys used. Other types keep d0..d17.
export function encode(m, o) {
  const d = m.data, used = [];
  const take = k => { used.push(k); return o[k]; };
  const opt = (k, v) => o[k] === undefined ? v : take(k);
  switch (m.t) {
    case 1: if (o.pc !== undefined) d[0] = +take('pc'); break;
    case 2: if (o.cc !== undefined) {
      d[0] = +take('cc'); d[1] = +opt('value', 0);
      if (o.exp !== undefined) { d[2] = 1 | (+take('exp') - 1) << 1; d[1] = 0; }
    } break;
    case 5: if (o.do !== undefined) d[0] = pick(REALTIME, take('do'), 'realtime'); break;
    case 7:
      if (o.tap !== undefined) { take('tap'); d[2] = 2 << 4; }
      else if (o.bpm !== undefined) { const b = +take('bpm'); d[0] = Math.floor(b / 100); d[1] = b % 100; }
      break;
    case 13: if (o.bank !== undefined) { d[0] = +take('bank') - 1; const p = +opt('page', 1) - 1; d[2] = (p >> 1) << 3 | p & 1 | 6; } break;
    case 14: if (o.page !== undefined) { const v = take('page'); d[0] = v === 'up' ? 1 : v === 'down' ? 2 : +v + 2; } break;
    case 15: if (o.do !== undefined) {
      m.c = pick(SETTOGGLE, take('do'), 'set toggle') + 1;
      for (const L of take('presets').toUpperCase().split(',')) { const i = LETTERS.indexOf(L); if (i < 0) throw new Error('preset ' + L); d[Math.floor(i / 7)] |= 1 << (i % 7); }
    } break;
    case 21: if (o.model !== undefined) d[0] = pick(FRACTAL.map(x => x.toLowerCase()), take('model'), 'model'); break;
    case 23: if (o.ms !== undefined) d[0] = Math.round(+take('ms') / 10); break;
    case 27: if (o.preset !== undefined) {
      const L = LETTERS.indexOf(take('preset').toUpperCase()); if (L < 0) throw new Error('preset A-X');
      const b = opt('bank'); d[1] = L | (b === undefined ? 64 : 0); d[0] = b === undefined ? 0 : +b - 1; d[2] = pick(ENGAGE_ACTION, opt('do', 'press'), 'action');
    } break;
    case 32: if (o.scroll !== undefined) {
      const t = pick(SCROLL, take('scroll'), 'scroll'); d[0] = t << 4 | +opt('counter', 0); d[1] = +opt('cc', 0);
      d[2] = (+opt('step', 1) & 63) | (opt('wrap', 'no') === 'yes' ? 64 : 0);
    } break;
    case 36: if (o.outputs !== undefined) {
      let mask = 0; for (const n of take('outputs').split(',')) mask |= 1 << pick(OUTPUTS.map(x => x.toLowerCase()), n, 'output');
      d[0] = 5; d[2] = mask & 127; d[3] = mask >> 7;
    } break;
    case 37: if (o.mode !== undefined) {
      const from = +opt('from', 0); d[0] = pick(AXEINT, take('mode'), 'mode') | (from >> 7 & 3) << 5; d[1] = from & 127;
      d[2] = pick(FRACTAL.map(x => x.toLowerCase()), opt('model', 'fm3'), 'model');
    } break;
    case 40: if (o.port !== undefined) {
      const p = PORT.map(x => x.toLowerCase()).indexOf(String(take('port')).toLowerCase().replace(/^([ab])$/, 'relay$1')); if (p < 0) throw new Error('port A, B, omni1-4');
      d[0] = p; d[1] = pick(RELAY, opt('tip', 'nothing'), 'tip'); d[2] = pick(RELAY, opt('ring', 'nothing'), 'ring');
    } break;
  }
  return used;
}
