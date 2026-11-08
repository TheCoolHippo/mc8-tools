"""Direct USB connector for the MC8 Pro, no browser. Port of the session and restore protocol from
benemon/morningstar-sdk (hardware-verified on firmware 3.13.6). Windows, standard library only.
  python mc8usb.py info                       controller info and current bank name
  python mc8usb.py read <bank 1-128> <out.json>
  python mc8usb.py write <single-bank.json> --yes     restore to its bankNumber, read back, compare
  python mc8usb.py setting <byte> <value> --yes   change one general setting (32-byte 03 21 layout), read back
  python mc8usb.py compare <a.json> <b.json>
  python mc8usb.py settings read <out.json>       all 10 global sections (config, channels, omniports, ...), raw + decoded
  python mc8usb.py settings write <in.json> <section> --yes   encode the decoded block, write, read back, compare
  python mc8usb.py settings set <section.key.idx...> <value> --yes   e.g. config.brightness 5, omniports.0.type 1
Close the web editor first: one program at a time on the port. Writes go to flash."""
import ctypes as C, json, sys, time
from ctypes import wintypes as W

MODEL = 8
mm = C.WinDLL('winmm')


class HDR(C.Structure):
    _fields_ = [('lpData', C.c_void_p), ('dwBufferLength', W.DWORD), ('dwBytesRecorded', W.DWORD),
                ('dwUser', C.c_size_t), ('dwFlags', W.DWORD), ('lpNext', C.c_void_p),
                ('reserved', C.c_size_t), ('dwOffset', W.DWORD), ('dwReserved', C.c_size_t * 8)]


class INCAPS(C.Structure):
    _fields_ = [('m', W.WORD), ('p', W.WORD), ('v', W.UINT), ('name', W.WCHAR * 32), ('sup', W.DWORD)]


class OUTCAPS(C.Structure):
    _fields_ = [('m', W.WORD), ('p', W.WORD), ('v', W.UINT), ('name', W.WCHAR * 32), ('tech', W.WORD),
                ('voices', W.WORD), ('notes', W.WORD), ('mask', W.WORD), ('sup', W.DWORD)]


MHDR_DONE = 1


def build(cmd1, cmd2, args=(0, 0, 0, 0), payload=b'', model=MODEL):
    b = bytearray([0xF0, 0, 0x21, 0x24, model, 0, cmd1, cmd2, *args, 0, 0, 0, 0]) + bytes(payload) + b'\0\xF7'
    c = 0
    for x in b[:-2]:
        c ^= x
    b[-2] = c & 0x7F
    return bytes(b)


class Port:
    def __enter__(self):
        ins, outs = [], []
        for i in range(mm.midiInGetNumDevs()):
            c = INCAPS(); mm.midiInGetDevCapsW(i, C.byref(c), C.sizeof(c)); ins.append(c.name)
        for i in range(mm.midiOutGetNumDevs()):
            c = OUTCAPS(); mm.midiOutGetDevCapsW(i, C.byref(c), C.sizeof(c)); outs.append(c.name)
        ii = next(i for i, n in enumerate(ins) if n.startswith('Morningstar'))
        oi = next(i for i, n in enumerate(outs) if n.startswith('Morningstar'))
        self.hin, self.hout = C.c_void_p(), C.c_void_p()
        r = mm.midiInOpen(C.byref(self.hin), ii, None, None, 0)
        if r:
            raise SystemExit(f'MIDI in busy (error {r}): close the editor tab or Chrome')
        r = mm.midiOutOpen(C.byref(self.hout), oi, None, None, 0)
        if r:
            mm.midiInClose(self.hin)
            raise SystemExit(f'MIDI out busy (error {r}): close the editor tab or Chrome')
        self.bufs = [C.create_string_buffer(8192) for _ in range(16)]
        self.hdrs = [HDR(lpData=C.cast(b, C.c_void_p), dwBufferLength=8192) for b in self.bufs]
        for h in self.hdrs:
            mm.midiInPrepareHeader(self.hin, C.byref(h), C.sizeof(h))
            mm.midiInAddBuffer(self.hin, C.byref(h), C.sizeof(h))
        self.q, self.part = [], b''
        mm.midiInStart(self.hin)
        return self

    def __exit__(self, *a):
        mm.midiInStop(self.hin); mm.midiInReset(self.hin)
        for h in self.hdrs:
            mm.midiInUnprepareHeader(self.hin, C.byref(h), C.sizeof(h))
        mm.midiInClose(self.hin); mm.midiOutClose(self.hout)

    def send(self, d):
        s = C.create_string_buffer(d, len(d))
        h = HDR(lpData=C.cast(s, C.c_void_p), dwBufferLength=len(d), dwBytesRecorded=len(d))
        mm.midiOutPrepareHeader(self.hout, C.byref(h), C.sizeof(h))
        if mm.midiOutLongMsg(self.hout, C.byref(h), C.sizeof(h)):
            raise RuntimeError('midiOutLongMsg failed')
        t = time.time()
        while not h.dwFlags & MHDR_DONE and time.time() - t < 5:
            time.sleep(.001)
        mm.midiOutUnprepareHeader(self.hout, C.byref(h), C.sizeof(h))

    def poll(self):
        for h in self.hdrs:
            if h.dwFlags & MHDR_DONE:
                self.part += C.string_at(h.lpData, h.dwBytesRecorded)
                h.dwBytesRecorded = 0
                h.dwFlags &= ~MHDR_DONE
                mm.midiInAddBuffer(self.hin, C.byref(h), C.sizeof(h))
        while b'\xF7' in self.part:
            i = self.part.index(b'\xF7')
            self.q.append(self.part[:i + 1])
            self.part = self.part[i + 1:]

    def recv(self, timeout):
        t = time.time()
        while time.time() - t < timeout:
            self.poll()
            if self.q:
                return self.q.pop(0)
            time.sleep(.001)
        return None

    def drain(self, quiet=.4):
        out = []
        while (f := self.recv(quiet)) is not None:
            out.append(f)
        return out


def rows(p):
    i, out = 0, []
    while i + 3 <= len(p) and p[i] == 0x7F:
        out.append((p[i + 1], p[i + 3:i + 3 + p[i + 2]]))
        i += 3 + p[i + 2]
    return out


def row(tag, d): return bytes([0x7F, tag, len(d)]) + bytes(d)
def ascii32(s): return s.encode('ascii', 'replace')[:32].ljust(32, b' ')
def text(b): return b.decode('ascii', 'replace').rstrip(' ')


COLORS = ('ledColor', 'ledToggleColor', 'ledShiftColor', 'backgroundColor', 'nameColor', 'nameToggleColor',
          'nameShiftColor', 'toggleBackgroundColor', 'shiftBackgroundColor')


def enc_preset(p, bank, num, is_exp):
    o = row(0, [bank, num, int(is_exp), 0])
    for m in p['msgArray']:   # write order: channel, action, toggle (dumps use action, toggle, channel)
        d = m['data']
        o += row(1, [m['m'], m['t'], d[0], d[1], d[2], m['c'], m['a'], m['tg'], *d[3:18]])
    cfg = bytearray(32)
    cfg[0:4] = [int(p['toToggle']), int(p['toBlink']), int(p['toMsgScroll']), p['toggleGroup']]
    for i, k in enumerate(COLORS):
        cfg[4 + i] = p.get(k) or 0
    return (o + row(2, ascii32(p['shortName'])) + row(3, ascii32(p['toggleName'])) + row(4, ascii32(p['longName']))
            + row(5, cfg) + row(6, ascii32(p['shiftName'])))


def dec_preset(pl):
    p = {'msgArray': [None] * 32}
    head = None
    for tag, d in rows(pl):
        if tag == 0:
            head = d
        elif tag == 1:
            p['msgArray'][d[0]] = {'data': list(d[2:5]) + list(d[8:23]), 'm': d[0], 'c': d[7], 't': d[1], 'a': d[5], 'tg': d[6]}
        elif tag == 2:
            p['shortName'] = text(d)
        elif tag == 3:
            p['toggleName'] = text(d)
        elif tag == 4:
            p['longName'] = text(d)
        elif tag == 6:
            p['shiftName'] = text(d)
        elif tag == 5:
            p.update(toToggle=bool(d[0]), toBlink=bool(d[1]), toMsgScroll=bool(d[2]), toggleGroup=d[3])
            for i, k in enumerate(COLORS):
                p[k] = d[4 + i]
    return head, p


def enc_meta(b, bank):
    o = row(0, [bank]) + row(1, [int(b['bankClearToggle']), int(b['toDisplay']), b['backgroundColor'], b['textColor'],
                                 int(b['isColorEnabled']), b['pageLimit'], 0, 0])
    for m in b['bankMsgArray']:
        d = m['data']
        o += row(2, [m['m'], m['t'], d[0], d[1], d[2], m['c'], m['a'], m['tg'], *d[3:9]])
    return o + row(3, ascii32(b['bankName'])) + row(4, ascii32(b['bankDescription']))


def dec_meta(pl):
    b = {'bankMsgArray': [None] * 32}
    for tag, d in rows(pl):
        if tag == 0:
            b['bankNumber'] = d[0]
        elif tag == 1:
            b.update(bankClearToggle=bool(d[0]), toDisplay=bool(d[1]), backgroundColor=d[2], textColor=d[3],
                     isColorEnabled=bool(d[4]), pageLimit=d[5])
        elif tag == 2:
            b['bankMsgArray'][d[0]] = {'data': list(d[2:5]) + list(d[8:14]) + [0] * 9, 'm': d[0], 'c': d[5], 't': d[1], 'a': d[6], 'tg': d[7]}
        elif tag == 3:
            b['bankName'] = text(d)
        elif tag == 4:
            b['bankDescription'] = text(d)
    return b


class Session:
    def __init__(self, port): self.p = port

    def __enter__(self):
        self.p.send(build(0, 27))
        time.sleep(1.2)
        self.opened = self.p.drain()   # the session-open avalanche (only source of the resistor ladder 03 28)
        return self

    def __exit__(self, *a):   # always leave edit mode, also after an error
        self.p.send(build(0, 28))
        time.sleep(.3 + getattr(self, 'settle', 0))

    def select(self, bank):
        self.p.send(build(0, 0x1F, (bank, 1, 0, 0)))
        self.p.drain()

    def read(self):
        self.p.send(build(7, 0, (50, 0, 0, 0), model=0))
        b, main, exp, t = None, [None] * 24, [None] * 4, time.time()
        while time.time() - t < 30:
            f = self.p.recv(10)
            if f is None:
                raise RuntimeError('no frame from the MC8 during bank read')
            self.p.send(build(0, 127, (f[-2], 0, 0, 0)))
            c, pl = (f[6], f[7]), f[16:-2]
            if c == (7, 0) and f[8] == 1:
                if b is None or None in main or None in exp:
                    raise RuntimeError('incomplete bank read')
                b['presetArray'], b['expPresetArray'] = main, exp
                return b
            if c == (7, 2):
                b = dec_meta(pl)
            elif c == (7, 1):
                h, p = dec_preset(pl)
                (exp if h[2] else main)[h[1]] = p
        raise RuntimeError('bank read timed out')

    def config(self):
        self.p.send(build(0, 36))
        for f in self.p.drain(.8):
            if f[6] == 3 and f[7] == 0x21:
                return bytearray(f[16:48])
        raise RuntimeError('no general settings reply')

    def upload_config(self, d):
        self.p.send(build(4, 0)); time.sleep(.1)
        self.p.send(build(4, 2, payload=d)); time.sleep(.1)
        self.p.send(build(4, 1)); time.sleep(1.5); self.p.drain()

    def settings(self, names=None):
        from mc8set import SECTIONS, dec
        fr = list(self.opened)
        for n in names or SECTIONS:
            if SECTIONS[n][0]:
                self.p.send(build(0, SECTIONS[n][0])); fr += self.p.drain(.8)
        got = {}
        for f in fr:
            if f[6] == 3: got[f[7]] = list(f[16:-2])   # last reply wins
        return {n: {'raw': got[r], 'decoded': dec(n, got[r])} for n, (_, r, _) in SECTIONS.items()
                if r in got and (names is None or n in names)}

    def upload(self, cmd2, d):
        self.p.send(build(4, 0)); time.sleep(.1)
        self.p.send(build(4, cmd2, payload=bytes(d))); time.sleep(.1)
        self.p.send(build(4, 1)); time.sleep(1.5); self.p.drain()
        self.settle = 8   # the USB port refuses sends for a few seconds after a settings write

    def wait(self, arg):
        t = time.time()
        while time.time() - t < 10:
            f = self.p.recv(.5)
            if f and f[6] == 7 and f[7] == 0 and f[8] == arg:
                return
        raise RuntimeError(f'MC8 did not answer {arg}')

    def restore(self, b, bank):
        self.p.send(build(7, 0, (48, 0, 0, 0))); self.wait(33)
        self.p.send(build(7, 16, payload=enc_meta(b, bank))); self.wait(33)
        for i, q in enumerate(b['presetArray']):
            self.p.send(build(7, 17, (i, 0, 0, 0), enc_preset(q, bank, i, False))); self.wait(33)
        for i, q in enumerate(b['expPresetArray']):
            self.p.send(build(7, 18, (i, 0, 0, 0), enc_preset(q, bank, i, True))); self.wait(33)
        self.p.send(build(7, 0, (49, 0, 0, 0))); self.wait(17)


def norm(b):
    def msg(m, n=18): return [m['m'], m['t'], m['c'], m['a'], m['tg'], *m['data'][:n]]

    def pre(p):
        return {'names': [p[k].rstrip() for k in ('shortName', 'toggleName', 'longName', 'shiftName')],
                'flags': [bool(p['toToggle']), bool(p['toBlink']), bool(p['toMsgScroll']), p['toggleGroup']],
                'colors': [p.get(k) or 0 for k in COLORS], 'msgs': [msg(m) for m in p['msgArray']]}
    return {'name': b['bankName'].rstrip(), 'desc': (b.get('bankDescription') or '').rstrip(),
            'cfg': [bool(b['bankClearToggle']), bool(b['toDisplay']), b['backgroundColor'], b['textColor'],
                    b['pageLimit']],   # isColorEnabled reads back False whatever was written
            'bankmsgs': [msg(m, 9) for m in b['bankMsgArray']],
            'presets': [pre(p) for p in b['presetArray']], 'exp': [pre(p) for p in b['expPresetArray']]}


def compare(a, b):
    x, y, out = norm(a), norm(b), []
    for k in ('name', 'desc', 'cfg', 'bankmsgs'):
        if x[k] != y[k]:
            out.append(f'{k}: {x[k]} vs {y[k]}'[:200])
    for g in ('presets', 'exp'):
        for i, (p, q) in enumerate(zip(x[g], y[g])):
            for k in p:
                if p[k] != q[k]:
                    if k == 'msgs':
                        n = next(j for j in range(32) if p[k][j] != q[k][j])
                        out.append(f'{g}[{i}] slot {n}: {p[k][n]} vs {q[k][n]}')
                    else:
                        out.append(f'{g}[{i}].{k}: {p[k]} vs {q[k]}')
    return out


def load_bank(f):
    d = json.load(open(f, encoding='utf-8'))
    return d['data'].get('bank') or d['data']['bankArray'][0]


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    if a[0] == 'compare':
        r = compare(load_bank(a[1]), load_bank(a[2]))
        print('identical' if not r else '\n'.join(r[:40]))
        return
    with Port() as p:
        if a[0] == 'info':
            p.send(build(0x70, 0x32)); p.send(build(0x70, 0x30))
            for f in p.drain(1):
                print(f.hex(' ')[:60], repr(bytes(x for x in f[16:-2] if 32 <= x < 127)))
        elif a[0] == 'read':
            bank = int(a[1]) - 1
            with Session(p) as s:
                s.select(bank)
                b = s.read()
            if b['bankNumber'] != bank:
                raise SystemExit(f"read bank {b['bankNumber'] + 1}, wanted {bank + 1}")
            json.dump({'dumpType': 'singleBank', 'data': {'bank': b}}, open(a[2], 'w', encoding='utf-8'))
            print('read', bank + 1, repr(b['bankName']), [q['shortName'] for q in b['presetArray'] if q['shortName'] != 'EMPTY'])
        elif a[0] == 'write':
            if '--yes' not in a:
                raise SystemExit('add --yes: this writes to the MC8 flash')
            b = load_bank(a[1])
            bank = b['bankNumber']
            with Session(p) as s:
                s.select(bank)
                s.restore(b, bank)
                time.sleep(1.5)
                s.select(bank)
                back = s.read()
            r = [f"read back bank {back['bankNumber'] + 1}"] if back['bankNumber'] != bank else []
            r += compare(b, back)
            print(f"bank {bank + 1} {b['bankName']!r}:", 'written, read back identical' if not r else 'DIFFERENT\n' + '\n'.join(r[:40]))
            if r:
                sys.exit(1)
        elif a[0] == 'setting':
            if '--yes' not in a:
                raise SystemExit('add --yes: this writes to the MC8 flash')
            with Session(p) as s:
                before = s.config()
                d = bytearray(before)
                d[int(a[1])] = int(a[2])
                s.upload_config(d)
                after = s.config()
            print('before', list(before)); print('after ', list(after))
            if after != d:
                sys.exit('read back differs')
        elif a[0] == 'settings':
            from mc8set import SECTIONS, enc
            if a[1] == 'read':
                with Session(p) as s:
                    d = s.settings()
                json.dump(d, open(a[2], 'w'), indent=1)
                print('read', ', '.join(f"{k} {len(v['raw'])}" for k, v in d.items()))
                return
            if '--yes' not in a:
                raise SystemExit('add --yes: this writes to the MC8 flash')
            with Session(p) as s:
                if a[1] == 'write':
                    name, want = a[3], json.load(open(a[2]))[a[3]]['decoded']
                else:   # set
                    path = a[2].split('.'); name = path[0]
                    want = s.settings([name])[name]['decoded']
                    o = want
                    for k in path[1:-1]: o = o[int(k) if isinstance(o, list) else k]
                    k = path[-1]; o[int(k) if isinstance(o, list) else k] = int(a[3])
                s.upload(SECTIONS[name][2], enc(name, want)); time.sleep(.5)
                s.opened = s.p.drain() if name != 'ladder' else s.opened
                back = s.settings([name]) if name != 'ladder' else None
            if back is None:
                print('ladder written (read back needs a new session: run settings read)'); return
            ok = back[name]['decoded'] == want
            print(name, 'written, read back identical' if ok else 'DIFFERENT ' + json.dumps(back[name]['decoded'])[:600])
            if not ok:
                sys.exit(1)
        else:
            print(__doc__)


if __name__ == '__main__':
    main()
