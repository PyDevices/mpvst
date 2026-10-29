# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Write songs in Python and render them to Reaper projects or WAV files.

`mpvst_composer` is a small composing library. You build a `Project`, add
tracks that play MPVST instruments, fill them with note and drum patterns
written as scale degrees, route sends and a mix bus, and render. A Reaper
backend writes a project for a DAW to play; an offline backend renders a WAV
here with no DAW. `mpvst_composer_guide.md` in this folder is the full guide.

Needs: Python 3.8 or later. The Reaper backend needs an MPVST install for
its class IDs; the offline backend needs numpy and `pydevices-audiodsp`,
`pydevices-audioinstruments` and `pydevices-audioeffects`.

Run it: import it from a script beside this folder.

    from mpvst_composer import Note, Project, Scale

The scripts in `source/` show it in use, and `from_yaml.py` drives it from a
YAML file.

Tested on: CPython 3.12.3 on Linux (WSL 2) with PyYAML 6.0.3, numpy 2.5.4
and pydevices-audiodsp 0.6.7 and audiocomponents 0.4.1. Exercised by
`converge.py`, `canon_16.py` and `from_yaml.py`.
"""

from .theory import Note, Scale, TheoryEngine, Chord
from .models import (
    Project, Track, AuxTrack, MidiPattern, MidiEvent, MidiControlEvent,
    DrumPattern, DrumEvent, DRUM_MAP, MacroAutomation, AutomationPoint,
    VolumeAutomation, PanAutomation, resolve_drum_note,
)

__all__ = [
    "Note",
    "Scale",
    "TheoryEngine",
    "Chord",
    "Project",
    "Track",
    "AuxTrack",
    "MidiPattern",
    "MidiEvent",
    "MidiControlEvent",
    "DrumPattern",
    "DrumEvent",
    "DRUM_MAP",
    "MacroAutomation",
    "AutomationPoint",
    "VolumeAutomation",
    "PanAutomation",
    "resolve_drum_note",
]
