# Scripts

Maintainer and bootstrap automation - things a fresh clone or a release
needs, not day-to-day dev workflow (see [`../tools/`](../tools/README.md)
for that). Every script here is idempotent: safe to rerun.

- **`bootstrap.sh`** - one-shot setup for a fresh clone: fetches the VST3
  SDK, builds the engine with the micropython-pydevices checkout beside this
  one (`build_mp.py`; the command is in
  [`../docs/development.md`](../docs/development.md)), installs REAPER, then
  configures, builds, and runs the test suite as a final verification.
  Start here.
- **`fetch-vst3-sdk.sh`** - downloads the pinned VST3 SDK into `.deps/vst3sdk`.
- **`install-plugin-windows.sh [--no-build]`** - builds the Windows VST3
  bundle and installs it into the per-user VST3 directory any DAW scans.
- **`package-linux.sh`** / **`package-windows.sh`** - assemble the
  release archive for each platform's VST3 bundle.
- **`check-cross-platform-parity.sh`** - renders a fixed score through
  both platforms' real sidecars and compares the PCM byte for byte.

REAPER itself is a separate, deletable concern - its installer
(`install-reaper-portable.sh`) now lives in
[`../reaper/`](../reaper/README.md) alongside everything else that needs
it, not here. `bootstrap.sh` still calls it as one step of a fresh-clone
setup.
