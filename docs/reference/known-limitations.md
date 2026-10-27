# Known limitations

- There is no host-visible diagnostic string. Both editors show only the ready and error parameters; the bounded diagnostic text is available through the transport API.
- The editor is one generic panel. Per-script panels, a shared knob widget, meters, and resizable or zoomable editors are not built.
- State embeds one source file, not a dependency bundle. Imports must resolve in the sidecar's own MicroPython environment.
- `MPVST_SCRIPT_PATH` is process-wide, so two instances that follow a developer file cannot follow different scripts; they re-read it on restart and on save. A project that needs per-instance scripts embeds them in state instead, which `reaper/matrix/build_effect_project.py` shows by writing the chunks directly.
- The 2,080 hidden MIDI parameters are standards-compliant and pass the VST3 validator, but their cost at scan and project load hasn't been measured in real DAWs.
- The installers are not code signed, so Windows SmartScreen warns on first run. macOS is not a target.
- Real-time playback on Linux hardware hasn't been exercised.
- REAPER is the only DAW tested.

Planned work is in [ROADMAP.md](../../ROADMAP.md).
