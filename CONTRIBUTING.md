# Contributing to MPVST

This is how to build the plug-in from source, run its tests, and cut a release.
To write instruments or effects *for* MPVST, which needs none of this, see
[Write your own instruments and effects](docs/guides/write-a-script.md).

A focused fix with a test, or a docs example that shows an existing call, is a
good first contribution. Before a larger change, pick one narrow path and trace
it end to end: one MIDI event from the VST callback to an instrument, one
rendered block from a work slot back to the host's buffers, or one macro edit
from the panel back to host automation. Each crosses the important boundaries
and is small enough to test. [How it works](docs/how-it-works/index.md) is the
map to follow.

## Repository layout

| | |
|---|---|
| `src/` | the C++ that builds the plug-in: `plugin/` (VST3 classes), `protocol/` (the shared-memory wire format), `runtime/` (shared memory and child processes) |
| `usermods/` | the MicroPython C modules the engine binds to: `vstaudio/` (the audio API scripts use) and `vstui/` (the editor's framebuffer, input and edit rings) |
| `lib/` | everything staged into the bundle beside the engine: the bootstrap, the adapters, `mpvst_scan_plugins.py`, the default instrument, and the editor's Python half (`mpvst_editor.py`, `mpvst_board_config.py`, `mpvst_panel/`) |
| `tools/` | developer tooling - the library test sweeps, `audio_qc.py`, `derive_patches.py` |
| `tests/` | the ctest suite and `smoke_host/`, a minimal VST3 host that loads the bundle with no DAW |
| `scripts/` | build, packaging and setup automation |
| `installer/` | what a user runs rather than builds: `windows.nsi` (the NSIS installer, cross-built from Linux) and `install-linux.sh`, which ships inside the tarball as `install.sh` |
| `reaper/` + `reaper.sh` | everything that drives REAPER. Deletable as a unit; nothing outside it depends on it |
| `examples/` | two composers with their songs, and `bounce.py`; nothing in here imports anything above it (rendering: [Hear what you wrote](docs/guides/hear-what-you-wrote.md)) |

How the pieces fit is in [How it works](docs/how-it-works/index.md). The canonical structure sizes and offsets live in [`src/protocol/include/mpvst/protocol.h`](src/protocol/include/mpvst/protocol.h) and [`src/protocol/include/mpvst/ui.h`](src/protocol/include/mpvst/ui.h); the [protocol reference](docs/reference/ipc-protocol.md) summarises them.

## Prerequisites

- A C++17 toolchain: MSVC on Windows, GCC or Clang on Linux.
  **The Windows plug-in binary is the one thing here that needs MSVC**, and
  the full Visual Studio IDE is not required - **Visual Studio Build Tools**
  with the Desktop C++ workload and a Windows SDK is enough, and is about
  half the disk:

  ```powershell
  winget install --id Microsoft.VisualStudio.BuildTools --override ^
    "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools ^
     --add Microsoft.VisualStudio.Component.Windows11SDK.26100 --includeRecommended"
  ```

  The generator the install script names is `Visual Studio 18 2026`, so it
  wants the 2026 Build Tools (`18.x`); the winget id above has no year in it
  and resolves to that. Nothing else in the repository needs it: the Windows
  *sidecar engine* is cross-compiled from WSL with MinGW, the Linux build
  uses GCC, and a Python-only change to the instrument or effect library
  never touches a compiler at all (see [A Python-only change needs no compiler](#a-python-only-change-needs-no-compiler)).
- CMake 3.25+ and Ninja (`cmake -S . -B .build-linux -G Ninja` is the
  documented invocation below).
- On Linux, X11 development headers ([`src/plugin/CMakeLists.txt`](src/plugin/CMakeLists.txt) runs
  `find_package(X11 REQUIRED)` for the editor's native window) - e.g.
  `libx11-dev` on Debian/Ubuntu.
- Python 3.x for `tools/`, `scripts/`, and the `ctest`-registered Python
  suites; `numpy`, `pydevices-audiodsp`, `pydevices-audioinstruments` and
  `pydevices-audioeffects` (all from TestPyPI - see
  [`tools/README.md`](tools/README.md)) for the instrument/effect tests
  and preview renders, and `flake8` for the `mpvst_lint` ctest.
  [`scripts/bootstrap.sh`](scripts/bootstrap.sh) creates a repo-local `.venv` with these.
- The Steinberg VST3 SDK, fetched by [`scripts/fetch-vst3-sdk.sh`](scripts/fetch-vst3-sdk.sh) into the
  gitignored `.deps/vst3sdk` (see [License](#license) for its terms).
- A `micropython-pydevices` checkout beside this one. Its `build_mp.py`
  builds the MicroPython engine, fetching MicroPython and the modules it
  needs, and the plug-in build takes the engine from its `builds/`.
- On WSL, building the Windows plug-in needs a reachable Windows host:
  [`scripts/install-plugin-windows.sh`](scripts/install-plugin-windows.sh) shells out to `powershell.exe`, and
  `scripts/bootstrap.sh` skips the Windows engine automatically when
  `/mnt/c/Users` or `powershell.exe` is not available.

## Getting started

A fresh clone has none of the external dependencies this repo needs - the
VST3 SDK, the engine, or REAPER for the DAW-driven tooling. With a
`micropython-pydevices` checkout beside this one, one command sets the rest
up:

```bash
./scripts/bootstrap.sh
```

See [scripts/README.md](scripts/README.md) for what it does and how to run
each step individually.

## Building and testing

The MicroPython sidecar is a MicroPython build like any other:
micropython-pydevices' `build_mp.py` with the `vst3-engine` variant (no
sockets, SSL or FFI; see [What the shipped engine cannot do](docs/how-it-works/security.md)) and this repository
among its modules, by path. It carries the `audioinstruments` and
`audioeffects` packages frozen in, pydevices (the editor's `appdev` and `multimer`),
audiodsp's DSP, audioif, LVGL and ulab:

```bash
../micropython-pydevices/build_mp.py --port windows --variant vst3-engine \
    --modules audioinstruments,audioeffects,audiodsp,audioif,lvgl,pydevices,ulab,$PWD \
    ENGINE_ICON=$PWD/installer/art/mpvst.ico
../micropython-pydevices/build_mp.py --port unix --variant vst3-engine \
    --modules audioinstruments,audioeffects,audiodsp,audioif,lvgl,pydevices,ulab,$PWD
```

It lands in `../micropython-pydevices/builds/<port>/vst3-engine/`, and the
plug-in build stages it from there (`MPVST_ENGINE_BUILDS` moves that). Rebuild
it when `usermods/`, audiodsp's C or the audioinstruments and audioeffects packages change. CMake
never notices a stale engine itself, but the `mpvst_engine_provenance` ctest
refuses one, from the record `build_mp.py` writes beside it.

Linux:

```bash
cmake -S . -B .build-linux -G Ninja
cmake --build .build-linux
ctest --test-dir .build-linux --output-on-failure
```

Windows, driven from WSL with the vendored CMake. `scripts/install-plugin-windows.sh`
wraps the build and installs the result into the per-user VST3 directory a
DAW scans:

```bash
./scripts/install-plugin-windows.sh
```

### A Python-only change needs no compiler

Adding an instrument to audioinstruments, editing a script, or changing what
the catalog says does not touch the plug-in binary. The packages are frozen
into the engine, but the bundle's own directory comes before the frozen
modules on the sidecar's `sys.path`, so packages staged into an installed
bundle override the engine's copy. To try a change without rebuilding the
engine or reconfiguring MSVC, stage the packages and rewrite the two metadata
files with the bundle's own engine (and delete the staged copies once the
engine is rebuilt, or they keep shadowing it):

```bash
B="$WIN_LOCALAPPDATA/Programs/Common/VST3/MPVST.vst3/Contents/x86_64-win"
for pkg in audioinstruments audioeffects; do
    rm -rf "$B/$pkg" && mkdir -p "$B/$pkg"
    (cd ../$pkg/lib/$pkg && tar -cf - --exclude=__pycache__ \
        --exclude='*.egg-info' --exclude=pyproject.toml .) | (cd "$B/$pkg" && tar -xf -)
done
(cd "$B" && ./mpvst-engine.exe -X heapsize=64M mpvst_scan_plugins.py \
         && ./mpvst-engine.exe -X heapsize=64M mpvst_catalog.py)
```

That is what `cmake --build` does for these two directories, minus the
compiler: the excludes match [`src/plugin/stage_lib.cmake`](src/plugin/stage_lib.cmake), and the two
scripts rewrite `moduleinfo.json` and `catalog.json`. A new instrument does
not need a REAPER rescan either - the soundtrack composer's projects load
the generic "MPVST Script Host" class with the script embedded in state, so
the only thing REAPER has to find is the staged package the sidecar imports.

### Reconfiguring the Windows build

`install-plugin-windows.sh` refuses to run without a configured build, which
is what you see after the Temp directory is cleaned or MSVC is reinstalled:

```bash
source scripts/windows-paths.sh && mpvst_load_windows_paths
'.deps/cmake-4.4.2-windows-x86_64/bin/cmake.exe' \
    -S "$(wslpath -w .)" -B "$(wslpath -w "$WIN_TEMP/mpvst-build")" \
    -G 'Visual Studio 18 2026'
```

The Linux CMake cache remembers the engine path. After switching engines,
reconfigure with
`cmake -S . -B .build-linux -U MPVST_MICROPYTHON_ENGINE`.

Steinberg hosting tools are off by default so a plug-in-only build does
not pull in editor-host dependencies. Enable them in a dedicated validator
build with `-DSMTG_ENABLE_VST3_HOSTING_EXAMPLES=ON`. `VST3_SDK_ROOT` may
point at an existing SDK checkout instead of the fetched one.

## Building a release

`VERSION` at the repository root is the single
source of truth - CMake and both packaging scripts read it, and editing it
re-runs CMake's configure step, so a binary and the archive around it
cannot disagree about which version they are.

```bash
./scripts/fetch-nsis.sh          # once, for the Windows installer
./scripts/package-linux.sh
./scripts/package-windows.sh
```

Each produces a versioned archive plus a SHA-256 sidecar under the ignored
`dist/`, after verifying the bundle carries its engine and bootstrap;
`package-windows.sh` also builds the installer, from the same staging tree
the archive is made from, so the two cannot ship different bytes. The
installer is built by NSIS, which cross-builds a Windows installer from
Linux - `fetch-nsis.sh` unpacks it into `.deps/` rather than installing it
on the machine, so it needs no root and removing `.deps` removes it.
See [MPVST on Windows](docs/guides/windows.md) and
[MPVST on Linux](docs/guides/linux.md) for the install paths and the
desktop-script security model.

This repository has no hosted CI. The `ctest` suite (lint included) is the
gate, and you run it locally before pushing; `scripts/bootstrap.sh` runs it as
its final verification step.

## Testing against a real DAW

`ctest` covers the plug-in with no DAW involved. Two further harnesses use
REAPER, and both need the packaged plug-in installed first because they
exercise the installed bundle:

```bash
./reaper/matrix/run-reaper-matrix.sh --platform windows
./reaper/matrix/run-reaper-matrix.sh --platform linux
```

The matrix drives REAPER headlessly through a startup ReaScript, covering
what only a real host can - FX chain add/remove, parameter automation,
project save/reload, macro resync. It overwrites `Scripts/__startup.lua`
in REAPER's resource path, so remove that file before using REAPER
interactively. A host with no live audio device only processes during a
render, so the matrix forces a short render before reading any status
parameter.

```bash
./scripts/check-cross-platform-parity.sh
```

Both smoke hosts render a fixed score through the real MicroPython sidecar
and the raw float32 PCM is compared. The two should produce an identical
SHA-256: the platforms agree exactly, not within a tolerance.

`./reaper.sh` renders and plays the example pieces; see
[reaper/README.md](reaper/README.md) and
[examples/soundtrack/README.md](examples/soundtrack/README.md).

## Dependencies are read-only

The engine's modules are consumed read-only. No build or formatting command
here writes into any of them, or into the MicroPython checkout, which
`build_mp.py` prepares once and builds into its own `builds/`.

## Testing layers

The suite tests the system at several boundaries:

- **Protocol tests** exercise shared-memory validation, rings, generations,
  state parsing and bounded failure without an engine or DAW.
- **Engine tests** check that the staged MicroPython binary has the required
  audio, UI and LVGL modules, and none of the capabilities
  [the security page](docs/how-it-works/security.md) rules out.
- **Smoke-host tests** load the real VST3 bundle in a minimal host and cover
  embedded state, rendering, effects, patches, reload, editor input, and every
  named class.
- **Python component sweeps** test instruments directly against the CPython
  `audiodsp` package, for faster feedback.
- **Fuzz tests** exercise mapping and state parsing. A portable driver runs in
  the normal suite, and optional Clang/libFuzzer targets allow deeper runs
  (`-DMPVST_ENABLE_LIBFUZZER=ON`, with interesting inputs kept in
  [`tests/fuzz/corpus`](tests/fuzz/corpus/)).
- **REAPER harnesses** cover what needs a real DAW: FX-chain changes,
  automation, project reload, installed bundles and cross-platform render
  parity.

## Rules that keep the plug-in safe

- **Never make the audio callback wait.** Late or missing output is silence
  plus telemetry. Review changes to `Processor::process()`, the protocol or
  `SidecarTransport` for allocation, locks, waits, I/O, logging, unbounded work
  and UI calls.
- **Treat the protocol headers as an ABI.** Two independently built binaries
  share them, and they encode exact sizes, offsets and alignments. Update the
  conformance tests with any intentional change.
- **Keep editor failure separate from audio failure.** The editor is optional,
  does no work while closed, and must never stop an instance rendering.
- **Process isolation is not a trust boundary.** It contains crashes, not
  permissions. Read [the security page](docs/how-it-works/security.md) before
  changing the engine's enabled modules.

## License

MIT, in [LICENSE](LICENSE), the same terms as the rest of PyDevices.

That covers this repository's own source. The Steinberg VST3 SDK is **not**
vendored here: `scripts/fetch-vst3-sdk.sh` clones it into `.deps/`, which is
ignored. It carries its own dual license (GPLv3 or a proprietary Steinberg
agreement), and anyone distributing a **built** plug-in binary has to satisfy
one of those two for the SDK it links. Building from source for your own use
changes nothing here.
