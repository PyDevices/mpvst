# Parameters and state

What a host sees of an MPVST instance, what it saves, and the environment variables that change it.

## Parameters

An instance exposes 22 visible parameters: bypass, `Reload Script`, the read-only `Engine Ready` and `Engine Error`, a patch selector, 16 macros, and `MIDI Channel`. It also exposes 130 hidden parameters that carry MIDI controller, pitch-bend and channel-pressure input on the channels the instance listens to. REAPER reports three more of its own.

Hosts built on JUCE, such as Element, don't hide hidden parameters, so they show all 152.

Macro parameter IDs are permanently 100 to 115. Labels are metadata that a script may change without detaching any automation. In the host's generic editor they appear as `Macro 01` through `Macro 16`, or as the script's labels.

### MIDI channel

`MIDI Channel` says which MIDI channels an instance listens to: All, the default, or one channel from 1 to 16.

On All, every channel reaches the script. A note keeps the channel it came on. Controllers, pitch bend, channel pressure and program changes from any channel arrive as channel 1, because the host merges them into one set of parameters. Leave it on All when the host already decides what a track hears: REAPER, for one, can restrict a track's input to one channel without renumbering it, and an instance fixed to channel 1 would go silent on a track that takes channel 3.

On one channel, notes, poly and channel pressure, pitch bend, controllers and program changes on that channel reach the script, as that channel, and everything on the other 15 is dropped. To play two instruments from one keyboard split or one multi-channel MIDI track, give each instance its own channel.

Changing the setting releases any notes still held: the script gets All Notes Off (controller 123) on the channel it was listening to, or on all 16 when it was All.

The setting is saved with the project. A project saved before it existed opens on All, so it hears what it always heard. Its automation on channel 1's controllers keeps working, because they kept their parameter IDs; automation recorded on another channel's controllers points at parameters that no longer exist, and hosts drop it.

Bypass on an instrument produces silence. On an effect it swaps to a latency-matched dry path.

`Reload Script` is a rising edge: toggle it off, then on. It is only observed while the plug-in is processing, and its value isn't saved. Output fades out over 128 samples, holds for the pipeline latency plus one block (640 samples at a 128-frame block with 512 samples of latency), then fades in over 128 samples.

### Engine error codes

`Engine Error` is an integer.

| Value | Meaning |
|---|---|
| 0 | Clear. |
| 1 | The script failed to load. |
| 2 | An uncaught exception while rendering. |
| 3 | An uncaught exception in a reload callback. |

An exit code of `-1000` in the telemetry means the supervisor killed an engine that had hung, rather than finding one that exited on its own.

## Saved state

A project embeds the active script's source, so reopening it doesn't depend on the original path. State version 5 holds the bypass flag, the 16 macro values, the pipeline setting, up to 1 MiB of script source, which macros somebody actually set, and the `MIDI Channel` setting. It accepts versions 1 to 3, which open on All, and version 4, which keeps the one channel it saved. The byte layout is in [Generate projects from code](../guides/generate-projects.md#put-the-chunk-into-the-rpp).

An instance started from `MPVST_SCRIPT_PATH` follows that file: reloading re-reads it, and saving embeds what is on disk. An instance restored from project state keeps its embedded snapshot and ignores later edits to the original.

Current macro values are replayed to the script whenever it loads, reloads or is restored, so an automated or reopened instance sounds the way it was saved. A value the processor only initialized isn't replayed, so a script keeps its own defaults until someone changes a macro.

Host transport position, tempo and time signature reach the script. Locates, loop wraps, play-state changes and tempo or time-signature changes arrive as `vstaudio.EVENT_TRANSPORT` in the block they happen in, and `vstaudio.transport()` returns `(playing, seconds, bpm, numerator, denominator)`. A library delay or modulation effect with Sync on follows a tempo change in the block it happens in.

## Environment variables

| Variable | Effect |
|---|---|
| `MPVST_SCRIPT_PATH` | Absolute path of the script a Script Host instance starts with. Set it before starting the DAW. |
| `MPVST_HEAP_BYTES` | Caps the MicroPython heap of every instance started afterwards. |
| `MPVST_ENGINE_PATH` | Overrides which engine binary is launched. |
| `MPVST_DEFAULT_INSTRUMENT_AUDIBLE` | Any non-empty value lets the empty-slot instrument press notes. |
| `MPVST_BUNDLE` | Offline tools only: where an installed bundle is, if it isn't in the usual place. |
| `MPVST_COMPONENTS_LIB` | Offline soundtrack tools only: the `lib/` directory of an audioinstruments checkout. |
