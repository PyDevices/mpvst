# Newcomer's guide to the MPVST codebase

MPVST turns Python-defined audio instruments and effects into VST3 plug-ins.
One bundle exposes a named plug-in for every discovered `audioinstruments`
instrument and `audioeffects` effect, as well as generic instrument and effect
**MPVST Script Host** classes for running arbitrary scripts.

The defining architectural choice is that the DAW does not run MicroPython
inside its own process. Each plug-in instance launches a dedicated MicroPython
sidecar, while a native C++ VST3 component keeps the host's audio callback
bounded and real-time safe. If a script crashes, hangs, or exhausts its heap,
MPVST can silence and restart that instance without taking down the DAW.

This guide provides a map of the repository, follows the main execution path,
and points to the best places to learn each part in more detail.

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

## Repository map

| Path | Purpose |
|---|---|
| `src/plugin/` | The native VST3 processor, controller, editor/view, factory, catalog reader, and sidecar transport. |
| `src/protocol/` | Stable shared-memory wire structures and lock-free queues shared by the plug-in and engine. |
| `src/runtime/` | Cross-platform shared-memory and child-process primitives. |
| `usermods/` | Native MicroPython modules compiled into the engine: `vstaudio` and `vstui`. |
| `lib/` | Python code staged into the bundle: bootstrap, adapters, editor, scanner, catalog generator, and fallback scripts. |
| `tests/` | Protocol and reload tests, fuzzing, and a minimal VST3 smoke host. |
| `tools/` | Python component sweeps, audio-quality checks, and developer utilities. |
| `scripts/` | Dependency setup, engine builds, packaging, and cross-platform checks. |
| `installer/` | The Linux installer and Windows NSIS installer. |
| `reaper/` | Real-DAW integration, rendering, automation, reload, and parity harnesses. |
| `examples/` | Composer APIs, generated projects, songs, private scripts, and rendering examples. |
| `docs/` | User, contributor, script-author, IPC, UI, security, and project-generation documentation. |

The root `CMakeLists.txt` assembles three native pieces: the protocol library,
the runtime library, and the VST3 plug-in. It adds the test tree separately
when `BUILD_TESTING` is enabled.

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
`src/protocol/include/mpvst/protocol.h` and
`src/protocol/include/mpvst/ui.h`. The audio mapping contains:

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

Read [the IPC design](architecture/ipc-v1.md) before changing any protocol
structure. A seemingly harmless field change is an ABI change between two
independently built processes, not an ordinary C++ refactor.

### 4. Each instance starts its own MicroPython engine

Each processor instance has a separate sidecar process and shared-memory
namespace. This isolates MicroPython VM state, garbage collection, exceptions,
and crashes between instances. The controller does not own the sidecar: a VST
host may construct a controller independently, and the processor must work
without an open editor.

The engine begins in `lib/mpvst_bootstrap.py`. The bootstrap:

1. configures `vstaudio` with the audio mapping;
2. removes current-directory entries inherited from the DAW from `sys.path`;
3. adds the staged bundle library directory;
4. optionally starts the editor;
5. reads and executes the selected script in a fresh namespace; and
6. enters the native `vstaudio.run()` loop, supplying reload and UI callbacks.

An editor startup failure is deliberately non-fatal. Audio rendering can
continue without a custom editor.

### 5. Adapters connect Python components to VST semantics

The sibling `audiocomponents` repository contains the host-neutral
`audioinstruments` and `audioeffects` packages. They know nothing about VST3
or MPVST's shared memory.

`lib/mpvst_instrument_adapter.py` and `lib/mpvst_effect_adapter.py` form the
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

`usermods/vstui/modvstui.c` exposes the shared framebuffer, input, open-state,
edit, and error operations. `lib/mpvst_board_config.py` adapts those operations
to the normal PyDevices display contract, and `lib/mpvst_editor.py` and
`lib/mpvst_panel/` implement the product panel. Read
[the UI design](architecture/ui-v1.md) before modifying this path.

## Parameters, scripts, and state

### Stable parameters

The public parameter surface contains bypass, Reload Script, read-only engine
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
editor. See [Writing your own instruments and effects](writing-scripts.md) for
the complete contract.

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

CMake stages the sibling `audioinstruments` and `audioeffects` packages beside
the engine and MPVST's `lib/` files. It then runs:

- `mpvst_scan_plugins.py`, which writes host-facing `moduleinfo.json`; and
- `mpvst_catalog.py`, which writes tool-facing `catalog.json`.

The native factory reads `moduleinfo.json`. Project generators use
`catalog.json` for class IDs, macro labels and ranges, and patches. Do not
hardcode a named class ID from documentation: the installed bundle's catalog
is the authoritative copy, and a test verifies that it agrees with the classes
the plug-in exposes.

A Python-only component change normally needs no C++ rebuild. It can be staged
into an existing bundle and the two metadata files regenerated. See the
Python-only workflow in [Working on MPVST itself](development.md).

## Building the project

A fresh checkout is not self-contained. The build uses ignored external
dependencies, including:

- the Steinberg VST3 SDK under `.deps/vst3sdk`;
- sibling `audiodsp` and `audiocomponents` checkouts;
- a sibling `micropython-pydevices` checkout (the `vst3-engine` variant and
  patch series), the module repositories its preset names, and an upstream
  MicroPython clone at the pinned tag, all used to build the engine; and
- optionally REAPER for the DAW integration harnesses.

The supported setup command is:

```bash
./scripts/bootstrap.sh
```

There are two distinct builds: the native plug-in and the custom MicroPython
engine. CMake stages an existing engine binary but does not determine whether
that binary is stale. Rebuild the engine explicitly after changing
`usermods/vstaudio`, `usermods/vstui`, or relevant native DSP sources.

The normal Linux build and test loop is:

```bash
cmake -S . -B .build-linux -G Ninja
cmake --build .build-linux
ctest --test-dir .build-linux --output-on-failure
```

The root `VERSION` file is the single source of truth for the release version;
CMake and both packaging scripts consume it. The complete prerequisites,
Windows workflow, staging details, and release process are in
[Working on MPVST itself](development.md).

## Testing layers

The suite deliberately tests the system at several boundaries:

- **Protocol tests** exercise shared-memory validation, rings, generations,
  state parsing, and bounded failure without an engine or DAW.
- **Engine tests** verify that the staged MicroPython binary contains the
  required audio, UI, and LVGL modules.
- **Smoke-host tests** load the real VST3 bundle in a minimal host and cover
  embedded state, rendering, effects, patches, reload, editor input, and every
  named class.
- **Python component sweeps** test instruments directly against the CPython
  `audiodsp` package for a faster component-level feedback loop.
- **Fuzz tests** exercise mapping and state parsing; a portable driver runs in
  the normal suite, with optional Clang/libFuzzer targets for deeper runs.
- **REAPER harnesses** cover behavior that needs a real DAW, including FX-chain
  changes, automation, project reload, installed bundles, and cross-platform
  render parity.

There is deliberately no hosted CI at present. The local `ctest` suite is the
project gate.

## Invariants and common pitfalls

### Never make the audio callback wait

Late or missing output is silence plus telemetry, not a reason to block. Review
changes to `Processor::process()`, the protocol, or `SidecarTransport` for
allocation, locks, waits, I/O, logging, unbounded work, and UI calls.

### Treat protocol definitions as an ABI

The protocol headers are shared by independently built binaries and encode
exact sizes, offsets, alignments, and atomic semantics. Update the design and
conformance tests alongside any intentional protocol change.

### Keep UI failure separate from audio failure

The editor is optional. It should do no work while closed, and failure to
create or run it must not prevent an instance from rendering audio.

### Process isolation is not a trust boundary

A separate process provides crash containment, not permission isolation. A
script executes with the user's authority. Consult [Security](security.md)
before changing the engine's enabled modules or import capabilities.

### External repositories are intentional dependencies

Missing `audiodsp` or `audiocomponents` siblings are not forgotten generated
directories. Setup fetches them, and MPVST consumes them read-only.

### `phase-0.md` is partly historical

[The Phase 0 architecture contract](architecture/phase-0.md) remains useful
for process, thread, failure, and state reasoning, but its Windows-only,
no-editor product description is historical. Use it together with
[the current IPC design](architecture/ipc-v1.md) and
[the UI design](architecture/ui-v1.md).

## What to learn next

### To understand the native core

1. Read `docs/architecture/phase-0.md` for threading and failure behavior.
2. Read `docs/architecture/ipc-v1.md` for queues and shared-memory rules.
3. Inspect `src/protocol/include/mpvst/protocol.h` and `ui.h`.
4. Read `src/plugin/source/processor.h`, then `processor.cpp`.
5. Read `src/plugin/source/sidecar_transport.h` and `.cpp`.
6. Use `tests/protocol_tests.cpp` and `tests/reload_tests.cpp` as executable
   specifications.

Focus on generation numbers, sequence values, absolute sample positions, and
silence-on-failure behavior.

### To write instruments or effects

1. Read [Writing your own instruments and effects](writing-scripts.md).
2. Start with `lib/default_instrument.py` or `lib/default_effect.py`.
3. Read the corresponding adapter in `lib/`.
4. Explore the pieces under `examples/soundtrack/`.
5. Learn the component factory contract in the sibling `audiocomponents`
   project and the output-node model in `audiodsp`.

Writing a script does not require building MPVST itself.

### To work on the editor

1. Read `docs/architecture/ui-v1.md`.
2. Read `lib/mpvst_board_config.py` and `lib/mpvst_editor.py`.
3. Read `lib/mpvst_panel/panel_adapter.py`, then `panel.py`.
4. Inspect `usermods/vstui/modvstui.c`.
5. Follow the native presentation and input path in
   `src/plugin/source/editor.cpp`.

### To work on builds and releases

1. Read `docs/development.md` and `scripts/README.md`.
2. Trace `scripts/bootstrap.sh`.
3. Inspect `src/plugin/stage_lib.cmake`.
4. Compare `scripts/package-linux.sh` and `scripts/package-windows.sh`.
5. Read the installer for the target platform.

Remember that building the engine, building the plug-in, and staging a bundle
are separate operations.

### To generate projects or compose music

1. Read `docs/generating-projects.md`.
2. Study catalog generation in `lib/mpvst_catalog.py`.
3. Explore `examples/reaper-composer/` and `examples/soundtrack/composer/`.
4. Look at the project builders under `reaper/matrix/`.
5. Read `docs/rendering.md` to understand component, smoke-host, and real-DAW
   rendering.

## A good first contribution

Before making a large architectural change, choose a narrow path and trace it
end to end. Good examples include:

- one MIDI event from the VST callback through the event ring to an instrument;
- one rendered block from a work slot back into the host's output buffers;
- one macro edit from the LVGL panel back to host automation;
- one named component from Python metadata to `moduleinfo.json` and factory
  registration; or
- one embedded script from project state to sidecar execution.

These paths cross the important boundaries while remaining small enough to
reason about and test.
