"""MC8 Pro global settings (all 10 sections), decode/encode. Layouts from benemon/morningstar-sdk."""
CFG = ['midiClockPersist', 'dualLock', 'switchSensitivity', 'midiChannel', 'lcdAlign', 'bankChangeDelay',
       'bankChangeDisplay', 'thruUSBHost', 'thruUSBDevice', 'thruDIN5', 'thru35mm', 'thruBluetooth',
       'rememberToggleStates', 'longPressTime', 'btStartupDelay', 'ignoreMidiClock', 'loadLastBank',
       'numMidiCable', 'midiSendDelay', 'presetMaxFont', 'showPresetLabels', 'screenSaver', 'clockOutLSB',
       'clockOutMSB', 'relayPortA', 'relayPortB', 'brightness', 'middleLayerFont', 'bankPageFont']
OMNI = ['portNum', 'type', 'fixedSwTip', 'td1', 'td2', 'fixedSwRing', 'rd1', 'rd2', 'fixedSwTipRing', 'trd1', 'trd2']
EV = ['numberFrom', 'numberTo', 'channelFrom', 'channelTo', 'typeFrom', 'typeTo', 'valueFrom', 'valueTo',
      'setOutgoingValue', 'mapInputOutput', 'mapValue']


def rows(p):
    i, r = 0, []
    while i + 3 <= len(p) and p[i] == 0x7F:
        n = p[i + 2]; r.append((p[i + 1], list(p[i + 3:i + 3 + n]))); i += 3 + n
    return r


def row(tag, d): return [0x7F, tag, len(d), *d]


def dec(name, p):
    p = list(p)
    if name == 'config':
        d = dict(zip(CFG, p)); d['_spare'] = p[len(CFG):32]; return d
    if name == 'waveform':
        return [dict(zip(['engine', 'min', 'max', 'type'], p[1 + 4 * i:5 + 4 * i])) for i in range(p[0])]
    if name == 'scroll':
        return [dict(zip(['min', 'max', 'start'], p[1 + 3 * i:4 + 3 * i])) for i in range(p[0] & 0x1F)]
    if name == 'ladder':
        q = p + [0] * 4
        return [dict(zip(['switch', 'trigger', 'f1', 'f2'], q[1 + 4 * i:5 + 4 * i])) for i in range(p[0])]
    if name == 'clock':
        return {'_reserved': p[0], 'bpm': [p[2 + 2 * i] | p[3 + 2 * i] << 7 for i in range(p[1] & 0x1F)]}
    if name == 'arrangement':
        return {'active': p[0], 'countMinus1': p[1], '_reserved': p[2:10], 'order': p[10:]}
    if name == 'sequencer':
        return [{'len': p[1 + 18 * i] & 15, '_r': p[2 + 18 * i], 'steps': p[3 + 18 * i:19 + 18 * i]} for i in range(p[0])]
    if name == 'omniports':
        return [dict(zip(OMNI, p[1 + 11 * i:12 + 11 * i])) for i in range(p[0])]
    if name == 'events':
        return [{'slot': t, **dict(zip(EV, d))} for t, d in [(q[1], q[3:14]) for q in
                [p[i:i + 14] for i in range(0, len(p) - 13, 14)] if q[0] == 0x7F]]
    if name == 'channels':
        ch = [{'n': i} for i in range(16)]
        for t, d in rows(p):
            if t < 16: ch[t]['name'] = bytes(d).decode('ascii', 'replace').rstrip(' ')
            elif t < 32: ch[t - 16]['remap'], ch[t - 16]['portMSB'], ch[t - 16]['portLSB'], ch[t - 16]['_x'] = (d + [0] * 4)[:4]
            elif t < 48: ch[t - 32]['attr'] = d
        return ch
    raise KeyError(name)


def enc(name, d):
    """Encode the WRITE payload (some sections differ from the dump, see SDK notes)."""
    if name == 'config':
        return [d[k] for k in CFG] + d['_spare']
    if name == 'waveform':
        return [len(d)] + [x for e in d for x in (e['min'], e['max'], e['type'])]
    if name == 'scroll':
        return [len(d)] + [x for e in d for x in (e['min'], e['max'], e['start'])]
    if name == 'ladder':
        return [len(d)] + [x for e in d for x in (e['switch'], e['trigger'], e['f1'], e['f2'])]
    if name == 'clock':
        b = [max(0, min(500, x)) for x in d['bpm']]
        return [len(b)] + [x for v in b for x in (v & 127, v >> 7)]
    if name == 'arrangement':
        return [d['active'], d['countMinus1']] + d['_reserved'] + d['order']
    if name == 'sequencer':
        return [len(d)] + [x for e in d for x in [e['len'] & 15, e['_r']] + e['steps']]
    if name == 'omniports':
        return [e[k] for e in d for k in OMNI]
    if name == 'events':
        return [x for e in sorted(d, key=lambda e: e['slot']) for x in [0x7F, e['slot'], 11] + [e[k] for k in EV]]
    if name == 'channels':
        o = []
        for c in d: o += row(c['n'], list(c.get('name', '').encode('ascii')[:16].ljust(16, b' ')))
        for c in d: o += row(16 + c['n'], [c['remap'], c['portMSB'], c['portLSB'], c['_x']])
        for c in d: o += row(32 + c['n'], c['attr'])
        return o
    raise KeyError(name)


# name: (request cmd2 or None, reply 03 xx, write 04 xx)
SECTIONS = {'config': (36, 0x21, 2), 'channels': (40, 0x20, 3), 'arrangement': (41, 0x22, 4),
            'waveform': (37, 0x24, 5), 'sequencer': (38, 0x25, 6), 'scroll': (39, 0x26, 7),
            'omniports': (42, 0x23, 8), 'events': (45, 0x27, 10), 'ladder': (None, 0x28, 11), 'clock': (80, 0x29, 12)}


# Value meanings, from the Morningstar web editor (MC8 Pro general configuration page)
ONOFF = lambda v: 'on' if v else 'off'
THRU_DEST = {5: 'Bluetooth', 4: 'USB Host', 3: 'USB Device', 2: 'DIN5', 1: 'Omniport', 0: '3.5mm'}
def thru(v): return ', '.join(n for b, n in THRU_DEST.items() if v >> b & 1) or 'none'
CLOCK_PORTS = ['DIN MIDI', 'USB Device Port 1', 'Omniport 1', 'Omniport 2', 'Omniport 3', 'Omniport 4',
               '3.5mm TRS MIDI', 'USB Device Port 2', 'USB Device Port 3', 'USB Device Port 4', 'USB Host', 'Bluetooth']
OMNI_TYPE = {12: 'Disabled', 8: 'TRS Aux Switch', 11: 'Resistor Ladder Aux Switch', 1: 'Expression',
             5: 'MIDI Out - Type A (Standard)', 6: 'MIDI Out - Tip Active', 7: 'MIDI Out - Ring Active',
             9: 'MIDI Out - Type B', 10: 'Ext Omniport Relay Interface', 0: '(Deprecated) Aux Switch'}
RELAY = ['Tip NO, Ring NO', 'Tip NO, Ring NC', 'Tip NC, Ring NO', 'Tip NC, Ring NC']
FONT = lambda v: 18 - v if 0 <= v <= 10 else v
WAVE = ['Off', 'Sawtooth Up', 'Sawtooth Down', 'Triangle', 'Sine', 'Square', 'Random']
CFG_SHOW = {
    'midiChannel': ('MIDI Channel', lambda v: 'Disabled' if v == 0 else v),
    'switchSensitivity': ('Switch Sensitivity', lambda v: v + 1),
    'longPressTime': ('Long Press Time', lambda v: f'{100 + 50 * v} ms'),
    'bankChangeDelay': ('Bank Change Delay Time', lambda v: f'{10 * v} ms'),
    'bankChangeDisplay': ('Bank Change Display Time', lambda v: f'{10 * v} ms'),
    'midiSendDelay': ('MIDI Send Delay', lambda v: f'{v} ms'),
    'numMidiCable': ('USB Virtual MIDI Ports', str),
    'dualLock': ('Dual Switch Lock', ONOFF), 'midiClockPersist': ('MIDI Clock Persist', ONOFF),
    'rememberToggleStates': ('Remember Toggle States', ONOFF), 'loadLastBank': ('Load last used bank on power up', ONOFF),
    'ignoreMidiClock': ('Ignore MIDI Clock', ONOFF), 'lcdAlign': ('Align LCD Names', ONOFF),
    'showPresetLabels': ('Show Preset Labels', ONOFF),
    'thruUSBHost': ('USB Host MIDI In, thru to', thru), 'thruUSBDevice': ('USB Device MIDI In, thru to', thru),
    'thruDIN5': ('DIN5 MIDI In, thru to', thru), 'thru35mm': ('3.5mm MIDI In, thru to', thru),
    'thruBluetooth': ('Bluetooth MIDI In, thru to', thru),
    'btStartupDelay': ('Bluetooth Startup Delay', lambda v: 'OFF' if v == 0 else f'{10 * (v - 1)} s'),
    'screenSaver': ('Screensaver', lambda v: 'Off' if v == 0 else f'{v} h'),
    'brightness': ('Brightness', lambda v: f'{30 + 10 * v} %'),
    'relayPortA': ('Relay Port A', lambda v: RELAY[v] if v < 4 else v),
    'relayPortB': ('Relay Port B', lambda v: RELAY[v] if v < 4 else v),
    'presetMaxFont': ('Preset Max Font Size', FONT), 'middleLayerFont': ('Bank / Preset Long Name Font Size', FONT),
    'bankPageFont': ('Bank Page Font Size', lambda v: ['Large', 'Medium', 'Small', 'Hidden'][v] if v < 4 else v),
}


def describe(s):
    """Readable lines for a settings dict (as written by settings read)."""
    out = []
    c = s['config']['decoded']
    for k, (lab, f) in CFG_SHOW.items():
        out.append(f'{lab}: {f(c[k])}   [config.{k} = {c[k]}]')
    clk = c['clockOutLSB'] | c['clockOutMSB'] << 7
    out.append('MIDI Clock ports: ' + (', '.join(n for i, n in enumerate(CLOCK_PORTS) if clk >> i & 1) or 'none'))
    for o in s['omniports']['decoded']:
        out.append(f"Omniport {o['portNum'] + 1}: {OMNI_TYPE.get(o['type'], o['type'])}   [omniports.{o['portNum']}.type = {o['type']}]")
    for i, w in enumerate(s['waveform']['decoded']):
        if w['type']: out.append(f"Waveform {i + 1}: {WAVE[w['type']] if w['type'] < 7 else w['type']} {w['min']}-{w['max']}")
    for i, q in enumerate(s['sequencer']['decoded']):
        if q['len'] or any(q['steps']): out.append(f"Sequencer {i + 1}: len {q['len']} steps {q['steps']}")
    for i, q in enumerate(s['scroll']['decoded']):
        if (q['min'], q['max'], q['start']) != (0, 127, 0): out.append(f"Scroll counter {i + 1}: {q['min']}-{q['max']} start {q['start']}")
    for e in s['events']['decoded']:
        if any(v for k, v in e.items() if k != 'slot'): out.append(f"Event rule {e['slot'] + 1}: {e}")
    for c2 in s['channels']['decoded']:
        if c2.get('name') or c2['remap'] or any(c2['attr']): out.append(f"MIDI channel {c2['n'] + 1}: {c2}")
    a = s['arrangement']['decoded']
    out.append('Bank arrangement: ' + ('custom' if a['active'] else 'default order'))
    bpm = [b for b in s['clock']['decoded']['bpm'] if b]
    out.append('MIDI clock BPM slots: ' + (', '.join(map(str, bpm)) or 'all empty'))
    lad = [l for l in s['ladder']['decoded'] if l['trigger'] or l['f1'] or l['f2']]
    out.append(f'Resistor ladder switches set: {len(lad)}')
    return out
