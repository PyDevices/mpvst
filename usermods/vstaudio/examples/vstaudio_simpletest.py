# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Play a tone from the first MIDI note the host sends.

A script becomes an instrument by registering two things with vstaudio: a
function that receives the host's MIDI events, and a source of audio for the
plug-in to play. This one hands every note-on to a synthesizer and every
note-off to its release.

Needs: the MPVST plug-in, or a built tree to run it against.

Run it: load the script in MPVST's Script Host, or from a build tree:
    mpvst_smoke_host <bundle>.vst3 --instrument-script vstaudio_simpletest.py

Tested on: the MPVST engine for Windows, through the smoke host.
"""

import synthio
import vstaudio

# Print which build of the module this is, as an issue report would want.
print("vstaudio", vstaudio.__revision__)

# One synthesizer at the host's sample rate, in stereo.
synth = synthio.Synthesizer(sample_rate=vstaudio.sample_rate(), channel_count=2)
notes = {}


def on_event(event_type, channel, note_id, pitch, velocity, tuning, sample_position):
    # A note-on presses a note at the pitch and velocity the host sent.
    if event_type == vstaudio.EVENT_NOTE_ON and velocity > 0.0:
        note = synthio.Note(synthio.midi_to_hz(pitch + tuning), amplitude=velocity)
        notes[(channel, pitch)] = note
        synth.press(note)
    # A note-off releases the note it started.
    elif event_type == vstaudio.EVENT_NOTE_OFF:
        note = notes.pop((channel, pitch), None)
        if note is not None:
            synth.release(note)


# Register the event function, then the audio the plug-in plays.
vstaudio.on_event(on_event)
vstaudio.output(synth)
