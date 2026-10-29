# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Render a Minimoog line that changes patch halfway.

A test fixture rather than a piece of music. It exists to prove that a MIDI
Program Change reaches an instrument script and re-applies its patch.

The design point is that both halves play *exactly the same notes*. Bars
1-8 and bars 9-16 are byte-identical material, so any measured difference
between them can only have come from the patch change at bar 9. If the
program change did nothing, the two halves would measure the same.

  bars 1-8   Patch 2 "Deep Bass"      cutoff 0.2,  resonance 0.35, drive 0.15
  bars 9-16  Patch 3 "Screaming Lead" cutoff 0.55, resonance 0.75, drive 0.6

(Program Change 1 selects Patch 2: the wire value is zero-based, and DAWs
display it one-based.) Those two patches differ mostly in the filter, so
the expected evidence is a large jump in high-frequency energy at bar 9,
with the note material unchanged.

Minimoog is monophonic - MAX_VOICES = 1 - so this is a single line with no
overlaps anywhere.

Needs: Python 3 with numpy and `pydevices-audiodsp`,
`pydevices-audioinstruments` and `pydevices-audioeffects`, and an MPVST
install (set `MPVST_BUNDLE` if it is somewhere unusual). Opening the Reaper
project this feeds needs Reaper and MPVST.

Run it: from the `soundtrack` folder, render the piece to a WAV, or write its
Reaper project.

    python composer/preview.py --piece PatchTest patchtest.wav
    python composer/reaper.py --piece PatchTest

Success is a level report ending in "wrote patchtest.wav" with no failed checks.

Tested on: CPython 3.12.3 on Linux (WSL 2), rendered with
`composer/preview.py` using pydevices-audiodsp 0.6.7 and audiocomponents
0.4.1.
"""

# Change these to suit the piece.
TITLE = "Patch_Test"
INSTRUMENTS_DIR = "../../lib/instruments"
SAMPLE_RATE = 48000
MASTER_GAIN_DB = -3.0
ACTIVE_LIMIT = 1
CLIMAX_SECTION = "B Screaming Lead"
BEATS_PER_BAR = 4
TOTAL_BARS = 16
TAIL_SECONDS = 4.0

TEMPO_MAP = [(0.0, 100.0)]

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


A1, C2, D2, E2, G2, A2 = 33, 36, 38, 40, 43, 45

# Two-bar riff in eighths. Notes are 0.45 long against a 0.5 grid, so a
# repeated pitch never overlaps itself.
RIFF = [
    (0.0, A1), (0.5, A1), (1.0, A2), (1.5, A1),
    (2.0, C2), (2.5, A1), (3.0, E2), (3.5, D2),
    (4.0, A1), (4.5, A1), (5.0, A2), (5.5, G2),
    (6.0, E2), (6.5, D2), (7.0, C2), (7.5, A1),
]


def riff_notes():
    """The same eight repetitions across both halves - deliberately."""
    out = []
    for repeat in range(8):                      # 8 x 2 bars = 16 bars
        base = bar(1 + repeat * 2)
        for offset, pitch in RIFF:
            accent = 0.15 if offset in (0.0, 4.0) else 0.0
            out.append((base + offset, 0.45, pitch, 0.7 + accent))
    return out


TRACKS = [
    {
        "name": "Minimoog", "script": "minimoog.py", "gain_db": -6.0,
        "pan": 0.0, "notes": riff_notes(),
        # No macros set at all: every one resolves to the instrument's
        # Patch 0, and the program changes below replace them wholesale.
        # That is the point - if patches did not work, this would be
        # sixteen macros of whatever the fallback happened to be.
        "macros": {},
        "vol": [(bar(1), 1.0)],
        "macro_env": {},
        # (beat, program). Zero-based on the wire: 1 is "Deep Bass",
        # 2 is "Screaming Lead".
        "programs": [(bar(1), 1), (bar(9), 2)],
    },
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
    ("A Deep Bass", bar(1), bar(9)),
    ("B Screaming Lead", bar(9), bar(17)),
]
