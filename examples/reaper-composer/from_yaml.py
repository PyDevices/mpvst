# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Write a song in YAML instead of Python.

Reads a YAML file that names some patterns and says where they play, then
drives the same `mpvst_composer` library the Python examples use, so
anything you can express here is a real project with real routing. It is
deliberately smaller than the Python API: patterns, tracks, sends, an aux
track or two and a mix bus, which is what a first song needs. When you
outgrow it, `mpvst_composer/mpvst_composer_guide.md` covers the library
from the inside. A `.rpp` output is a Reaper project; a `.wav` output is
rendered here with no DAW. Success is the "wrote ..." line and the file.

A song file looks like this:

    title: Interlock
    tempo: 104
    key: D
    scale: dorian

    patterns:
      figure:                       # [beat, length, degree, octave]
        - [0.0, 0.5, 1, 4]
      pulse:                        # [beat, drum]
        - [0.0, kick]

    tracks:
      - name: Pluck
        instrument: clavichord
        gain_db: -6
        play:
          - {bar: 1, pattern: figure, repeat: 8}
          - {bar: 9, pattern: figure, repeat: 8, offset: 0.5}

Any other key on a track is one of the instrument's own macros, such as
`decay: 0.9` or `cutoff_hz: 800`, named the way the instrument names it and
applied over the patch. Inserts and aux effects work the same way.

`degree` is a step of the scale: 1 is the tonic and 8 is the octave above.
A drum pattern uses names (`kick`, `snare`, `closed_hihat`), and the
instrument's own note map decides which key each one is. `offset` shifts
every beat in a placement, so two tracks playing one pattern half a beat
apart interlock into a line neither is playing.

Needs: PyYAML (`pip install pyyaml`). For a `.wav` output, also numpy and
`pydevices-audiodsp`, `pydevices-audioinstruments` and
`pydevices-audioeffects`.

Run it:

    python from_yaml.py source/interlock.yaml
    python from_yaml.py source/interlock.yaml interlock.wav

Tested on: CPython 3.12.3 on Linux (WSL 2) with PyYAML 6.0.3, numpy 2.5.4
and pydevices-audiodsp 0.6.7 and audioinstruments 0.5.0. Rendered
`interlock.yaml` to a WAV with every track sounding; the `.rpp` output was
not written.
"""

from __future__ import annotations

import sys

import yaml

from mpvst_composer import DrumPattern, MidiEvent, MidiPattern, Note, Project, Scale
from mpvst_composer.backends.offline import OfflineRenderer
from mpvst_composer.backends.reaper import ReaperRenderer


def scale_of(name):
    """Look up a Scale by name, or exit listing the names that exist."""
    # Names are upper case in the enum, with underscores for hyphens.
    key = str(name).replace("-", "_").upper()
    try:
        return getattr(Scale, key)
    except AttributeError:
        raise SystemExit("unknown scale %r - try %s"
                         % (name, ", ".join(s.name.lower() for s in Scale)))


def note_of(name):
    """Look up a key by name, or exit if there is no such note."""
    # Sharps are spelled with an s in the Note enum.
    key = str(name).replace("#", "s").replace("b", "b").capitalize()
    try:
        return getattr(Note, key)
    except AttributeError:
        raise SystemExit("unknown key %r" % name)


def is_drum(rows):
    """A hit names its drum; a note gives a length. Told apart by the second
    column's type, so both may carry an optional trailing velocity."""
    return bool(rows) and isinstance(rows[0][1], str)


def build_pattern(rows, bar, repeat, offset, beats_per_bar):
    """One placement of a named pattern, shifted by `offset` beats."""
    if is_drum(rows):
        pattern = DrumPattern(start_measure=bar, repeat=repeat,
                              beats_per_bar=beats_per_bar)
        for row in rows:
            beat, hit = row[0], row[1]
            pattern.add_hit(float(beat) + offset, str(hit),
                            int(row[2]) if len(row) > 2 else 100)
        return pattern
    pattern = MidiPattern(start_measure=bar, repeat=repeat,
                          beats_per_bar=beats_per_bar)
    for row in rows:
        beat, length, degree, octave = row[0], row[1], row[2], row[3]
        pattern.add_event(MidiEvent(
            start_beat=float(beat) + offset, length_beats=float(length),
            degree=int(degree), octave=int(octave),
            velocity=int(row[4]) if len(row) > 4 else 100))
    return pattern


def load(path):
    """Read a YAML file and build the project it describes."""
    with open(path, "r", encoding="utf-8") as handle:
        return build(yaml.safe_load(handle))


def build(document):
    """Build a project from an already-parsed document.

    Split out from `load` so a composition written in Python can produce the
    same dictionary and go either way with it - straight to a project, or out
    to YAML for someone to read and edit. `source/canon_16.py` does both.
    """
    # Start the project and set its key, meter and opening tempo.
    song = Project(name=document.get("title", "Untitled"))
    song.set_key(note_of(document.get("key", "C")),
                 scale_of(document.get("scale", "major")))
    beats_per_bar = int(document.get("beats_per_bar", 4))
    song.add_tempo_marker(measure=1, bpm=float(document.get("tempo", 120)),
                          signature=(beats_per_bar, 4))
    # Add any later tempo changes.
    for marker in document.get("tempo_changes") or []:
        song.add_tempo_marker(measure=int(marker["bar"]),
                              bpm=float(marker["tempo"]))

    # Make the aux tracks first, so a track's sends can find them by name.
    patterns = document.get("patterns") or {}
    auxes = {}
    for spec in document.get("aux_tracks") or []:
        options = {k: v for k, v in spec.items()
                   if k not in ("name", "effect", "patch")}
        auxes[spec["name"]] = song.add_aux_track(
            spec["name"], effect=spec["effect"], patch=spec.get("patch"),
            **options)

    #: Keys a track spec uses for itself. Anything else is taken as one of
    #: the instrument's macros, named the way the instrument names it.
    track_keys = {"name", "instrument", "patch", "gain_db", "pan",
                  "inserts", "sends", "play"}

    # Make each track: its instrument, level, pan, inserts, sends and the
    # places its patterns play.
    tracks = []
    for spec in document.get("tracks") or []:
        options = {k: v for k, v in spec.items() if k not in track_keys}
        track = song.add_track(spec["name"], instrument=spec["instrument"],
                               patch=spec.get("patch", "Default"), **options)
        if "gain_db" in spec:
            track.volume = 10.0 ** (float(spec["gain_db"]) / 20.0)
        if "pan" in spec:
            track.pan = float(spec["pan"])
        for insert in spec.get("inserts") or []:
            options = {k: v for k, v in insert.items()
                       if k not in ("effect", "patch")}
            track.add_insert(insert["effect"], patch=insert.get("patch"),
                             **options)
        for send in spec.get("sends") or []:
            target = auxes.get(send["to"])
            if target is None:
                raise SystemExit("%s sends to %r, which is not an aux track"
                                 % (spec["name"], send["to"]))
            track.add_send(target, float(send.get("level", 1.0)))
        for placement in spec.get("play") or []:
            name = placement["pattern"]
            if name not in patterns:
                raise SystemExit("%s plays %r, which is not in patterns"
                                 % (spec["name"], name))
            track.add_pattern(build_pattern(
                patterns[name], int(placement["bar"]),
                int(placement.get("repeat", 1)),
                float(placement.get("offset", 0.0)), beats_per_bar))
        tracks.append(track)

    # Put any effects on the master.
    for effect in document.get("master_effects") or []:
        options = {k: v for k, v in effect.items()
                   if k not in ("effect", "patch")}
        song.add_master_effect(effect["effect"], patch=effect.get("patch"),
                               **options)

    # Add a mix bus and route every track through it, if asked.
    mix = document.get("mix_bus")
    if mix:
        bus = song.add_mix_bus(**{k: v for k, v in mix.items()
                                  if k != "name"})
        song.route_to_mix_bus(bus)
    return song


def renderer_for(path):
    """The backend that writes `path`, chosen by what you asked it to write.

    A `.wav` is rendered here through the CPython audio packages; anything
    else is a Reaper project. Asking for the audio is asking for the offline
    path, so there is no flag to forget.
    """
    return OfflineRenderer if path.lower().endswith(".wav") else ReaperRenderer


def main():
    # Read the command line: the song, and optionally where to write it.
    if len(sys.argv) < 2:
        raise SystemExit("usage: from_yaml.py <song.yaml> [out.rpp|out.wav]")
    source = sys.argv[1]
    song = load(source)
    # Default to a Reaper project beside the song.
    out = sys.argv[2] if len(sys.argv) > 2 else source.rsplit(".", 1)[0] + ".rpp"
    # Render, and say what was written.
    song.render(out, renderer_for(out))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
