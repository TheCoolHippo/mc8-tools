# mc8-tools

Scripts to read, edit and write **Morningstar MC8 Pro** banks without the web editor.

- `mc8bak.mjs`: offline editor for the `.json` backups from the Morningstar Editor (Controller Backup).
  No install, plain Node. Run it with no arguments for the command list.
- `mc8msg.mjs`: encoder/decoder for the 18-byte message slots (CC, PC, Bank Jump, Toggle Page, Set Toggle, Trigger...).
- `mc8usb.py`: direct USB connector (Windows, winmm): read and write banks, compare with a file, no browser.
- `FORMAT.md`: the backup file format, field by field, with what was verified on hardware (firmware 3.13.6, section 10).

```
node mc8bak.mjs check backup.json
node mc8bak.mjs bank backup.json 1
node mc8bak.mjs msg in.json out.json 1 B 1 "cc value scroll" a=press c=2 scroll=dec+send counter=0 cc=20 step=16
node mc8bak.mjs export out.json bank1.json 1
python mc8usb.py read 1 bank1.json
```
The hash is recalculated on every save. Writes over USB go to flash: back up first, and close the web editor
(one program at a time on the port).

## Credits
USB session protocol: benemon/morningstar-sdk. Not affiliated with Morningstar Engineering.
Companion repo for the Fractal FM3: [fm3-syx-editor](https://github.com/TheCoolHippo/fm3-syx-editor).
