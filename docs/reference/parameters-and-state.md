# Parameters and state

What a host sees of an MPVST instance, what it saves, and the environment variables that change it.

## Parameters

An instance exposes 20 visible parameters: bypass, `Reload Script`, the read-only `Engine Ready` and `Engine Error`, a patch selector, and 16 macros. It also exposes 2,080 hidden parameters (16 MIDI channels by 130 controllers) that carry MIDI controller input. REAPER reports three more of its own.

Macro parameter IDs are permanently 100 to 115. Labels are metadata that a script may change without detaching any automation. In the host's generic editor they appear as `Macro 01` through `Macro 16`, or as the script's labels.

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

A project embeds the active script's source, so reopening it doesn't depend on the original path. State version 2 holds the bypass flag, the 16 macro values, the pipeline setting and up to 1 MiB of script source. It accepts legacy version 1 data. The byte layout is in [Generate projects from code](../guides/generate-projects.md#put-the-chunk-into-the-rpp).

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
| `MPVST_COMPONENTS_LIB` | Offline soundtrack tools only: the `lib/` directory of an audiocomponents checkout. |
