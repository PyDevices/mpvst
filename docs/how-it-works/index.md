# How MPVST works

MPVST turns Python-defined audio instruments and effects into VST3 plug-ins.
One bundle exposes a named plug-in for every discovered `audioinstruments`
instrument and `audioeffects` effect, as well as generic instrument and effect
**MPVST Script Host** classes for running arbitrary scripts.

The defining architectural choice is that the DAW does not run MicroPython
inside its own process. Each plug-in instance launches a dedicated MicroPython
sidecar, while a native C++ VST3 component keeps the host's audio callback
bounded and real-time safe. If a script crashes, hangs, or exhausts its heap,
MPVST can silence and restart that instance without taking down the DAW.

This page follows the main execution path from the DAW to your script and back.
Where to look in the source, and how to build and test it, is in
[CONTRIBUTING.md](../../CONTRIBUTING.md).

## A mental model

```text
DAW
 `-- Native VST3 plug-in instance (C++)
      |-- Processor: audio callback, events, parameters, saved state
      |-- Controller: host-visible parameters and editor coordination
      |-- Native view: displays a shared framebuffer
      `-- Shared memory
           ^
           |
           v
          MicroPython sidecar process
           |-- vstaudio native module
           |-- vstui native module
           |-- Python bootstrap
           |-- instrument/effect adapter
           |-- user or generated Python script
           `-- LVGL generic editor
```

The processor and engine exchange only fixed, versioned data. No C++ object,
native pointer, or MicroPython object crosses the process boundary.

## How an instance works

### 1. The DAW instantiates a VST3 class

The VST3 factory can construct a generic instrument Script Host, a generic
effect Script Host, or a named class discovered from the component catalog.
Named classes do not require generated C++ classes or generated Python shim
files. The factory gives a catalog entry to the same `Processor`
implementation used by the other classes.

That distinction is useful during development: adding or editing a Python
component generally changes staged Python and metadata, not the native plug-in
binary.

### 2. The processor owns audio and sidecar coordination

`src/plugin/source/processor.{h,cpp}` implements the host-facing audio
component. It is responsible for:

- audio bus negotiation and processing setup;
- activation, deactivation, and latency reporting;
- MIDI events and parameter automation;
- transport information;
- component state save and restore;
- sidecar lifetime and shared-memory coordination; and
- copying completed audio to the host, or emitting silence when none is ready.

Instrument and effect modes share this implementation. Effect mode adds a
stereo input bus and latency-matched bypass behavior; instrument mode has no
audio input.

The processor's audio-thread state uses fixed storage or lock-free atomics.
When working here, treat any allocation, mutex, wait, filesystem operation,
process operation, log call, or UI call in `process()` as a design error.

### 3. Work crosses a fixed shared-memory protocol

The canonical definitions are in
[`src/protocol/include/mpvst/protocol.h`](../../src/protocol/include/mpvst/protocol.h) and
[`src/protocol/include/mpvst/ui.h`](../../src/protocol/include/mpvst/ui.h). The audio mapping contains:

1. a host-to-engine command ring;
2. a timestamped event and parameter ring;
3. render-work slots;
4. engine-to-host planar float output slots; and
5. status counters and bounded diagnostics.

The wire format deliberately excludes native pointers, C++ objects, `bool`,
`size_t`, compiler-sized enums, and implicit padding. Integers have fixed
widths, regions identify their size and generation, and the headers use
compile-time layout checks.

Queues and slots use sequence values with acquire/release ordering. The audio
thread never waits for a free slot. A full ring produces a bounded drop; late,
missing, stale, or mismatched output produces silence. Absolute sample
positions, rather than host block ordinals, identify work because hosts may
vary their block sizes.

The record sizes and ring rules are in the [protocol reference](../reference/ipc-protocol.md). A field change is an ABI change between two independently built processes, not an ordinary C++ refactor.

### 4. Each instance starts its own MicroPython engine

Each processor instance has a separate sidecar process and shared-memory
namespace. This isolates MicroPython VM state, garbage collection, exceptions,
and crashes between instances. The controller does not own the sidecar: a VST
host may construct a controller independently, and the processor must work
without an open editor.

The engine begins in [`lib/mpvst_bootstrap.py`](../../lib/mpvst_bootstrap.py). The bootstrap:

1. configures `vstaudio` with the audio mapping;
2. removes current-directory entries inherited from the DAW from `sys.path`;
3. adds the staged bundle library directory;
4. optionally starts the editor;
5. reads and executes the selected script in a fresh namespace; and
6. enters the native `vstaudio.run()` loop, supplying reload and UI callbacks.

An editor startup failure is deliberately non-fatal. Audio rendering can
continue without a custom editor.

### 5. Adapters connect Python components to VST semantics

The [audiocomponents](https://github.com/PyDevices/audiocomponents) repository contains the host-neutral
`audioinstruments` and `audioeffects` packages. They know nothing about VST3
or MPVST's shared memory.

[`lib/mpvst_instrument_adapter.py`](../../lib/mpvst_instrument_adapter.py) and [`lib/mpvst_effect_adapter.py`](../../lib/mpvst_effect_adapter.py) form the
boundary. The instrument adapter, for example:

- constructs an instrument at the host sample rate;
- maps VST notes, macros, pitch bend, pressure, and controller events onto the
  component API;
- converts normalized VST values into the MIDI-style ranges used by that API;
- exposes the component's output through `vstaudio`; and
- clears the imported component package during reload so changes to shared
  helpers take effect too.

## Processor, controller, and editor

These are separate VST3 responsibilities and should remain separate.

### Processor

The processor owns the audio buses and callback, pipeline latency, event and
automation input, saved script state, sidecar lifecycle, and audio-safe
snapshots. It creates the UI mapping but does no UI work in `process()`.

### Controller

`src/plugin/source/controller.{h,cpp}` owns the host-visible parameters, MIDI
controller mapping, and editor coordination. The processor reports the UI
mapping name and generation through VST3 `IConnectionPoint` messaging. The
controller retains that identity independently of a particular window because
hosts may open, close, or briefly overlap editor views in any order.

### Editor and native view

The Python editor draws an RGB565 framebuffer with LVGL. The native view:

- blits that framebuffer into a host-owned native window;
- sends pointer and wheel input back to the engine; and
- turns published edits into VST `beginEdit`/`performEdit`/`endEdit` calls.

It does not interpret the widgets or reconstruct the UI. The seam is:
**Python paints pixels; native code presents pixels.**

[`usermods/vstui/modvstui.c`](../../usermods/vstui/modvstui.c) exposes the shared framebuffer, input, open-state,
edit, and error operations. [`lib/mpvst_board_config.py`](../../lib/mpvst_board_config.py) adapts those operations
to the normal PyDevices display contract, and [`lib/mpvst_editor.py`](../../lib/mpvst_editor.py) and
[`lib/mpvst_panel/`](../../lib/mpvst_panel/) connect the engine to the panel, the `controlpanel` package frozen into the engine. [The editor](editor.md) covers what the panel does and how it fails.

## Parameters, scripts, and state

### Stable parameters

The host-visible parameter surface (listed in the [reference](../reference/parameters-and-state.md)) contains bypass, Reload Script, read-only engine
ready and error values, a patch selector, and 16 macros. A further set of
hidden parameters implements 16-channel MIDI mapping. Macro IDs are permanently
100 through 115; their labels are metadata and may change without breaking
saved automation.

The processor distinguishes between macro values supplied by an authoritative
source, such as automation or restored state, and values it merely initialized.
On load it replays only known values, preserving a script's own defaults when
nobody has explicitly changed them.

### Script contract

At its simplest, a script registers an event callback with
`vstaudio.on_event()` and an output provider with `vstaudio.output()`. It may
also declare `MACRO_LABELS`, `MACRO_MODES`, and `PATCHES` for the host and
editor. See [Write your own instruments and effects](../guides/write-a-script.md) and the [script reference](../reference/script-api.md) for the complete contract.

Events arrive at absolute delayed sample positions. They include notes, pitch
bend, channel and poly pressure, MIDI controllers, transport changes, and macro
parameter changes.

### Saved state

Project state embeds the active script source rather than depending on its
original path. Current state accepts legacy version 1 data, bounds embedded
source at 1 MiB, and restores the source through an instance-private temporary
file.

An instance launched through `MPVST_SCRIPT_PATH` follows that development file:
reload reads it again, and save embeds its current contents. Once restored from
project state, an instance uses the embedded snapshot and no longer follows
later edits to the original file.

## Catalog and staging

CMake stages the `audioinstruments` and `audioeffects` packages beside
the engine and MPVST's `lib/` files. It then runs:

- `mpvst_scan_plugins.py`, which writes host-facing `moduleinfo.json`; and
- `mpvst_catalog.py`, which writes tool-facing `catalog.json`.

The native factory reads `moduleinfo.json`. Project generators use
`catalog.json` for class IDs, macro labels and ranges, and patches. Do not
hardcode a named class ID from documentation: the installed bundle's catalog
is the authoritative copy, and a test verifies that it agrees with the classes
the plug-in exposes.

A Python-only component change normally needs no C++ rebuild: stage it into an existing bundle and regenerate the two metadata files. The workflow is in [CONTRIBUTING.md](../../CONTRIBUTING.md#a-python-only-change-needs-no-compiler).

## Latency and the audio thread

For input and events at sample position `t`, the engine publishes the matching audio at `t + L`. `L` is the pipeline depth (four blocks by default, set in saved state) times the largest block size the host reports, and the processor reports `L` to the host so it can compensate. The first `L` samples after activation are silence. A change of sample rate or maximum block size deactivates the plug-in and rebuilds the pipeline outside `process()`, and a generation number keeps stale output from the old configuration from ever being played.

In `process()` the audio thread only reads the host's buffers, events and parameter queues; copies into and out of preallocated shared-memory slots; converts samples; updates lock-free atomics and fixed-size counters; and emits silence when output isn't ready. It never allocates, locks, waits, opens files, starts a process, calls MicroPython, logs, or touches UI.

## When something goes wrong

- **Underrun:** the plug-in outputs silence, increments a counter and carries on.
- **Protocol or generation mismatch:** silence, and a request for recovery outside the callback.
- **Python exception:** the engine reports a bounded error and stops that instance's graph. The DAW is untouched, and `Engine Error` (see the [reference](../reference/parameters-and-state.md#engine-error-codes)) says which kind it was.
- **Engine exit or hang:** silence, while a supervisor outside the callback restarts the engine, at most three consecutive times.
- **A host-side error:** never thrown across a VST interface boundary.

Process separation is crash containment, not a sandbox. A script runs with your permissions: see [What the shipped engine cannot do](security.md).

## Where to go next

- [The editor](editor.md): the panel and how its gestures become automation.
- [What the shipped engine cannot do](security.md): why there are no sockets, SSL or FFI.
- [Protocol reference](../reference/ipc-protocol.md): the shared-memory records and rules.
- [CONTRIBUTING.md](../../CONTRIBUTING.md): the repository map, building, tests, and where to start reading the source.
