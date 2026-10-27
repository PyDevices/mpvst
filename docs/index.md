# MPVST

MPVST is a VST3 plug-in whose instruments and effects are MicroPython-compatible scripts. One bundle ships a whole library: every `audioinstruments` module and every `audioeffects` class appears in your DAW's browser under its own name and category, next to two generic **MPVST Script Host** classes that run any script you point them at.

Windows and Linux both ship, and the same project renders identical audio on both. Every instance runs its Python in a separate process, so a script that loops forever or runs out of memory takes down its own process and is restarted, not your DAW. The audio callback itself stays native and real-time safe.

## Get started

- [Install](get-started/install.md): the release files for each platform, and rescanning in your host.
- [First program](get-started/first-program.md): play a library instrument, then run a 20-line script of your own.

## Guides

- [Write your own instruments and effects](guides/write-a-script.md)
- [Hear what you wrote](guides/hear-what-you-wrote.md): rendering with and without a DAW.
- [Generate projects from code](guides/generate-projects.md)
- [MPVST on Windows](guides/windows.md)
- [MPVST on Linux](guides/linux.md)

## Reference

- [Parameters and state](reference/parameters-and-state.md)
- [Script reference](reference/script-api.md)
- [Protocol reference](reference/ipc-protocol.md)
- [Known limitations](reference/known-limitations.md)

## How it works

- [How MPVST works](how-it-works/index.md)
- [The editor](how-it-works/editor.md)
- [What the shipped engine cannot do](how-it-works/security.md)

## Changelog

- [Changelog](changelog.md) and the [roadmap](../ROADMAP.md).

To build MPVST from source, see [CONTRIBUTING.md](../CONTRIBUTING.md).
