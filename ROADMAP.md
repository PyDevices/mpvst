# Roadmap

Planned work, in no particular order:

- **Wet/dry and sidechain for effects.** A mix parameter on every effect, and
  sidechain input buses for the effects that want one.
- **64-bit audio.** Float64 processing for hosts that ask for it, and a
  floating-point audio graph behind it.
- **macOS.** Signed and notarised universal bundles.
- **Coverage-guided fuzzing.** [`tests/fuzz`](tests/fuzz/) already exposes libFuzzer entry
  points (`-DMPVST_ENABLE_LIBFUZZER=ON` on clang); running them is the plan.
- **CI.** A workflow that builds the plug-in and runs its tests on every
  change.
- **The C modules in the shape every PyDevices module has.** `vstaudio` and
  `vstui` keep their C under `src/`, gain a simpletest each and a `__revision__`.

Bugs, and things you need that don't work yet, go to
[issues](https://github.com/PyDevices/mpvst/issues).
