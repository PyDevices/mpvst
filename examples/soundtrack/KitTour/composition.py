# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Render a drum part that walks through five drum machines.

A fixture rather than a piece of music, in the same spirit as Patch Test: the
groove never changes, so everything you hear change came from the machine
playing it. It walks the package's drum machines - Rhythm808, Rhythm909,
Rhythm606, Rhythm78 and ElectronicDrums5 - four bars each at 120, one track
per machine, each track playing only its own four bars.

The part is written in General MIDI, which every machine in the package
answers, and it deliberately reaches past the notes they all share:

  kick 36, snare 38                          every machine has these
  hats 42/46, crash 49                       all but ElectronicDrums5
  cowbell 56, congas 62/63                   Rhythm808 and Rhythm78 only

So the backbone holds all the way through while the decoration comes and goes.
A machine with no cowbell is silent on the cowbell - it does not answer with
the nearest drum it has. The crash lands on the downbeat of every switch, so
the change announces itself.

A drum machine's macros are its own, so each track plays its patch 0; nothing
here sets a macro.

Needs: Python 3 with numpy and `pydevices-audiodsp`,
`pydevices-audioinstruments` and `pydevices-audioeffects`, and an MPVST
install (set `MPVST_BUNDLE` if it is somewhere unusual). Opening the Reaper
project this feeds needs Reaper and MPVST.

Run it: from the `soundtrack` folder, render the piece to a WAV, or write its
Reaper project.

    python composer/preview.py --piece KitTour kittour.wav
    python composer/reaper.py --piece KitTour

Success is a level report ending in "wrote kittour.wav" with no failed checks.

Tested on: CPython 3.12.3 on Linux (WSL 2), rendered with
`composer/preview.py` using pydevices-audiodsp 0.6.7 and
audioinstruments 0.5.0.
"""

# Change these to suit the piece.
TITLE = "Kit_Tour"
SAMPLE_RATE = 48000
MASTER_GAIN_DB = -3.0
ACTIVE_LIMIT = 1
CLIMAX_SECTION = "ElectronicDrums5"   # measured: the loudest of the five
BEATS_PER_BAR = 4
BARS_PER_KIT = 4
TAIL_SECONDS = 3.0

#: The machines, in the order they play: a section name and the instrument
#: script behind it. Block N of four bars belongs to index N.
KITS = [
    ("Rhythm808", "rhythm808.py"), ("Rhythm909", "rhythm909.py"),
    ("Rhythm606", "rhythm606.py"), ("Rhythm78", "rhythm78.py"),
    ("ElectronicDrums5", "electronic_drums5.py"),
]

TOTAL_BARS = BARS_PER_KIT * len(KITS)
TEMPO_MAP = [(0.0, 120.0)]

TOTAL_BEATS = float(TOTAL_BARS * BEATS_PER_BAR)


# Convert a position in beats to seconds, following the tempo map.
def beats_to_seconds(beat):
    seconds = 0.0
    for index, (start, bpm) in enumerate(TEMPO_MAP):
        end = TEMPO_MAP[index + 1][0] if index + 1 < len(TEMPO_MAP) else None
        if end is None or beat <= end:
            return seconds + max(0.0, beat - start) * 60.0 / bpm
        seconds += (end - start) * 60.0 / bpm
    return seconds


SONG_SECONDS = beats_to_seconds(TOTAL_BEATS)
RENDER_SECONDS = SONG_SECONDS + TAIL_SECONDS


def bar(n, beat=0.0):
    return (n - 1) * BEATS_PER_BAR + beat


KICK, SNARE, HAT_C, HAT_O, CRASH = 36, 38, 42, 46, 49
COWBELL, CONGA_HI, CONGA_MID = 56, 62, 63


def groove_notes():
    """The same bar, twenty times over. Only the machine underneath changes."""
    out = []
    for index in range(TOTAL_BARS):
        first = bar(index + 1)
        in_kit = index % BARS_PER_KIT          # 0-3 within this kit's block

        # The switch announces itself: a crash on the downbeat of each kit.
        if in_kit == 0:
            out.append((first, 1.0, CRASH, 0.8))

        # Backbone - every kit answers all four of these.
        for beat in (0.0, 2.0):
            out.append((first + beat, 0.3, KICK, 0.9))
        if in_kit % 2 == 1:
            out.append((first + 2.75, 0.3, KICK, 0.6))
        for beat in (1.0, 3.0):
            out.append((first + beat, 0.3, SNARE, 0.85))
        for eighth in range(8):
            beat = eighth * 0.5
            open_hat = (eighth == 7 and in_kit % 2 == 0)
            out.append((first + beat, 0.2,
                        HAT_O if open_hat else HAT_C,
                        0.5 if eighth % 2 == 0 else 0.35))

        # Decoration - here is where the kits stop agreeing.
        if in_kit in (1, 3):
            out.append((first + 2.5, 0.2, COWBELL, 0.6))
        if in_kit == 2:
            out.append((first + 1.75, 0.2, CONGA_HI, 0.55))
            out.append((first + 3.25, 0.2, CONGA_MID, 0.5))
    return out


def block_notes(index):
    """The groove notes that fall in machine `index`'s four bars."""
    first = bar(1 + BARS_PER_KIT * index)
    last = bar(1 + BARS_PER_KIT * (index + 1))
    return [n for n in groove_notes() if first <= n[0] < last]


TRACKS = [
    {
        "name": name, "script": script, "gain_db": -5.0,
        "pan": 0.0, "notes": block_notes(index),
        # Nothing set: each machine plays its own patch 0.
        "macros": {},
        "vol": [(bar(1), 1.0)],
        "macro_env": {},
    }
    for index, (name, script) in enumerate(KITS)
]


def _db(x):
    return 10.0 ** (x / 20.0)


# The linear gain of a track at a beat: its mix gain times its volume envelope.
def track_gain(track, beat):
    base = _db(track["gain_db"])
    points = track["vol"]
    if not points:
        return base
    if beat <= points[0][0]:
        return base * points[0][1]
    for i in range(len(points) - 1):
        b0, m0 = points[i]
        b1, m1 = points[i + 1]
        if beat <= b1:
            f = (beat - b0) / (b1 - b0) if b1 > b0 else 1.0
            return base * (m0 + (m1 - m0) * f)
    return base * points[-1][1]


# A macro's value at a beat: its automation, or its fixed setting.
def macro_value(track, index, beat):
    env = track["macro_env"].get(index)
    if not env:
        return track["macros"].get(index, 0.5)
    if beat <= env[0][0]:
        return env[0][1]
    for i in range(len(env) - 1):
        b0, v0 = env[i]
        b1, v1 = env[i + 1]
        if beat <= b1:
            f = (beat - b0) / (b1 - b0) if b1 > b0 else 1.0
            return v0 + (v1 - v0) * f
    return env[-1][1]


# Count the tracks with a note sounding at a beat.
def active_track_count(beat):
    count = 0
    for track in TRACKS:
        for start, dur, _pitch, _vel in track["notes"]:
            if start <= beat < start + dur:
                count += 1
                break
    return count


SECTIONS = [
    (name, bar(1 + BARS_PER_KIT * index), bar(1 + BARS_PER_KIT * (index + 1)))
    for index, (name, _script) in enumerate(KITS)
]
