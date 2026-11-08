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
