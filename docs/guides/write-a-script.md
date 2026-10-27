# Write your own instruments and effects

You don't need to build anything to write for MPVST. The installed plug-in runs any script you point it at, and the library it ships is ordinary Python you can read. Start from [`lib/default_instrument.py`](../../lib/default_instrument.py) (it is also in the installed bundle), point `MPVST_SCRIPT_PATH` at your own file, and use the **MPVST Script Host** class. [MPVST on Windows](windows.md#develop-a-script) and [MPVST on Linux](linux.md#develop-a-script) cover the edit-and-reload loop. This page is what a script can say about itself.

## An instrument

A script registers an event callback and an output. [`examples/pluck.py`](../../examples/pluck.py) is the shortest working one, walked through in [First program](../get-started/first-program.md).

[`lib/default_instrument.py`](../../lib/default_instrument.py) is the fuller reference. It tracks voices by VST note ID, maps velocity to amplitude, applies pressure and pitch bend, and uses an explicit 50 ms release. It makes no sound, so that a slot nobody chose is obvious: every event path is there, but it doesn't press a note unless `MPVST_DEFAULT_INSTRUMENT_AUDIBLE` is set. A Script Host class loads it when nothing else is named.

Events arrive through `vstaudio.on_event()`. Macro automation arrives through the same callback as `vstaudio.EVENT_PARAMETER`. The [script reference](../reference/script-api.md) lists every event and what its arguments mean.

## Declare macros and patches

A script says what controls it has with module-level names:

```python
MACRO_LABELS = ("Gain", "Tone", "Attack", "Release")
MACRO_MODES = {0: "UNIPOLAR", 1: "UNIPOLAR", 2: "UNIPOLAR", 3: "UNIPOLAR"}
PATCHES = {0: ("Default", (64, 64, 64, 64))}
```

A bare script without them still runs, but the editor draws no macros or patches. Renaming a label doesn't change any parameter ID or detach automation. The first `PATCHES` entry is the sound the script's own defaults describe, and it is what an unset macro resolves to, not the middle of its range. Values are MIDI integers 0 to 127.

[`tools/derive_patches.py`](../../tools/derive_patches.py) generates a `PATCHES` block by measuring the instrument instead of guessing.

## An effect

An effect script reads `vstaudio.input()` and registers an output. The usual way is the effect adapter, which wires a library effect to the host and rebuilds it safely when a macro change needs a new graph:

```python
import mpvst_effect_adapter

mpvst_effect_adapter.run("TapeDelay", mix=0.5, feedback=0.4)
```

Instruments have the same adapter, `mpvst_instrument_adapter.run("audioinstruments.minimoog")`. Reach for the adapters when your script has to survive macro changes without dropouts. For a fixed chain with no macros you can build the effect yourself:

```python
import audioeffects
import vstaudio

delay = audioeffects.create("TapeDelay", vstaudio.input(), vstaudio.sample_rate())
vstaudio.output(delay.output)
```

Build library effects through `audioeffects.create(name, source, sample_rate, **options)`, so the construction stays the same across CPython, MicroPython and CircuitPython.

## Where the library lives

The instruments and effects are the `audioinstruments` and `audioeffects` packages from [audiocomponents](https://github.com/PyDevices/audiocomponents): host-neutral Python built on audiodsp's audio nodes, which any application can import, not just this plug-in. They're built into the engine.

There is no file per instrument. The unit the plug-in deals in is still a script: a saved project embeds its bytes, and the editor reads macro labels out of it. For a library instrument that script is built from its catalog entry when the class is instantiated, as two lines, so the library stays the one source of a plug-in's name, category and macro labels.

A library module declares `NAME`, `MACRO_LABELS`, `MACRO_MODES` and `PATCHES`; percussion instruments also declare `NOTE_MAP`. `CATEGORIES`, `VERSION`, `VENDOR` and `DISPLAY_NAME` are optional. The plug-in needs only `NAME`, and uses `DISPLAY_NAME` for the title when there is one. The class ID is derived from the file path plus `NAME`, so a copy of a library instrument is a distinct plug-in, and renaming the file or `NAME` changes the plug-in's identity.

A `.py` file declares itself with variables. The `# mpvst-` comment lines exist only in `moduleinfo.json`, where JSON5 comments are the only extension slot the format has.

[`lib/mpvst_instrument_adapter.py`](../../lib/mpvst_instrument_adapter.py) is where host values meet the library. `vstaudio` speaks the normalized floats the VST3 parameter API uses; the instrument API speaks MIDI 0 to 127. The conversion happens there and nowhere else, as a multiply, so a host that automates a macro with more than 7 bits keeps its resolution.

Piece-private instruments in the [soundtrack examples](../../examples/soundtrack/README.md) stay whole scripts in their own directory and end with a `__main__` guard that hands `create` to the same adapter.

## Next

- [Generate projects from code](generate-projects.md), if you want to put a script into a `.RPP` yourself.
- [Hear what you wrote](hear-what-you-wrote.md), for rendering a script without a DAW.
- [Parameters and state](../reference/parameters-and-state.md), for what a host sees.
