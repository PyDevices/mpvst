# First program

You can play a library instrument in two minutes, and run a script of your own in a few more. Both start from an installed bundle: see [Install](install.md).

## Play a library instrument

MPVST does not install as one plug-in. Every instrument and effect in the library appears in your FX browser under its own name and category. Search for **TR-808**, **Minimoog** or **Tape Delay** and drop it on a track like any other VST3.

Its editor has a patch selector, a bypass switch, an engine-status light and a slider per macro, labelled with whatever that instrument calls its knobs. Click a control to focus it, then scroll: sideways adjusts it, up and down move between controls. If your host provides no editor, its generic parameter editor reaches the same parameters.

The names are not compiled in. Each is a two-line Python script the plug-in builds when you insert it, and your project saves that script as plain text. Adding an instrument is writing a script, not rebuilding anything.

## Run a script of your own

The two **MPVST Script Host** entries (one instrument, one effect) run whatever script you point them at. With none pointed at them the instrument host makes no sound, so an empty slot you did not choose is easy to spot, and the effect host passes its input through unchanged.

This is [`examples/pluck.py`](../../examples/pluck.py), a plucked instrument in about twenty lines:

```python
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
```

Set `MPVST_SCRIPT_PATH` to the file's absolute path *before* starting your DAW, then insert **MPVST Script Host** (the instrument one) and play it. On Linux:

```bash
export MPVST_SCRIPT_PATH=$HOME/instruments/pluck.py
reaper &
```

Each new instance reads that file. Toggle `Reload Script` off and on to re-read it after an edit, without reopening the project. Saving the project embeds the script's text, so the project still opens if the file moves.

What each line is for:

- `on_event` receives every note, pressure and pitch-bend event at its exact sample position, and `vstaudio.output` tells the plug-in which node to pull audio from. The full list of events is in the [script reference](../reference/script-api.md).
- `MACRO_LABELS` and `PATCHES` are the script's declarations to the editor. This script has no macros, so it declares none and the editor draws no sliders.
- Notes are keyed by pitch here. A script that has to cope with overlapping notes on one pitch would key them by `note_id`, as the bundle's `default_instrument.py` does.

## Hear it without a DAW

You can render the script offline, with no host and no plug-in, to check that it makes sound. From a checkout of this repository, in a virtual environment with the audio packages from TestPyPI:

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ \
    pydevices-audiodsp pydevices-audioinstruments pydevices-audioeffects numpy
```

save this as `check_pluck.py` and run `python check_pluck.py` from the checkout's root:

```python
import sys
sys.path.insert(0, "examples/soundtrack")
from composer.harness import InstrumentRun, peak_rms

run = InstrumentRun("examples/pluck.py")
run.deliver(1, 0, 1, 60, 0.8, 0.0, 0)   # note on: middle C, velocity 0.8
peak, rms = peak_rms(run.pull_frames(48000))
print("peak %.2f, rms %.3f over one second" % (peak, rms))
```

```text
peak 0.40, rms 0.158 over one second
```

A peak of 0 means the script registered an output but never made sound. The offline path runs the same DSP as the plug-in's engine but not the plug-in itself, so it can't prove the plug-in works; [Hear what you wrote](../guides/hear-what-you-wrote.md) says what each render path does and does not tell you.

## Next

- [Write your own instruments and effects](../guides/write-a-script.md)
- [MPVST on Windows](../guides/windows.md) and [MPVST on Linux](../guides/linux.md) for where files go and how to develop a script with edit-and-reload.
- [Generate projects from code](../guides/generate-projects.md)
