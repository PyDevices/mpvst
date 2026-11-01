#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Render a piece offline to a WAV.

The render loop, tempo math, mixing and level report all live in audiodsp's
`audiorender`. What stays here is the part about this plug-in: instruments
load the way the engine loads them, as a script run against the `vstaudio`
shim, so the preview checks the same path the bounce takes. The shim drives
the same adapter as the engine, so normalized host values cross the same
MIDI-unit boundary in both. The program writes a stereo master WAV and
prints a report of peaks, RMS per section and simultaneous track counts.

Needs: Python 3 with numpy and `pydevices-audiodsp`,
`pydevices-audioinstruments` and `pydevices-audioeffects`, and an MPVST
install (set `MPVST_BUNDLE` if it is somewhere unusual).

Run it: from the `soundtrack` folder,

    python composer/preview.py --piece Perihelion
    python composer/preview.py --piece Automata automata.wav --stems stems

Tested on: CPython 3.12.3 on Linux (WSL 2) with pydevices-audiodsp 0.6.7 and
audioinstruments 0.5.0; `preview.py` and `reaper.py` run on several pieces.
"""

import sys
from pathlib import Path

# Find the soundtrack folder, and put it on the import path so the composer
# package beside this file imports. The harness adds audiodsp's lib/, which
# is where audiorender is.
SCRIPT_DIR = Path(__file__).resolve().parent
SOUNDTRACK = SCRIPT_DIR.parent
sys.path.insert(0, str(SOUNDTRACK))

from composer.harness import EffectRun, InstrumentRun  # noqa: E402
from composer.pieces import load_piece, patch_macros, piece_arg  # noqa: E402
from composer import vstaudio as shim  # noqa: E402

import audiorender  # noqa: E402

# Read which piece to render from the command line, and load it.
PIECE, ARGV = piece_arg(sys.argv[1:])
C, INSTRUMENTS = load_piece(PIECE)

SR = C.SAMPLE_RATE

#: audiorender's event kinds, as the vstaudio event values a script reads.
#: The two sets of numbers are separate, so the translation is a table
#: rather than an assumption that they match.
EVENT_OF = {
    audiorender.NOTE_ON: shim.EVENT_NOTE_ON,
    audiorender.NOTE_OFF: shim.EVENT_NOTE_OFF,
    audiorender.MACRO: shim.EVENT_PARAMETER,
    audiorender.PROGRAM: shim.EVENT_PROGRAM_CHANGE,
}


class ScriptVoice:
    """One instrument script, driven through the sidecar's own API.

    Values cross the same normalized-host-to-MIDI-provider conversion as the
    plug-in. That keeps this preview's contract check honest: the script sees
    the units the real sidecar sends, including MIDI's 128-step quantization.
    """

    def __init__(self, script_path):
        self.run = InstrumentRun(script_path, SR)

    def deliver(self, event, sample_position):
        _position, kind, data, value = event
        self.run.deliver(EVENT_OF[kind], 0, -1, data, value, 0.0,
                         sample_position)

    def pull_frames(self, frames):
        return self.run.pull_frames(frames)


class ShimClock(audiorender.Clock):
    """A transport the scripts can read, published where the shim keeps it."""

    def move_to(self, sample):
        # Move the clock, then publish its reading for scripts to read.
        audiorender.Clock.move_to(self, sample)
        shim._transport = self.reading


def voice_for(track, _clock):
    """Make the voice that plays a track's instrument script."""
    return ScriptVoice(INSTRUMENTS / track["script"])


def patch_for(track):
    """Patch 0's macros - what a macro the composition does not set means.

    Read the same way `reaper.py` reads it. If these two disagree the
    preview stops being a usable check on the bounce.
    """
    patch, _name = patch_macros(INSTRUMENTS / track["script"])
    return patch


def effects_for(track):
    """Yield one effect stage for each effect rack on a track."""
    for effect in track.get("effects", ()):
        name = "<%s: %s>" % (track["name"], effect["name"])

        def stage(pcm, effect=effect, name=name):
            run = EffectRun(effect["source"], pcm, SR, name)
            # Deliver all sixteen macro values, including the ones the rack
            # does not set. The plug-in always has a value for each
            # parameter and `reaper.py` writes all sixteen into the project,
            # so delivering fewer would make the preview disagree with the
            # bounce it exists to check.
            for index in range(16):
                run.deliver(shim.EVENT_PARAMETER, 0, -1, index,
                            C.macro_value(effect, index, 0.0), 0.0, 0)
            return run

        yield stage


def main():
    # Choose where the WAV goes, and whether to write a stem per track.
    out_path = SOUNDTRACK / "build" / ("%s_preview.wav" % PIECE)
    argv = list(ARGV)
    stems_dir = None
    if "--stems" in argv:
        stems_dir = Path(argv[argv.index("--stems") + 1])
        argv.remove("--stems")
        argv.remove(str(stems_dir))
        stems_dir.mkdir(parents=True, exist_ok=True)
    if argv:
        out_path = Path(argv[0])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Render the piece, and print the level report.
    master = audiorender.render(
        C, voice_for, patch_for=patch_for, effects_for=effects_for,
        clock=ShimClock(audiorender.TempoMap.of(C)), out=print,
        stems=stems_dir)
    ok = audiorender.report(master)

    # Write the master and exit non-zero if the report found a problem.
    audiorender.write_wav(out_path, master.data, master.sample_rate)
    print("\nwrote %s" % out_path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
