# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Compose and preview the soundtrack pieces beside this package.

A piece is a directory holding `composition.py`, the tempo map, the notes,
the gains and the automation, plus any effects that piece alone uses. From
one of those you can go two ways: a Reaper project, or a WAV rendered here
without Reaper. `preview` renders offline through the same DSP the plug-in
runs, using the CPython build of audiodsp, so you can hear a change without
opening a DAW. `reaper` writes the project you then hand to
`examples/bounce.py`.

This is not the composer in `examples/reaper-composer/`. That one is a
framework you write a song with; this one reads songs already written as
modules.

Needs: Python 3 with numpy and `pydevices-audiodsp`,
`pydevices-audioinstruments` and `pydevices-audioeffects`, and an MPVST
install (set `MPVST_BUNDLE` if it is somewhere unusual).

Run it: from the `soundtrack` folder,

    python composer/reaper.py --piece Perihelion
    python composer/preview.py --piece Perihelion perihelion.wav

Tested on: CPython 3.12.3 on Linux (WSL 2) with pydevices-audiodsp 0.6.7 and
audiocomponents 0.4.1; `preview.py` and `reaper.py` run on several pieces.
"""
