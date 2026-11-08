# mc8-tools

Scripts to read, edit and write **Morningstar MC8 Pro** banks without the web editor.

- `mc8bak.mjs`: offline editor for the `.json` backups from the Morningstar Editor (Controller Backup).
  No install, plain Node. Run it with no arguments for the command list.
- `mc8msg.mjs`: encoder/decoder for the 18-byte message slots (CC, PC, Bank Jump, Toggle Page, Set Toggle, Trigger...).
- `mc8usb.py`: direct USB connector (Windows, winmm): read and write banks, compare with a file, no browser.
  Also reads and writes all 10 global settings sections (`settings read|write|set`).
- `mc8set.py`: codec for those sections (decoded names, and the write layouts that differ from the dumps).
- `FORMAT.md`: the backup file format, field by field, with what was verified on hardware (firmware 3.13.6, section 10).

```
node mc8bak.mjs check backup.json
node mc8bak.mjs bank backup.json 1
node mc8bak.mjs msg in.json out.json 1 B 1 "cc value scroll" a=press c=2 scroll=dec+send counter=0 cc=20 step=16
node mc8bak.mjs export out.json bank1.json 1
python mc8usb.py read 1 bank1.json
python mc8usb.py settings read settings.json
python mc8usb.py settings set config.brightness 5 --yes
python mc8usb.py settings write settings.json omniports --yes
```

## Global settings
| Section | Read (00 cmd → reply 03 xx) | Write (04 xx) | Notes |
|---|---|---|---|
| config (32 bytes: MIDI thru per port, channel, long press, relays, brightness, fonts...) | 36 → 21 | 02 | same layout both ways |
| channels (16 names, remap, port) | 40 → 20 | 03 | row-framed |
| arrangement (bank order) | 41 → 22 | 04 | |
| waveform engines | 37 → 24 | 05 | write drops the engine number |
| sequencer engines | 38 → 25 | 06 | |
| scroll counters | 39 → 26 | 07 | |
| omniports (4 entries x 11) | 42 → 23 | 08 | write drops the leading count |
| event processor (16 rules) | 45 → 27 | 0A | |
| resistor ladder (aux switches) | session open only → 28 | 0B | dump is one byte short |
| MIDI clock slots | 80 → 29 | 0C | write drops the leading reserved byte |

Verified on firmware 3.13.6: every section above except the ladder, the arrangement, the sequencer, the scroll counters and the event processor was written and read back identical; `config` was also changed and restored. After a
settings write the USB port refuses sends for a few seconds; the script waits.
The hash is recalculated on every save. Writes over USB go to flash: back up first, and close the web editor
(one program at a time on the port).

## Credits
USB session protocol: benemon/morningstar-sdk. Not affiliated with Morningstar Engineering.
Companion repo for the Fractal FM3: [fm3-syx-editor](https://github.com/TheCoolHippo/fm3-syx-editor).
