# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Play short plucked notes from MIDI input.

The smallest instrument script MPVST can load. It makes a synthio
synthesizer, gives each note a quick attack and a decaying envelope, and
presses and releases notes as MIDI arrives. You hear a pluck for every note
you play.

Needs: MPVST installed in a VST3 host. The script runs inside the
plug-in's engine, where `vstaudio` and `synthio` exist.

Run it: set `MPVST_SCRIPT_PATH` to this file's absolute path before starting
your DAW, then insert the "MPVST Script Host" instrument and play notes.

    export MPVST_SCRIPT_PATH=$HOME/instruments/pluck.py
    reaper &

To hear it with no host, render it offline with `InstrumentRun` from
`soundtrack/composer/harness.py`; the first-program guide shows how.

Tested on: CPython 3.12.3 on Linux (WSL 2) with pydevices-audiodsp 0.6.7,
through the offline `InstrumentRun`; not loaded in a DAW.
"""

import synthio
import vstaudio

# The plug-in reads these two names: this script has no macro knobs and a
# single patch.
MACRO_LABELS = ()
PATCHES = {0: ("Default", ())}

# Make the synthesizer at the host's sample rate, in stereo.
synth = synthio.Synthesizer(sample_rate=vstaudio.sample_rate(), channel_count=2)

# A fast attack and a decaying tail give the pluck.
env = synthio.Envelope(attack_time=0.005, decay_time=0.4, sustain_level=0.1, release_time=0.3)

# The notes now sounding, keyed by MIDI pitch, so a note-off can release them.
held = {}


def on_event(kind, channel, note_id, pitch, velocity, bend, position):
    # A note-on with a velocity starts a note.
    if kind == vstaudio.EVENT_NOTE_ON and velocity > 0:
        held[pitch] = synthio.Note(synthio.midi_to_hz(pitch), amplitude=velocity, envelope=env)
        synth.press(held[pitch])
    # A note-off, or a note-on with velocity zero, releases it.
    elif kind in (vstaudio.EVENT_NOTE_ON, vstaudio.EVENT_NOTE_OFF) and pitch in held:
        synth.release(held.pop(pitch))


# Hand MIDI events to the handler and the synthesizer to the host.
vstaudio.on_event(on_event)
vstaudio.output(synth)
