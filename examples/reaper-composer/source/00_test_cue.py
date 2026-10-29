# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Write a small test project that uses every part of the pipeline.

Builds eight bars, about sixteen seconds, with four instrument tracks
(TR-808, Minimoog, Juno-106, SH-101), two insert effects, a sidechain duck
and an effect on the master. It is small enough to render in a couple of
seconds and complete enough that, if it comes out clean, the routing works.
Swap instruments and effects into it to measure them. The program writes a
Reaper project and prints its path.

Needs: Python 3.8 or later. Opening or rendering the project needs MPVST
installed with Reaper (see `examples/bounce.py`).

Run it:

    python source/00_test_cue.py

Tested on: CPython 3.12.3 on Linux (WSL 2) with pydevices-audiodsp 0.6.7 and
audiocomponents 0.4.1; the project it wrote rendered in REAPER 7.79 through
`bounce.py`.
"""

import os
import sys

# Put the folder holding mpvst_composer on the import path.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mpvst_composer import (
    Chord,
    DrumPattern,
    MidiEvent,
    MidiPattern,
    Note,
    Project,
    Scale,
)
from mpvst_composer.backends.reaper import ReaperRenderer

# Change these to match your setup.
STEM = "00_test_cue"  # name of the project and its rendered WAV
BOUNCE_DIR = os.path.join(ROOT, "bounce")


def main():
    # Start a project in D minor at 118 bpm, 48 kHz, with room for reverb
    # tails at the end of the render.
    song = Project(name="Signal Room — Test Cue")
    song.set_key(Note.D, Scale.MINOR)
    song.tempo_markers.clear()
    song.add_tempo_marker(measure=1, bpm=118, signature=(4, 4))
    song.sample_rate = 48000
    song.render_tail_ms = 800
    song.render_file = os.path.join(BOUNCE_DIR, f"{STEM}.wav")

    # Four instrument tracks, with their levels and pan positions.
    drums = song.add_track("TR-808", instrument="tr808", patch="Default")
    drums.volume = 0.34
    drums.pan = 0.0

    bass = song.add_track("Minimoog Bass", instrument="minimoog", patch="Deep Bass")
    bass.volume = 0.26
    bass.pan = 0.0

    pad = song.add_track("Juno Pad", instrument="juno106", patch="Default")
    pad.volume = 0.16
    pad.pan = -0.08

    lead = song.add_track("SH-101 Hook", instrument="sh101", patch="Default")
    lead.volume = 0.20
    lead.pan = 0.12

    # An aux return wants the tail alone, and Reverb's Mix gives you that at
    # 2: the dry stays at unity up to Mix 1, then fades out.
    hall = song.add_aux_track("Hall", effect="Reverb", patch="Concert Hall", mix=2.0)
    hall.volume = 0.22
    pad.add_send(hall, send_level=0.28)
    lead.add_send(hall, send_level=0.18)

    # Insert effects: a chorus on the pad and tape saturation on the lead.
    pad.add_insert("Chorus", rate=0.55, depth=0.18, mix=0.35, delay_ms=9.0, tone_hz=4500.0)
    lead.add_insert("Saturation", mix=0.18, character="tape", drive_db=-1.68)

    # Kick -> bass key (channels 3/4) plus an audible volume duck.
    drums.add_send(bass, send_level=1.0, src_chan=0, dst_chan=2, mode=1)
    bass.add_insert(
        "NoiseGate",
        sidechain=True,
        duck=True,
        threshold_db=-28.0,
        attack_ms=1.0,
        hold_ms=40.0,
        release_ms=120.0,
        range_db=-10.0,
    )

    # The drum groove: kick on 1 and 3, a hi-hat on every half beat and an
    # open hi-hat leading into the next bar.
    groove = DrumPattern(start_measure=1, repeat=8, beats_per_bar=4)
    for bar_off in (0,):
        groove.add_hit(bar_off + 0.0, "kick", 118)
        groove.add_hit(bar_off + 2.0, "kick", 108)
        groove.add_hit(bar_off + 0.0, "closed_hihat", 72)
        groove.add_hit(bar_off + 0.5, "closed_hihat", 48)
        groove.add_hit(bar_off + 1.0, "closed_hihat", 64)
        groove.add_hit(bar_off + 1.5, "closed_hihat", 44)
        groove.add_hit(bar_off + 2.0, "closed_hihat", 70)
        groove.add_hit(bar_off + 2.5, "closed_hihat", 46)
        groove.add_hit(bar_off + 3.0, "open_hihat", 80)
        groove.add_hit(bar_off + 3.5, "closed_hihat", 52)
    groove.humanize(velocity_jitter=6, timing_jitter_beats=0.006)
    drums.add_pattern(groove)

    # The bass, one bar repeated eight times.
    bass_pat = MidiPattern(start_measure=1, repeat=8, beats_per_bar=4)
    # Held roots with a fifth answer — leaves space for the duck.
    bass_pat.add_event(MidiEvent(0.0, 1.75, degree=1, octave=1, velocity=110))
    bass_pat.add_event(MidiEvent(2.0, 1.75, degree=5, octave=1, velocity=100))
    bass.add_pattern(bass_pat)

    # The pad plays a held triad on the tonic.
    triad = song.theory.get_chord_degrees(1, Chord.TRIAD)
    pad_pat = MidiPattern(start_measure=1, repeat=8, beats_per_bar=4)
    pad_pat.add_chord(0.0, 3.9, 1, triad, octave=4, velocity=78)
    pad.add_pattern(pad_pat)

    # The lead plays a short hook.
    hook = MidiPattern(start_measure=1, repeat=8, beats_per_bar=4)
    hook.add_event(MidiEvent(0.5, 0.45, degree=5, octave=4, velocity=96))
    hook.add_event(MidiEvent(1.0, 0.45, degree=6, octave=4, velocity=90))
    hook.add_event(MidiEvent(1.5, 0.9, degree=1, octave=5, velocity=100))
    hook.add_event(MidiEvent(2.75, 0.4, degree=7, octave=4, velocity=86))
    hook.add_event(MidiEvent(3.25, 0.65, degree=5, octave=4, velocity=92))
    hook.humanize(velocity_jitter=5, timing_jitter_beats=0.008)
    lead.add_pattern(hook)

    # Duck the bass on every kick.
    song.apply_sidechain_duck(
        drums, bass, hit_type="kick",
        depth=0.42, attack_beats=0.02, hold_beats=0.08, release_beats=0.22,
    )

    # Limit the whole mix on a bus that every track feeds.
    mix = song.add_mix_bus(
        "Mix Bus",
        ceiling_db=-1.6,
        gain_db=15.5,
        lookahead_ms=2.0,
        release_ms=180.0,
        true_peak=True,
        knee_db=1.5,
    )
    mix.volume = 1.0
    song.route_to_mix_bus(mix)

    # Write the Reaper project and say where it is.
    os.makedirs(BOUNCE_DIR, exist_ok=True)
    rpp = os.path.join(BOUNCE_DIR, f"{STEM}.rpp")
    song.render(rpp, ReaperRenderer)
    print(f"wrote {rpp}")


if __name__ == "__main__":
    main()
