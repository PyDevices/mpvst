import synthio
import vstaudio

MACRO_LABELS = ()
PATCHES = {0: ("Default", ())}
synth = synthio.Synthesizer(sample_rate=vstaudio.sample_rate(), channel_count=2)
env = synthio.Envelope(attack_time=0.005, decay_time=0.4, sustain_level=0.1, release_time=0.3)
held = {}


def on_event(kind, channel, note_id, pitch, velocity, bend, position):
    if kind == vstaudio.EVENT_NOTE_ON and velocity > 0:
        held[pitch] = synthio.Note(synthio.midi_to_hz(pitch), amplitude=velocity, envelope=env)
        synth.press(held[pitch])
    elif kind in (vstaudio.EVENT_NOTE_ON, vstaudio.EVENT_NOTE_OFF) and pitch in held:
        synth.release(held.pop(pitch))


vstaudio.on_event(on_event)
vstaudio.output(synth)
