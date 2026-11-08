# Morningstar MC8 Pro backup JSON: format spec

Purpose: enough detail to write an offline editor for MC8 Pro backup files.
Date: 2026-11-05. Static analysis only: no hardware touched, nothing executed from the bundle or the SDK.

## 0. Sources and conventions

| Tag | Source |
|---|---|
| `main.js@N` | Official editor bundle, character offset N in the decoded file. For a component it is the exact `selectors:` literal, which comes after the class body. Other offsets point at or near the named code. Identifiers such as `xr`, `ln`, `Ki` are minifier names and change between builds; string literals and selectors are the stable anchors. |
| `<selector>` | Angular component in the bundle that edits that message type, e.g. `<cc-scroll>`. |
| SDK | `benemon/morningstar-sdk`, `pkg/mc8pro/...` |
| testdata | SDK `testdata/all-banks.json` (real MC8 Pro, 128 banks, editor-downloaded) and `bank-guitar-live.json` |
| mc6-virtual | `ivnvxd/mc6-virtual` `Commands.swift` (independent reverse engineering, used as a cross-check) |
| FootSmart | `jgateley/FootSmart` `backup_grammar.py` (cross-check of the schema) |

Marks: **[code]** read directly in the editor's code. **[verified]** additionally checked against real files. **[inferred]** my deduction, not stated by any source. **[unknown]** see section 8.

`data[n]` is 0-based: `data[0]` is what the editor calls `data1`, `data[17]` is `data18`.

Model IDs (`Ye`, main.js@1623870): MC6MK2 3, MC8 4, MC3 5, MC6PRO 6, ML10X 7, **MC8PRO 8**, MC4PRO 9, ML5R 10, MC6PROMK2 11, LIVE_MODE 127.

MC8 Pro dimensions (`setModelParams` main.js@3982841 and @3999134; counts confirmed by testdata):
128 banks, 24 presets (A..X), 4 expression presets, 32 messages per preset, 32 bank messages, 18 data bytes per message, names 32 characters, 8 waveform engines, 8 sequencer engines, 16 scroll counters, 16 MIDI clock slots, 16 MIDI converter events, 16 resistor ladder switches, 4 Omniports, 2 relay ports.

## 1. File envelope

```
{ schemaVersion: 1, dumpType, deviceModel: 8, downloadDate, hash, data, description }
```

| Key | Value |
|---|---|
| `schemaVersion` | Always 1 when written; only tested for non-null on read |
| `dumpType` | `"allBanks"` (`data.bankArray[128]` + `data.controller_settings`), `"singleBank"` (`data.bank`). A class at main.js@5832587 also writes `"full"`; the restore flow has no branch for it **[code]** |
| `deviceModel` | Number, 8 |
| `downloadDate` | ISO date string, not used on read |
| `hash` | Signed 32-bit integer, see section 7 |
| `description` | String; in testdata it appears after `data` |

`singleBank` files with `controller_settings` are possible at write time (`ra.getJSON`, main.js@4864436) but the restore code ignores it there.

Other JSON files the editor produces, for reference: single preset (a bare preset object, recognized by `msgArray` + `isExp`) and `controller_settings_all.json` (`{type:"controller_settings_all",data:{...}}`).

## 2. Message object

```json
{"data":[18 ints],"m":0,"c":1,"t":0,"a":0,"tg":2,"mi":""}
```

This key order is the editor's output (class `ln`, loader at main.js@3967474). An empty slot is exactly the line above with `m` set to its index.

| Key | Meaning |
|---|---|
| `data` | Array of 18 integers 0..127. The UI setters mask to 7 bits; the JSON loader does not, so an out-of-range value reaches the sysex builder unmasked **[code]** |
| `m` | Message number, 0..31, equals the array index. Sent to the device as the slot number, so it must match the index **[code]** `getSysexArray` |
| `c` | Channel field, **stored 1-based** (1..16) when it is a MIDI channel. Default 1. Many types reuse it, see 2.1 |
| `t` | Message type. **Three separate numberings**: preset (3), bank (4), expression (5) |
| `a` | Action, preset messages: 2.2; bank messages: 2.3; expression messages: 0 |
| `tg` | Toggle position: 0 Pos 1, 1 Pos 2, 2 Both (default), 3 Shift (main.js@4768223 `getToggleName`) |
| `mi` | Message description, editor-side text, UI limit 64 chars. **Not sent to the device** (absent from `getSysexArray`) and blank on anything read from the device, so a restored `mi` is lost on the next download **[code]**. It is still part of the hashed text |

### 2.1 What `c` means per type

`setChannel` rejects 0 and values over 16 (main.js@3969887), but the JSON loader accepts anything.

| Use of `c` | Types (preset numbering unless noted) |
|---|---|
| True MIDI channel 1..16 | 1 PC, 2 CC, 3/4 Note, 8/9 PC Scroll, 19/20 Strymon, 21 Axe Tuner, 26 Waveform, 28 Kemper, 31 Sequencer, 32 CC Scroll, 33 PC Scroll, 37 Axe Integration. Editor helper `cKe` (main.js@3420820) lists most of them. Expression types 1, 2, 3, 6..13 |
| Reused: Set Toggle (15) | `c-1` = toggle action (table in 3.15) |
| Reused: PC Multi Channel (34) | `c-1` bits 0-1 = channels 15 and 16 of the mask |
| Reused: Keystroke (35) | Modifier 2 enum, 1..11 |
| Reused: ML10X (39) | Command, 1..12 (table in 3.39) |
| Reused: Preset Rename (44) | `c-1`: bit 0 load original name, bits 1-3 which name |
| Meaningless, leave 1 | All other types. mc6-virtual treats a non-1 `c` on Engage as having no effect. testdata has one type 24 with c=2, see below |

### 2.2 Preset actions (`a`)

`actionPresetTypes`, main.js@4078066: 0 No Action, 1 Press, 2 Release, 3 Long Press, 4 Long Press Release, 5 Double Tap, 6 Double Tap Release, 7 Long Double Tap, 8 Long Double Tap Release, 9 Release All, 10 Long Press Scroll, 11 On Disengage, 12 On First Engage, 13 On First Engage (send only this).

### 2.3 Bank message events (`a` in `bankMsgArray`)

`eventBankPresetTypesPro`: 0 Nothing, 1 On Enter Bank, 2 On Exit Bank, 3 On Enter Bank - Execute Once Only, 4 On Exit Bank - Execute Once Only, 5/6/11/12 On Enter Bank - Page 1/2/3/4, 7/8/9/10 On Toggle Page - Page 1/2/3/4.

Bank messages have no toggle position in the UI; `tg` stays 2 **[inferred]**.

## 3. Preset message types

Numbering `xr`, main.js@3417300. Unlisted `data` indexes are unused by the form and should stay 0. "No parameters" means no form exists in `msg-parameters`.

### 0 Empty, and types with no parameters

| t | Name | Note |
|---|---|---|
| 0 | Empty | |
| 10 / 11 | Bank Up / Bank Down | No parameters |
| 12 | Bank Change Mode | No parameters |
| 19 / 20 | Strymon Bank Up / Down | `c` only (`<generic-channel>`) |
| 22 | Toggle Preset | No parameters |
| 24 | MIDI Clock Tap | No parameters (`<midiclocktap>` main.js@4716459). The one real example in testdata still holds `data:[44,64,...]`, `c:2`: it looks like leftovers of an earlier CC **[inferred]**, so unused fields can be non-zero and must be preserved on round trip |
| 28 | Kemper Tuner | `c` only |
| 30 | Set Display | In the enum, but not offered in the type menu and has no form **[unknown]** |
| 38 | NRPN | Same as 30 **[unknown]** |

### 1 PC, `<pcmsg>` main.js@4528341

| data | Field | Values |
|---|---|---|
| 0 | PC number | 0..127 |
| 2 | Send Type | 0 Send Program Change, 122 Last sent PC number, 123 Send last sent PC and decrease, 124 Send last sent PC and increase, 125 Decrease last sent PC and send, 126 Increase last sent PC and send, 127 Send PC to all channels |

The form resets `data[2]` to 0 if it holds any other value. `data[0]` is shown only for 0 or 127, `c` only below 127.

### 2 CC, `<ccmsg>` main.js@4519761

| data | Field | Values |
|---|---|---|
| 0 | CC number | 0..127 |
| 1 | CC value | 0..127 (hidden when bit 0 of data[2] is set) |
| 2 | Value source | bit 0: use the current expression pedal position instead of data[1]. bits 1-2: expression port 0..3 |

testdata: `{t:2, data:[39,64,...], c:2, a:1}` **[verified]** present; the file does not prove what the device sent.

### 3 Note On, 4 Note Off, `<note-message>` main.js@4531727

| data | Field | Values |
|---|---|---|
| 0 | Note | 0..127 |
| 1 | Velocity | 0..127 |
| 2 | All Notes | Note Off only: 1 sends Note Off to all notes |

### 5 Real Time, `<realtime>`

`data[0]`: 0 Nothing, 1 Start, 2 Stop, 3 Continue.

### 6 SysEx, `<sysex>` main.js@4537310 and `preset-sysex-utility-dialog` main.js@5236138

A SysEx string spans consecutive messages of type 6:

| Message | data[0] | data[1..17] |
|---|---|---|
| First | Length N of the string, excluding F0 and F7 | First 17 bytes |
| Each following | Next byte | Next 17 bytes |
| Last | | Padded with 0 |

- The utility writes every message with `a=1`, `tg=2`, `c=1`, `m` consecutive from the chosen start slot.
- F0 and F7 are not stored: the utility skips a leading 240 and trailing 247, and treats any other value above 127 as invalid **[code]**. That the device adds them back is **[inferred]**.
- Form tooltip on `data[0]`: length if this is the first message, otherwise a SysEx value.
- Length limits: `onApply` (main.js@5234485) allows `numMidiMessages*numMsgParameter-1` = 575 bytes, but `checkTextValue` compares with `maxLength = numMidiMessages*4-1` = 127 (main.js@5233666) and flags longer text invalid. So the utility effectively stops at 127 bytes on a Pro **[inferred]** from the valid flag. Whether the firmware accepts more through hand-built JSON is **[unknown]**.
- The slots check uses `ceil(N/18)`, which ignores the length byte, so N = 18k still needs one more message than it reserves **[code]**.

### 7 MIDI Clock, `<midiclock>` main.js@4546400

| data | Field | Values |
|---|---|---|
| 0, 1 | BPM | `bpm = data[0]*100 + data[1]`, 0..1000. Exception: type 5 |
| 0 | Slot | Type 5 only: slot 0..15 (`data[1]` then 1) |
| 2 | Flags | bit 0 and bits 4-5: function type, see below. bit 1: Use Current BPM Setting. bits 2-3: decimal, 0 +0, 1 +0.25, 2 +0.50, 3 +0.75 |

The enum calls this `M_CLOCKTAP`, but the `msg-parameters` switch sends it to the `<midiclock>` form; the separate tap message is type 24. `clockType = (data[2] & 1) | ((data[2] >> 4 & 3) << 1)`: 0 Start MIDI Clock, 1 MIDI Clock Menu, 2 Load BPM from next Slot, 3 Load BPM from previous Slot, 4 Tap Tempo, 5 Load BPM from selected Slot.

Stop MIDI Clock is encoded as `data[0..2] = 0` (bpm 0). Choosing type 1 writes BPM 120 (data 1, 20). A total over 1000 is displayed as 120.

### 8 / 9 PC Scroll Up / Down (deprecated), `<pc-scroll>` main.js@4550734

| data | Field |
|---|---|
| 0 | bits 0-3 counter 0..15 (labelled 0..F). bit 4: increment/decrement enabled |
| 1 | Lower limit |
| 2 | Upper limit |

### 13 Bank Jump, `<set-bank>` main.js@4568821

| data | Field | Values |
|---|---|---|
| 0 | Bank | 0..127, used only when data[1]=0 |
| 1 | Go to last used bank | 0 No, 127 Last used Bank Only, 126 Last used Bank / Page, 125 Last used Bank / Page or Page. The form zeroes 1..124 |
| 2 | Flags | Page = `(bit 3 << 1) | bit 0`, 0..3 = page 1..4. bit 1: **clear** = Ignore Bank Preset On Enter. bit 2: **clear** = Ignore Bank Preset On Exit |

A newly chosen Bank Jump gets `data[2]=6` (page 1, nothing ignored). Note the inverted bits. mc6-virtual agrees on the page encoding. The form hides page values 2 and 3 only on non-Pro models.

### 14 Toggle Page, `<toggle-page>` main.js@4715024

`data[0]`: 1 Page Up, 2 Page Down, 3..6 Go to Page 1..4.

### 15 Set Toggle, `<app-set-toggle>` main.js@3963080

| Field | Encoding |
|---|---|
| Action | `c-1` & 15: 0 Dis-engage Toggle, 1 Engage Toggle, 2 Toggle, 3 Shift, 4 Unshift, 5 Shift+, 6 Set Toggle, 7 Shift Hold, 8 Engage Toggle Last (Beta), 9 Dis-engage Toggle Last (Beta) |
| data[0] | Preset mask bits 0-6: presets A..G |
| data[1] | bits 0-6: H..N |
| data[2] | bits 0-6: O..U |
| data[3] | bits 0-2: V..X |

The encoder also has room in data[3] bits 3-6 and data[4] bits 0-3 for presets 25..32, unused with 24 presets. mc6-virtual reads the same mask. testdata fits this: preset E holds `c:2, data[0]=16` (engage E) and `c:1, data[0]=32` (disengage F), preset F the mirror image, a mutual exclusion pair **[inferred reading]**.

### 16 MIDI Thru, `<app-midi-thru>`

`data[0]`: 0 MIDI Thru Off, 1 MIDI Thru On.

### 17 Select Exp Message, `<app-select-exp>` main.js@4579688

Selects which messages of an expression preset are active. Bit `n` below is message number n (0-based).

| data | Field |
|---|---|
| 0 | bits 0-1: expression input 0..3. bits 2-6: messages 27..31 |
| 1 | bits 0-6: messages 20..26 |
| 2 | bits 0-6: messages 13..19 |
| 3 | bits 0-6: messages 6..12 |
| 4 | bits 0-5: messages 0..5 |

mc6-virtual computes the same mask.

### 18 Looper Mode, `<looper-mode>` main.js@4585678

| data | Field |
|---|---|
| 0 | bits 0-1: 0 Toggle, 1 Engage, 2 Dis-engage. bit 2: apply to selected switches only. bit 3: disable looper message on LCD |
| 1 | bits 0-6: switches A..G |
| 2 | bit 0: switch H |

### 21 AxeFX Tuner, `<axefx-tuner>` main.js@4686126

`data[0]` model: 0 Axe-Fx III, 1 FM3, 2 FM9. `c` Fractal channel. The form's note says the device must have Tuner mapped to CC 15 and Send Realtime Sysex on.

### 23 Delay, `<delaymsg>` main.js@4588328

`data[0]` = delay / 10 ms. Range 0..126, so 0..1260 ms (table `_2e`, label "Delay (ms)"). mc6-virtual: `ms = data[0]*10`.

### 25 Song Position, `<songposition>`

`beats = data[0] << 7 | data[1]`, 0..16383.

### 26 CC Waveform, `<ccmsgwaveform>` main.js@4604164 (Pro branch)

| data | Field | Values |
|---|---|---|
| 0 | CC number | Start only |
| 1 | Flags | bit 6: 1 Start, 0 Stop. bit 5: 1 Perpetual, 0 Once Only. bits 3-4: speed multiplier x1/x2/x4/x8. bit 2: Follow MIDI Clock BPM. The Pro form writes the low bits as constant 3 on Start, 7 on Stop; their meaning is **[unknown]** |
| 2 | Speed | Not following BPM: cycles per minute minus 1. Following BPM: note division, 8 4 Whole, 7 3 Whole, 6 2 Whole, 0 Whole, 1 Half, 2 Quarter, 3 Eighth, 4 Triplets, 5 Sixteenth |
| 3 | Reverse | bit 0 |
| 4 | Engine | 0..7, 15 All Engines (All offered on Stop only) |

### 27 Engage Preset, `<engage-preset>` main.js@4611936

| data | Field | Values |
|---|---|---|
| 0 | Bank | 0..127. When "Current Bank" is chosen it holds the bank number at edit time and is ignored |
| 1 | Preset | bits 0-4: 0..23 (A..X). bit 6: Current Bank |
| 2 | Action | Table `c$e`: 0 No Action, 1 Press, 2 Release, 3 Long Press, 4 Long Press Release, 5 Double Tap, 6 Double Tap Release, 7 Long Double Tap, 8 Long Double Tap Release, 9 Release All, 10 Long Press Scroll |

mc6-virtual resolves the bank the same way: bit 6 set means the message's own bank, otherwise data[0].

### 29 Song Select, `<song-select>`

`data[0]` song number 0..127.

### 31 Sequence Generator, `<ccmsg-sequencer>` main.js@4628090 (Pro branch)

| data | Field | Values |
|---|---|---|
| 0 | CC or PC number | |
| 1 | Flags | As type 26 |
| 2 | Speed | As type 26 |
| 3 | Reverse | bit 0, read by the class but no form control is visible |
| 4 | Engine | 0..7, 15 All Engines |
| 5 | Send Type | bit 0: 0 Control Change, 1 Program Change |

### 32 CC Value Scroll, `<cc-scroll>` main.js@4560968

| data | Field | Values |
|---|---|---|
| 0 | Counter and type | bits 0-3: counter 0..15. bits 4-6: scroll type: 0 Send only, 1 Increase and send, 2 Decrease and send, 3 Update only, 4 Reset only, 5 Increase only, 6 Decrease only |
| 1 | CC number, or for type 3 the Counter Value | 0..127, unused for 4, 5, 6 |
| 2 | Step and wrap | bits 0-5: step 1..63 (0 read as 1). bit 6: wrap-around. Used by 1, 2, 5, 6 |

`c` used for types 0..2. Counter ranges live in `scroll_counters` (section 6).

### 33 PC Number Scroll, `<pc-scroll-new>` main.js@4634715

| data | Field | Values |
|---|---|---|
| 0 | Counter and type | As type 32 |
| 1 | To Value | Type 3 only |
| 2 | Wrap | bit 0, **inverted**: 1 = No, 0 = Yes. Used by 1, 2, 5, 6. No step field |

`c` used for types 0..2.

### 34 PC Multi Channel, `<pc-multi-channel>` main.js@4639992

`data[0]` PC number. Channel mask, 16 bits: `data[1]` bits 0-6 = ch 1..7, `data[2]` bits 0-6 = ch 8..14, `c-1` bits 0-1 = ch 15, 16.

### 35 Keystroke, `<keystroke-message>` main.js@4643028

| Field | Encoding |
|---|---|
| data[0] | bits 0-3: Modifier 1. bits 4-6: action, 0 Press / Release, 1 Press, 2 Release |
| `c` | Modifier 2 |
| data[1], data[2] | Keystroke 1 and 2 |

A new Keystroke gets `data[0]=1`. Modifier values: 1 Nothing, 2 CTRL, 3 RIGHT CTRL, 4 SHIFT, 5 RIGHT SHIFT, 6 ALT, 7 RIGHT ALT, 8 WINDOWS/CMD, 9 RIGHT WINDOWS/CMD, 10 CTRL+SHIFT, 11 ALT+SHIFT.

Key values (`x$e`, main.js@3450468 is its `KEYPAD ASTERIX` entry): 0 Nothing, 1..26 A..Z, 27..35 digits 1..9, 36 digit 0, 37 ENTER, 38 ESC, 39 BACKSPACE, 40 TAB, 41 SPACE, 42 MINUS, 43 EQUAL, 44 LEFT BRACE, 45 RIGHT BRACE, 46 BACKSLASH, 47 SEMICOLON, 48 QUOTE, 49 TILDE, 50 COMMA, 51 PERIOD, 52 SLASH, 53 CAPS LOCK, 54..65 F1..F12, 66 PRINT SCREEN, 67 SCROLL LOCK, 68 PAUSE, 69 INSERT, 70 HOME, 71 PAGE UP, 72 DELETE, 73 END, 74 PAGE DOWN, 75 RIGHT ARROW, 76 LEFT ARROW, 77 DOWN ARROW, 78 UP ARROW, 79 NUM LOCK, 80 KEYPAD SLASH, 81 KEYPAD ASTERIX, 82 KEYPAD MINUS, 83 KEYPAD PLUS, 84 KEYPAD ENTER, 85..93 KEYPAD 1..9, 94 KEYPAD 0, 95 KEY MEDIA.

### 36 Utility, `<preset_utility>` main.js@4669435

`data[0]` selects the sub-function.

| data[0] | Sub-function | Parameters |
|---|---|---|
| 0 | Set Message Scroll Counter | data[1] preset 0..23. data[2] 127 Reset, 0..31 Msg 1..32 |
| 1 | Clear Global Preset Toggles | None |
| 2 / 3 | Increase / Decrease MIDI Clock BPM by 1 | None |
| 4 | Set Scroll Counter Values | data[1]: bits 0-3 counter, bits 4-6 type (5 Increase, 6 Decrease, 3 Update, 4 Reset). data[2]: bits 0-5 step, bit 6 wrap (5, 6). data[3]: Counter Value (3) |
| 5 | Set MIDI Output Mask | data[1]: "maskUntil", no form control, written 0 **[unknown]** purpose. Mask = `data[3] << 7 | data[2]`, bits below |
| 6 | Manage Preset Message Scroll | data[1]: 0 Do nothing, 1 Toggle Scroll Direction, 2 Toggle Scroll Direction and Execute, 3 Reverse Direction Once and Execute, 4 Set number of messages to scroll. data[2]: 1..8, for 4 only |
| 7 | Set Current Bank Background/Text Color | data[1] background, data[2] text (section 4.3, undimmed) |
| 8 | Set Current Preset Background/Text/Strip Color | data[1] background, data[2] text, data[3] strip |
| 9 | Set Selected Preset Background/Text/Strip Color | As 8, plus data[4] preset 0..23 |
| 10 | Delay LCD Refresh (Beta) | None |
| 11 / 12 | Enable / Disable Fast Step Mode (Beta) | None |

Output mask bits: 0 DIN, 1 USB port 1, 2..5 Omniport 1..4, 6 3.5mm, 7..9 USB ports 2..4, 10 USB Host. UI default is all on.

### 37 AxeFX Integration, `<axefx-integration>` main.js@4677614

| data | Field | Values |
|---|---|---|
| 0 | Type, offset high | bits 0-1: 0 Preset Select, 1 Scene Select, 2 Preset + Scene Select, 3 Effect Bypass (v3.14). bits 5-6: preset offset bits 7-8 |
| 1 | Offset low | Preset offset bits 0-6. Offset = "Preset Start From" (Axe III 0..383, FM3/FM9 0..511), types 0 and 2 |
| 2 | Fractal model | bits 0-1: 0 Axe-Fx III, 1 FM3, 2 FM9 |
| 3..10 | Effect per switch A..H | Effect enum, below. All 0 = auto-list from the current Fractal preset |

`c` = Fractal MIDI channel.

Effect enum (`R$e`, main.js@3466926): 0 (None), then four of each in this order starting at 1: Comp, GEQ, PEQ, Drive, Cab, Rev, Delay, MTap, Chorus, Flange, Rotary, Phaser, Wah, Formant, Vol, Trem, Pitch, Filter, Fuzz, Enh, Synth (so Comp 1 = 1, Drive 1 = 13, Synth 4 = 84). I did not read past 84 **[unknown]** whether the table continues.

In this build the effect slot panel is compiled to never display (its condition is constant false), though the class keeps the code and reads data[3..10]. Its correct behavior on hardware is **[unknown]**.

### 39 ML10X, `<ml10x-engage>` main.js@4695527

| Field | Encoding |
|---|---|
| `c` | Command: 1 Set Loops, 2 Engage Selected Loops, 3 Bypass Selected Loops, 4 Toggle Selected Loops, 6 Scroll Up, 7 Scroll Down, 8 Select Preset, 9 Set Output Cut/Restore, 10 Cut Output, 11 Restore Output, 12 Toggle Cut/Restore Output (9..12 Advanced Mode) |
| data[2] | Device ID: 0 Omni, 1..16 |
| data[0], data[1] | Commands 1..4, 9..12: 14-bit loop mask, `data[1] << 7 | data[0]`. Bits 0..13: A Tip, A Ring, B Tip, B Ring, C Tip, C Ring, D Tip, D Ring, E Tip, E Ring, Input Tip, Input Ring, Output Tip, Output Ring |
| data[0], data[1] | Command 8: bank 0..3, preset 0..127 |

### 40 Relay Switching, `<omniport-relay>` main.js@4683948

| data | Field | Values |
|---|---|---|
| 0 | Port | MC8 Pro: 0..3 Omniport 1..4, 4 Relay Port A, 5 Relay Port B |
| 1 | Tip action | 0 Nothing, 1 Tap - NO, 2 Tap - NC, 3 Engage, 4 Disengage, 5 Toggle, 6 Sync Clock 8 Taps |
| 2 | Ring action | Same |

Omniports need the Morningstar Relay Interface (Omniport type 10).

### 41 MMC, `<midi-mmc>`

`data[0]`: 0 Nothing, 1 Stop, 2 Play, 3 Deferred Play, 4 Fast Forward, 5 Rewind, 6 Record Strobe, 7 Record Exit, 8 Record Pause, 9 Pause, 10 Eject, 11 Chase, 13 MMC Reset. `data[1]`: device ID, 0x7F for all.

### 42 Trigger Messages, `<trigger-messages>` main.js@4704958

`data[0]` source preset 0..23. Then a 32-bit mask of which of its messages to trigger: `data[5]` bits 0-3 = messages 0..3, `data[4]` bits 0-6 = 4..10, `data[3]` = 11..17, `data[2]` = 18..24, `data[1]` = 25..31.

### 43 Focus Mode, `<focus-mode>`

`data[0]`: 0 On, 1 Off, 2 Toggle.

### 44 Preset Rename, `<preset-rename>` main.js@4710844

| Field | Encoding |
|---|---|
| `c-1` | bit 0: Load Original Preset Name. bits 1-3: 0 Current Active Name, 1 Short Name, 2 Toggle Name, 3 Shift Name, 4 Long Name |
| data[0..17] | New name, ASCII codes, max 18 chars. Unused bytes are 0. Bytes outside 32..127 are skipped on display |

`c` values therefore range 1..10.

### 45 ML5R, `<app-ml5-r-engage>` main.js@4719696

| data | Field | Values |
|---|---|---|
| 0 | Loop order | Permutation index 0..119 in lexical order of ABCDE (table `L$e`, main.js@3474622), 127 = a "no change" style entry **[inferred]** from the form treating index 127 specially |
| 1 | Loops | bits 0-4: loops A..E. bits 5-6: 0 No Change, 1 Engage Selected, 2 Bypass Selected, 3 Set Selected |
| 2 | Trails | 0..4 Loop A..E, 5 No Trails |
| 3 | Device ID | 0 Omni, 1..16 |

### 46 Multi Engage/Bypass, `<device-engage-bypass>` main.js@4725360

| data | Field |
|---|---|
| 0 | bits 0-2: 0 Engage, 1 Bypass, 2 Set. bits 3-6: channels 1..4 |
| 1 | bits 0-6: channels 5..11 |
| 2 | bits 0-6: channels 12..16 |

What is sent per channel comes from `midi_channels[n].dataAttributes` (section 6).

## 4. Bank and preset objects

### 4.1 Preset fields (`ai.getJSON`, main.js@3974700)

Keys in output order. Same object for `presetArray[24]` and `expPresetArray[4]`.

| Key | Type | Meaning |
|---|---|---|
| `presetNum` | int | 0..23 (A..X), or 0..3 for expression |
| `bankNum` | int | 0..127 |
| `isExp` | bool | |
| `shortName`, `toggleName`, `longName`, `shiftName` | string | 32 chars max. Padded with spaces at sysex time, truncated beyond 32 |
| `toToggle`, `toBlink`, `toMsgScroll` | bool | Toggle Mode, Blink, Message Scroll |
| `toggleGroup` | int | 0 None, 1..22 Group n, 23..30 Reset Group 1..8 (`O$e`). `setToggleGroup` zeroes values over 32. User-renameable in the editor profile, not in the file |
| `ledColor`, `ledToggleColor`, `ledShiftColor` | int | LED color, Pos 1 / Pos 2 / Shift |
| `nameColor`, `nameToggleColor`, `nameShiftColor` | int | Text color. `clearPreset` default 7 (white) |
| `backgroundColor`, `toggleBackgroundColor`, `shiftBackgroundColor` | int | Background |
| `msgArray` | 32 messages | |

Names may contain `%E<n>` and `%F<n>` tokens to show a scroll counter (`%F` adds 1 to the shown value), per the editor's placeholder text.

testdata: unused presets and all 512 expression presets are named `EMPTY`. That is device data, not an editor rule.

### 4.2 Bank fields (`Ki.getJSON`, main.js@3994000)

| Key | Type | Meaning |
|---|---|---|
| `bankNumber` | int | 0..127, array index |
| `bankName` | string | 32 chars max, sliced on load |
| `bankClearToggle` | bool | Clear Toggle on bank load |
| `bankMsgArray` | 32 messages | Bank numbering, section 4.4 |
| `presetArray`, `expPresetArray` | 24, 4 presets | |
| `bankDescription` | string | 32 chars max |
| `toDisplay` | bool | Display Description over preset long names |
| `pageLimit` | int | 0 No Limit, 1..3 Page 1..3 |
| `backgroundColor`, `textColor` | int | Section 4.3. All 128 banks in testdata hold 127/127 |
| `isColorEnabled` | bool | testdata true |

127 is not in the color table and the Ignore button in the picker returns null rather than a value. Reading it as "unset" is **[inferred]**.

### 4.3 Colors

Table `AQ`, main.js@3456680, 50 entries: 0 black, 1 lime, 2 blue, 3 purple, 4 yellow, 5 orchid, 6 grey, 7 white, 8 orange, 9 red, 10 skyblue, 11 deeppink, 12 olivedrab, 13 mediumslateblue, 14 darkgreen, 29 aqua, 30 turquoise, 31 cadetblue, 32 steelblue, 33 lightsteelblue, 34 tan, 35 brown, 36 cornsilk, 37 maroon, 38 lavender, 39 teal, 40 darkseagreen, 41 forestgreen, 42 olive, 43 indigo, 44 blueviolet, 45 thistle, 46 rebeccapurple, 47 gold, 48 khaki, 49 darkkhaki, 50 lightyellow, 51 lightsalmon, 52 tomato, 53 orangered, 54 darkorange, 55 indianred, 56 salmon, 57 firebrick, 58 darkred, 59 lightpink, 60 hotpink, 61 palevioletred, 62 slategray, 63 lightgray.

Dim variants (`MQ$1`, main.js@3466648): value 1..14 becomes value+14 (15..28), any other value ≤ 63 becomes value|64. A value counts as dim if it is 15..28 or has bit 6 set. Black dim is therefore 64.

### 4.4 Bank message types

Numbering `$l`, main.js@3418100, **different from presets**. Parameters match the preset form of the same component.

| t | Name | Same layout as preset type |
|---|---|---|
| 0 | Empty | |
| 1 | PC | 1 |
| 2 | CC | 2 |
| 3 / 4 | Note On / Off | 3 / 4 |
| 5 | Real Time | 5 |
| 6 | Set Toggle | 15 |
| 7 | Select Exp | 17 |
| 8 / 9 | Strymon Bank Up / Down | 19 / 20 |
| 10 | Delay | 23 |
| 11 | Song Position | 25 |
| 12 | Looper Mode | 18 |
| 13 / 14 | PC Scroll Up / Down | 8 / 9 |
| 15 | Engage Preset | 27 |
| 16 | Utility | 36, with the bank option list |
| 17 | PC Multi Channel | 34 |
| 18 | MIDI Clock | 7 |
| 19 | Relay Switching | 40 |
| 20 | MMC | 41 |
| 21 | Focus Mode | 43 |
| 22 | Bank Jump | 13. The bank form (`isBankPreset`) shows no last-used-bank or ignore options |
| 23 | Song Select | In the enum; no form and not in the menu |
| 24 | CC Waveform | 26 |
| 25 | Sequence Generator | 31 |
| 26 | ML10X | 39 |
| 27 | Toggle Page | 14, but only 3..6 |
| 28 | ML5R | 45 |
| 29 | SysEx | 6 |
| 30 | Multi Engage/Bypass | 46 |

Bank Utility options on a Pro (**numbers differ from presets above 6**): 0 Set Message Scroll Counter, 1 Clear Global Preset Toggles, 4 Set Scroll Counter Values, 5 Set MIDI Output Mask, 7 Set Bank Background/Text Color, 8 Enable Fast Step Mode (Beta), 9 Disable Fast Step Mode (Beta).

**Two bank message pitfalls:**

1. In testdata all 4096 bank messages are empty (t=0) yet have `data[9] == 127`. This looks like a parser artifact, not a setting: for 14-byte bank rows the editor reads `data10` one position past the row, which is the next record's 0x7F marker (main.js@~4001400). Preserve it or zero it **[inferred, strong]**. testdata therefore holds no real bank message, so every bank layout here rests on the code.
2. On restore, a bank rebuilt from JSON has `isProBugFix` false, so its rows are written in the 14-byte form with only `data[0..8]` (main.js@3996550). **Bank message bytes past index 8 are silently dropped on JSON restore.** So a bank SysEx carries at most 9 data bytes per message on JSON restore. The effect on the device is **[inferred]**, not tested.

## 5. Expression presets

Expression presets are in `expPresetArray`, with `isExp: true`. `presetNum` 0..3 are shown as "Expr 1".."Expr 4", and map to Expression 1..4, meaning Omniports 1..4 when set to type 1 **[inferred]** from labels. Each has 32 messages using this numbering (`Uze`, main.js@3418550). `a` stays 0, `tg` 2.

| t | Name | Form | Fields |
|---|---|---|---|
| 0 | Empty | | |
| 1 | Expression CC (Linear Response) | `<expmsg>` | data[0] CC, data[1] CC Min, data[2] CC Max, `c`. A new one gets data[2]=127 |
| 13 | Expression CC (Custom Response) | `<expmsg>` scaling | As 1, plus data[3] Scaling Factor |
| 2 / 3 | CC Toe Down / Heel Down | `<ccmsg>` | data[0] CC, data[1] value, `c`; data[2] 0 |
| 6 / 7 | Send CC On Engage / Disengage | `<ccmsg>` | Same |
| 8 / 9 | Send PC On Engage / Disengage | `<pcmsg>` | data[0] PC, data[2] Send Type, `c` |
| 10 / 11 | PC Toe Down / Heel Down | `<pcmsg>` | Same |
| 4 | Toe Down Toggle Channel | `<exptoedownchannelmsg>` | data[0] Msg Number 0..15, data[1] First Channel, data[2] Second Channel. **Channels here are in data and 1-based** |
| 5 | Toe Down Toggle CC | `<exptoedownccmsg>` | data[0] Msg Number, data[1] First CC, data[2] Second CC |
| 12 | Pitch Bend | `<exp-pitch-bend-msg>` | data[0] Pitch Bend Below 0, data[1] Above 0, `c`. Displayed as value << 6 |
| 14 | Waveform Engine Speed | `<exp-waveform-engine-speed>` | data[0] engine 0..3, data[1] min, data[2] max multiplier code |
| 15 | Sequencer Engine Speed | `<exp-sequencer-engine-speed>` | data[0] engine 0..1, data[1], data[2] as 14 |
| 16 | Utility | `<preset_utility>` isExp | Only data[0]=5, Set MIDI Output Mask |

Note that the forms for 14 and 15 only offer engines 1..4 and 1..2 even on a Pro with 8 of each.

Scaling Factor (`l$e`): 0 = 0, 1..20 = -20..-1, 21..40 = +1..+20. Its mathematical effect on the response is **[unknown]**.

Speed multiplier code `v`: `v < 63` gives `0.95^(63-v)`, `v = 63` gives 1, `v > 63` gives `1.05^(v-63)`.

**Curve:** there is no curve field anywhere in the format. The bundle's only uses of "curve" are MIDI dictionary entries. Response shaping consists of CC min/max per message, the Custom Response scaling factor, and `fixedSwTip` as Expression Sensitivity per Omniport (section 6). Calibration data is held on the device, requested separately, and is not in the backup **[code]** (`REQUEST_EXPRESSION_CALIBRATION`, no JSON field).

## 6. `data.controller_settings`

Envelope `{type:"controller_settings_all",data:{...}}`. Each section is `{type:<name>,data:...}`, and array entries are themselves `{type:<item>,data:{...}}`. `fromJson` (main.js@3937966) skips any missing section, and each section checks its `type` string. Order written: omniports, resistor_ladder_aux, controller_settings, waveform_engines, sequencer_engines, scroll_counters, midi_channels, bank_arrangement, midi_events, midi_clock_slots.

### 6.1 `omniports` (`omniport_all`, 4 × `omniport_input`, main.js@3910059)

Fields: `portNum` 0..3, `type`, `fixedSwTip`, `td1`, `td2`, `fixedSwRing`, `rd1`, `rd2`, `fixedSwTipRing`, `trd1`, `trd2`.

`type` (`h$e`): 12 Disabled, 8 TRS Aux Switch, 11 Resistor Ladder Aux Switch (Omniport 1 only), 1 Expression, 5 MIDI Out - Type A (Standard), 6 MIDI Out - Tip Active, 7 MIDI Out - Ring Active, 9 MIDI Out - Type B, 10 Ext Omniport Relay Interface, 0 (Deprecated) Aux Switch.

| `type` | `fixedSwTip` | `fixedSwRing` | `fixedSwTipRing` | `td1`/`rd1`/`trd1` |
|---|---|---|---|---|
| 1 | Expression Sensitivity: 2 Low, 1 Medium, 0 High | | | |
| 8 | Function, Tip | Function, Ring | Function, Tip+Ring (disabled in UI if Tip or Ring is 0) | Bank Number when that function is 15 |
| 10 | Relay Tip: 0 Normally Open, 1 Normally Closed | Relay Ring, same | Clock Sync: 0 No Sync, 1 Sync Tip only, 2 Sync Ring only, 3 Sync Tip + Ring | |
| 11 | See 6.2 | | | |

Aux function enum (`_$e` + `E$e`): 0 Do Nothing, 1 Bank Down, 2 Bank Up, 3 Toggle Page, 4 MIDI Clock Tap Tempo, 5 Toggle MIDI Clock, 6 Start MIDI Clock, 7 Stop MIDI Clock, 8 Toggle Looper Mode, 9 Enter Looper Mode, 10 Exit Looper Mode, 11 Enter Bank Change Mode, 12 Toggle Active Preset, 13 Page Up, 14 Page Down, 15 Bank Jump, 32..55 Preset A..X.

`td2`, `rd2`, `trd2`: no form control, always 0 in testdata **[unknown]** purpose.

Types 5, 6, 7, 9 use no other fields. All four ports are type 1 in testdata.

### 6.2 `resistor_ladder_aux` (`resistor_ladder_aux_switch_all`, 16 × `resistor_ladder_aux_switch`)

`switchNumber` 0..15, `triggerValue` (127 Not used, 1..126), `f1` function (enum 6.1), `f2` Bank Number when `f1` is 15. Trigger values normally come from the device's calibration menu **[inferred]**.

### 6.3 `controller_settings` (`general_configurations`, main.js@3927312)

| Field | Label | Values |
|---|---|---|
| `dualLock` | Dual Switch Lock | bool |
| `midiClockPersist` | MIDI Clock Persist | bool |
| `lcdAlign` | Align LCD Names | bool |
| `midiThru` | MIDI Thru | bool. **Not transmitted on Pro** (`getArray` omits it) |
| `crossMidiThru` | Cross MIDI Thru | bool. **Not transmitted on Pro** |
| `ignoreMidiClock` | Ignore MIDI Clock | bool |
| `savePresetToggle` | Remember Toggle States | bool |
| `loadLastBankOnStartup` | Load last used bank on power up | bool |
| `showPresetLabels` | Show Preset Labels | bool |
| `midiChannel` | MIDI Channel | 0 Disabled, 1..16 (1-based) |
| `switchSensitivity` | Switch Sensitivity | 0..4, labelled 1..5 |
| `bankChangeDelayTime` | Bank Change Delay Time | Value × 10 ms, step 5, 0..60 |
| `bankChangeDisplayTime` | Bank Name Display Time | Value × 10 ms, step 5, 0..100 |
| `longPressTime` | Long Press Time | ms = 100 + 50 × value, 0..28 in the form; the setter used on read from device clamps to 2..30 |
| `numMidiCable` | USB Virtual MIDI Ports | 1..4 |
| `midiSendDelay` | MIDI Send Delay (ms) | 0..50 |
| `presetMaxFontSize` | Preset Max Font Size | 0..10 = 18..8 |
| `middleLayerFontSize` | Bank / Preset Long Name Font Size | Same scale **[inferred]**, MC8 Pro only |
| `bankPageFontSize` | Bank/Preset Font Size | 0 Large, 1 Medium, 2 Small, 3 Hidden |
| `screenSaverTime` | Screensaver Time | 0 Off, 1..10 hours |
| `brightnessValue` | LCD Brightness | 0..7 = 30%..100% |
| `bluetoothStartupDelay` | Bluetooth Startup | 0 OFF, 1 0s, 2 10s ... 7 60s |
| `midiClockOutputPorts` | MIDI Clock Port Settings | 12-bit mask, bits as `sendToPort` below |
| `rpA`, `rpB` | Relay Port A, B | 0 Tip NO Ring NO, 1 Tip NO Ring NC, 2 Tip NC Ring NO, 3 Tip NC Ring NC |
| `midiThruMatrix` | MIDI Thru Settings | Below |

`midiThruMatrix`: `{type:"midiThruMatrix",data:{usbHost,usbDevice,din5,mm35,bluetooth}}`, one object per input with bool keys per output. usbHost: usbDevice, din5, omniport, mm35, bluetooth. usbDevice: usbHost, din5, omniport, mm35, bluetooth. din5: usbHost, usbDevice, omniport, mm35, din5, bluetooth. mm35: usbHost, usbDevice, omniport, din5, mm35, bluetooth. bluetooth: usbHost, usbDevice, din5, mm35, omniport. No Omniport input row exists.

### 6.4 `waveform_engines` (8 × `waveform_engine`)

`num` 0..7, `min`, `max`, `type`: 0 Off, 1 Sawtooth Up, 2 Sawtooth Down, 3 Triangle, 4 Sine, 5 Square, 6 Random.

### 6.5 `sequencer_engines` (8 × `sequencer_engine`)

`engineNum` 0..7, `arr` 16 values 0..127, `len` 0..15. Reset gives `arr` 0..15 and `len` 15, so `len` = steps − 1 **[inferred]**.

### 6.6 `scroll_counters` (16 × `scroll_counter`)

`index` 0..15, `min`, `max`, `start`. The loader stops and returns false at the first missing entry of its 16 (main.js@3898754), so write all 16.

### 6.7 `midi_channels` (16 × `midi_channel`)

| Field | Meaning |
|---|---|
| `name` | Channel name, 16 chars on Pro |
| `channel` | 1..16, **1-based**. Used as the index on load |
| `sendToPort` | Output ports bitmask: 0 DIN, 1 USB device 1, 2..5 Omniport 1..4, 6 3.5mm, 7..9 USB device 2..4, 10 USB Host, 11 Bluetooth. 4095 = all |
| `remap` | Remap MIDI Channel To: 0 No Remap, 1..16 |
| `isMidiChannelOffset` | Shows PC numbers with a +1 offset in the editor. Whether the device uses it is **[unknown]** |
| `engageEnabled`, `bypassEnabled` | Multi Engage/Bypass enable. On the wire these are bit 0 and bit 1 of `dataAttributes[0][0]` |
| `dataAttributes` | 8 pairs. `[0]`: flags as above (testdata channel 2: `[[1,0],[0,127],...]` with `engageEnabled` true). `[1]`: Engage CC number, value. `[2]`: Bypass CC number, value. Pairs 3..7 unused, 0 **[unknown]** |

Edit `dataAttributes[0][0]` and the two bools together: the JSON path keeps them separately.

### 6.8 `bank_arrangement`

`{type,data:[...],isActive,numBanksActive}`. Entries `{type:"bank_arrangement",data:{bankNum,bankName}}`. testdata has 127 entries, bank numbers 0..126, `isActive` false. On load each `bankNum` is appended to the active sequence.

### 6.9 `midi_events` (16 × `midi_event`, MIDI Message Converter)

| Field | Values |
|---|---|
| `typeFrom`, `typeTo` | 0 Nothing, 1 Program Change, 2 Control Change, 3 Note On, 4 Note Off |
| `numberFrom`, `numberTo`, `valueFrom`, `valueTo` | 0..127 |
| `channelFrom`, `channelTo` | **0..15 = channel 1..16: 0-based, unlike everything else** (`g2e`) |
| `toMapInputOutput` | 0 Input, 2 Input no MIDI Thru, 1 Output |
| `toMapValue` | bool, convert the value rather than use the incoming one |
| `toSetOutgoingValue` | bool |

### 6.10 `midi_clock_slots` (16 × `midi_clock_slot`)

`index` 0..15, `bpm`. Constructor and `update` clamp to 500, `fromJson` does not. 14-bit on the wire (`getLSB`, `getMSB`). Same all-16 rule as 6.6 (main.js@3935854).

## 7. Restore validation

The file is checked at three places. The hash algorithm is the same in all three.

### Hash

`o2e`, main.js@3419685: Java `String.hashCode`. For each UTF-16 code unit `c` of the input, `h = (h*31 + c)` truncated to signed 32 bits, starting at 0.

Input: `JSON.stringify(file.data)`, so compact, no spaces, in the file's own key order, over the `data` object only. The envelope keys are excluded. Compared with loose `==` by `BQ$1`, main.js@3419889.

Reproduced in Python on both real files: all-banks 89250710 = 89250710, bank-guitar-live 356811990 = 356811990 **[verified]**. Python recipe:

```python
text = json.dumps(doc["data"], separators=(",", ":"), ensure_ascii=False)
h = 0
raw = text.encode("utf-16-le")
for i in range(0, len(raw), 2):
    h = (h * 31 + (raw[i] | raw[i + 1] << 8)) & 0xFFFFFFFF
hash_value = h - (1 << 32) if h >= 1 << 31 else h
```

Keep integers as integers (`1.0` would stringify as `1` in JS but not in Python). Key order is free as long as the hash is computed on the same order that is written.

### Main restore (`app-preset-manager`, `prepareJsonRestore`, main.js@4881500)

1. Extension must be `.json` (or `.syx`, the legacy path with packet and batch checksums). Parse failure: snackbar "Invalid JSON file selected".
2. `isJsonValid`: `schemaVersion`, `dumpType`, `deviceModel`, `hash` must all be non-null. Their values are not checked here. Otherwise the same snackbar and stop.
3. **Hash mismatch is only a warning.** Dialog "Backup Data Changed" (main.js@4900592): the data "seem to have been manually altered ... Proceed at your own risk", buttons Cancel and Proceed with Upload. Cancel clears the file; Proceed continues.
4. `deviceModel` differing from the connected model: second dialog "Data-Controller mismatch" (main.js@4901537; uploads to overlapping presets, message types like Set Toggle need checking), same two buttons.
5. No file size limit, no JSON schema check, no range check of any field, no checksum beyond the hash.

### What the upload actually does (`clickSendJsonButton`, main.js@4883300)

The file is not sent as is. It is rebuilt through the model classes, then each bank and preset is serialized and sent:

- `singleBank`: `data.bank` is loaded, written to its own `bankNumber`. `controller_settings` is ignored. Commands 7/16, 7/17, 7/18.
- `allBanks`: every `bankArray` entry is rebuilt and queued by its `bankNumber` (`bankNum` also accepted). A null entry gives a snackbar "Missing value at index N" and is skipped. If `controller_settings` is present it is loaded into the controller state and sent. Commands 7/19, 7/20, 7/21.
- `dumpType` anything else: nothing is sent.

Load behaviors an offline writer should respect:

- A bank needs `bankNumber`; a preset needs `presetNum` or the load returns false for it. Each message needs `m`, otherwise the loader returns false and that slot stays empty. `bankMsgArray` must exist (no guard); a short one just leaves the remaining slots empty.
- Presets at or above 24 and expression presets at or above 4 are logged and dropped. Fewer presets is accepted; slots not in the file stay at their initial state **[inferred]**, so always write all 24 + 4.
- `expPresetArray` has no null guard, so a null entry there throws; `presetArray` has one.
- Keep 32 messages, 18 data bytes.
- `bankName` and `bankDescription` are cut to 32. Preset names are cut or space-padded to 32 at sysex time, and character codes go through unmasked at the JSON stage, then `addByte` masks to 7 bits in the chunk builder, so non-ASCII is corrupted rather than rejected **[inferred]**.
- Preset colors are applied only when truthy. A bank `textColor` that does not parse defaults to 7, `backgroundColor` to 0.
- Bank messages are truncated to 9 data bytes (section 4.4).

### Other loaders

- Patch Share upload dialog (main.js@3496631): **strict**. Needs `dumpType=="singleBank"` (or a preset file), and a hash mismatch rejects the file outright. Not relevant to restoring to the device.
- ML10X/ML5R panel (main.js@5983697): separate device, same pattern plus a hard model ID error.
- Offline editor (main.js@6090962, @6182772): model mismatch shows a message; loads `singleBank` and `allBanks`. No hash check in those paths.

## 8. API channel byte (`0x70`)

**Not determined.**

- The bundle contains no use of the external API (op1 0x70): it talks the session protocol only.
- The official API doc (`manuals/text/mc8-pro-sysex-api.md`) says only `pp -- MIDI Channel`, with no base.
- SDK `external.go` `SetPresetMessage` sends `byte(m.Channel)` unchanged, and `model.Message.Channel` is documented 1..16, so the SDK **assumes** 1-based. Its integration test writes `Channel: 1` and never reads the channel back or checks the MIDI output, so this proves nothing.

What is settled: the **session** protocol uses the JSON value unchanged, 1..16 (`getSysexArray` sends `getChannel()` raw; the SDK's capture notes in `sysex/preset.go` record an empty slot with JSON c=1 at the channel position). For the record, that protocol's rows are asymmetric: position 5..7 is action, toggle, channel in dumps, but channel, action, toggle in writes.

A one-message test would settle it: `0x70` write of a PC on channel byte 1 with a MIDI monitor attached.

## 9. Not determined

Stated plainly, in addition to items flagged inline.

1. Base of the `0x70` API channel byte (section 8).
2. Firmware behavior for values the forms never produce: out-of-range `data`, `c` over 16 on channel-free types, unused `data` indexes non-zero. All layouts here come from the editor; the firmware was not examined.
3. Whether the firmware honors SysEx strings beyond the editor's 127-byte UI limit, up to the 575 implied by `onApply`. How the firmware recognizes the end of one SysEx and the start of another in the same preset, beyond the length byte.
4. Types 30 Set Display and 38 NRPN, and bank type 23 Song Select: numbered but no form or menu entry. Layout unknown.
5. Utility 5 `data[1]` (`maskUntil`): written 0, no control. Effect unknown.
6. Utility 10, 11, 12 and bank 8, 9 take no parameters in the form. Whether the firmware reads any is unknown.
7. Effect of the Custom Response scaling factor (expression type 13).
8. Axe FX Integration effect slots (`data[3..10]`): the panel is compiled out in this build, so correctness on hardware is unconfirmed. Effect enum read to 84 only.
9. `isMidiChannelOffset`: whether the device uses it. `dataAttributes` pairs 3..7. Omniport `td2`, `rd2`, `trd2`.
10. Bank `backgroundColor`/`textColor` 127: "unset" is inferred.
11. ML5R `data[0]=127` meaning: inferred.
12. Whether `midiThru` and `crossMidiThru` have any effect on a Pro restored from JSON. They are not in the Pro settings array, so presumably not; the matrix replaces them **[inferred]**.
13. Whether a custom `bank_arrangement` restores byte-exactly: the logic was read, but not tested against an active arrangement, since testdata has `isActive` false.
14. testdata exercises only preset types 2, 15, 24 and no bank or expression message at all. All other layouts rest on the editor's code. mc6-virtual decodes preset types 1, 2, 13, 14, 15, 17, 22, 23, 24, 27, 36 and 44, and I compared Set Toggle, Select Exp, Bank Jump, Toggle Page, Engage, Delay and Utility against it. It is a third-party reader, not proof of firmware behavior.

## 10. Verified on hardware (MC8 Pro firmware 3.13.6, 2026-11-05)

- `mc8bak.mjs` keeps a backup byte-identical when nothing is edited, and its hash matches the editor's.
- A single-bank file edited offline restored through the official editor with no warning. Reading the bank back gave the same hash, so all 11 test messages (CC, CC Value Scroll, Set Toggle, Relay Switching, Axe FX Tuner, Bank Jump, Delay, Utility output mask, Axe FX Integration, Engage Preset, Real Time) were stored unchanged.
- Sent for real, seen on the USB echo: CC (`B1 14 40`). CC Value Scroll with Decrease and Send stays at the counter minimum without wrap (`B1 14 00`).
- Delay and output mask send nothing visible on USB.
- MC8 DIN to FM3 works: CC 2 = 1 on channel 2 moved FM3 Pitch 1 from channel A to B.
- CC#10+n value 1 over USB presses preset n of the current bank.

- A bank built by a script restored and read back with the same hash, including after a reconnect.
- Toggle Mode, Set Toggle Disengage and messages on Pos 1 / Pos 2 work: two presets exclude each other, checked with Get Toggle State (0x31). Set Toggle does not send the messages of the preset it disengages.
- Trigger Messages works and fires messages of the source preset whatever their action: a holder preset keeps them under Long Double Tap Release, so pressing the holder alone sends nothing, and the triggering preset sends them.
- **Message Scroll steps on Release only.** With `toMsgScroll` on, messages under action Press all fire on every press (USB or physical switch), with or without Manage Preset Message Scroll. Under action Release (`a` 2, `tg` 0, as in the editor template `preset_template_msg_scroll.json`) each release sends the next message and wraps at the end. Checked with Trigger Messages as the scrolled messages.
- CC#10+n value 2 over USB is a Release of preset n, so a USB test of a Release message needs value 1 then value 2.
- Editor Controller Settings: a toggle is local until the section's Save Settings. An All Banks backup taken before that shows the local state (seen: dualLock true and midiThru false while the device still had dualLock false). Load Settings shows the device. Save offers Restart now.
- Toggle Page 1, 2 and 3 confirmed on the display by camera, from USB presses. The display shows `B001 P0n`, the bank name, and two rows per screen: E-H above A-D on the unit.

Not verified: behaviour of relay, tuner, integration, bank jump and Engage Preset on the device; Message Scroll on Release from a physical press; persistence after a power cycle; the counter unit and upper end of CC Value Scroll with step 16.

## 11. Direct USB connector (2026-11-06)

`mc8usb.py` reads and writes banks without a browser, over winmm, using the session protocol from benemon/morningstar-sdk. Session open `00 1B`, select bank `00 1F bank 1 0 0`, restore `07 00 48`, then `07 10`, `07 11` × 24, `07 12` × 4, `07 00 49`; the device answers `07 00 33` before each next frame and `07 00 17` at the end. Bank read: `07 00 50` with model byte 0, every frame acknowledged by `00 7F checksum`, end `07 00 1`. Verified on firmware 3.13.6: seven banks written and read back identical, and bank 1 unchanged after writing bank 3. `isColorEnabled` reads back False whatever was written. Bank Jump works. Toggle states clear on leaving a bank unless Remember Toggle States (general settings byte 12) is on.
