# Icon art

`mpvst.ico` is mpvst's icon: the PyDevices board with a turned-up knob in
its centre, at 16, 24, 32, 48, 64, 128 and 256 px.
[make-placeholder-icon.py](make-placeholder-icon.py) drew the placeholder that
came before it; nothing in the build runs it, and nothing downstream cares
where the `.ico` came from. Replacing it is one file.

Two Windows surfaces read this one file, and both of them used to carry
somebody else's mark:

- **The sidecar executable.** The engine build passes it as `ENGINE_ICON=` to
  MicroPython's make (CONTRIBUTING.md); the windows vst3-engine variant in
  micropython-pydevices swaps the port's resource rule for one that compiles
  this file, so the checkout is never edited. Without it the engine wears
  MicroPython's logo.
- **The bundle folder in Explorer.** [`src/plugin/CMakeLists.txt`](../../src/plugin/CMakeLists.txt) sets
  `SMTG_PACKAGE_ICON_PATH`, which the VST3 SDK copies into the bundle root as
  `PlugIn.ico` with a `desktop.ini` beside it. Without it the SDK defaults to
  Steinberg's VST logo.

Neither is the installer's own icon, which is deliberately NSIS stock.

To replace it: put a real `.ico` here under the same name. It must be a true
Windows icon - `build_mp.sh` checks the `00 00 01 00` header and refuses a
renamed `.png` rather than letting `windres` fail deep in a build. Ship at
least 16, 32, 48 and 256 px; the small sizes are what a taskbar and a file
list actually show.
