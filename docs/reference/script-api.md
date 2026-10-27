# Script reference

What the engine gives a script, and what a script declares to the plug-in. The [guide](../guides/write-a-script.md) shows these in use.

## `vstaudio`

| Call | Role |
|---|---|
| `vstaudio.on_event(handler)` | Register the event callback. One owner per instance: the script. |
| `vstaudio.output(node)` | Tell the plug-in which audio node to pull from. |
| `vstaudio.input()` | The audio the host sends this track (effects). |
| `vstaudio.sample_rate()` | The host sample rate. |
| `vstaudio.transport()` | `(playing, seconds, bpm, numerator, denominator)`. |

## Events

The handler is called as `handler(event_type, channel, note_id, data0, value0, value1, sample_position)`. Events arrive at absolute sample positions on the delayed render interval, and the offset inside the block is preserved.

| Constant | Value | `data0`, `value0`, `value1` |
|---|---:|---|
| `EVENT_NOTE_ON` | 1 | pitch; velocity 0 to 1; tuning offset in semitones |
| `EVENT_NOTE_OFF` | 2 | pitch |
| `EVENT_POLY_PRESSURE` | 3 | pitch; pressure |
| `EVENT_PITCH_BEND` | 4 | `value0` is 0 to 1; `value1` is the same bend as -1 to 1 |
| `EVENT_CONTROL_CHANGE` | 5 | controller number; normalized value |
| `EVENT_PARAMETER` | 6 | zero-based macro index; normalized value |
| `EVENT_CHANNEL_PRESSURE` | 7 | pressure in `value0` |
| `EVENT_TRANSPORT` | 8 | sent on locates, loop wraps, play-state, tempo and time-signature changes |
| `EVENT_PROGRAM_CHANGE` | 9 | `data0` is the program number |

A note-on with velocity 0 is how some hosts send a note-off. Every one of the 128 MIDI controllers on 16 channels reaches the script as `EVENT_CONTROL_CHANGE`.

## Declarations

| Name | Type | Meaning |
|---|---|---|
| `NAME` | str | Stable name. For a discovered library module it is required, and the class ID derives from the file path plus this. |
| `DISPLAY_NAME` | str | Title shown by the host and the editor. Optional. |
| `MACRO_LABELS` | tuple of str | One label per macro. Without it the editor draws no macros. |
| `MACRO_MODES` | dict | `index: mode`, where the mode is `"UNIPOLAR"`, `"BIPOLAR"` or `"TOGGLE"`; it picks the control the editor draws. |
| `PATCHES` | dict | `index: (name, (macro values, MIDI 0-127))`. The first is what an unset macro resolves to. |
| `NOTE_MAP` | tuple | Percussion instruments: `(note, name)` pairs. |
| `CATEGORIES`, `VERSION`, `VENDOR` | | Optional metadata. |

## `catalog.json`

One entry per class in `Contents/Resources/catalog.json` of the installed bundle:

| Key | Contents |
|---|---|
| `name`, `cid` | The class name and its VST3 class ID. |
| `macro_labels` | The macro labels. |
| `macro_ranges` | `[low, high]` per macro, in the macro's own units. |
| `patches` | `{index, name, macros}`, with macro values in MIDI 0 to 127. |
| `note_map` | `[note, name]` pairs for percussion. |

`moduleinfo.json` beside it is Steinberg's file, for hosts: the same IDs, with no patches or ranges. Read class IDs from the catalog in the bundle you installed, not from a document.

## `mpvst_scan_plugins.py`

Run with the bundle's engine from the folder holding it, it writes `moduleinfo.json`. `--list` prints what it found instead, and `--json` prints the file it would write.
