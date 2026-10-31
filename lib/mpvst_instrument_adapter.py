"""Play an `audioinstruments` module inside the sidecar.

The instrument library lives in audiocomponents now, where it knows nothing
about this plug-in: an instrument is constructed through
`audioinstruments.create(name, sample_rate, ...)`, returning an object with
`note_on`/`note_off`/`set_macro`/`program_change` and an `output` to pull PCM
from. This module is the one place that knows both halves. It binds that
factory to `vstaudio`, so a script here shrinks to two lines. This is the
instrument side of audiodsp's component factory boundary:

    import mpvst_instrument_adapter
    mpvst_instrument_adapter.run("audioinstruments.tr808")

That line is what the plug-in builds for a named instrument, from the entry
`moduleinfo.json` carries for it - there are no generated shim files. The
soundtrack's piece-private instruments keep
their bodies and call `attach(create)` from a `__main__` guard instead,
because those files *are* the patches and are meant to be read and edited
in place.

Some instruments render ahead of the pull rather than inside it - a ring a
background step keeps full, or a graph whose notes and knobs land on its
next control pass. They say so with a `fill()` method. This seam calls it
after every event, so a note reaches the sound in the same block, and the
bootstrap calls `tick()` from the engine's housekeeping step, so the
instrument keeps moving while no events arrive. Instruments without `fill`
are untouched.

Units are the reason this file exists. `vstaudio` hands out normalized
0.0-1.0 floats, which is what the VST3 parameter API speaks; the
instrument API speaks MIDI 0-127, which is what a keyboard, a sequencer
and a saved patch speak. The conversion happens here, once, at the seam -
and it is a multiply, not a quantization, so a host automating a macro
with more than 7 bits of resolution keeps every bit of it.
"""

import sys

import vstaudio

# What the last `attach` built, and the module it came from. The editor panel
# reads these to label its controls and fill its patch list: an instrument
# already declares MACRO_LABELS and PATCHES for the library's own use, and the
# panel showing something other than those would be a second source of truth.
# Both are None for a script that builds its sound by hand rather than through
# this seam, and the panel falls back to generic names there.
instrument = None
module_name = None

# The attached instrument's `fill`, or None when it has none.
_fill = None


def _midi_byte(value):
    """Convert a normalized VST scalar to the provider's MIDI data byte."""
    value = max(0.0, min(1.0, float(value)))
    return int(value * 127.0 + 0.5)


def attach(create):
    """Build an instrument from `create` and wire it to the host.

    Returns the instrument, so a private script can keep a reference and
    poke at it - the soundtrack's `check_pump.py` does exactly that.
    """
    global instrument, _fill
    _fill = None
    instrument = create(vstaudio.sample_rate(), transport=vstaudio.transport)
    fill = getattr(instrument, "fill", None)
    labels = getattr(instrument, "MACRO_LABELS", None)
    if labels is None:
        labels = getattr(instrument, "macro_labels", ())

    def dispatch(event_type, channel, note_id, data0, value0, value1,
                 sample_position):
        if event_type == vstaudio.EVENT_NOTE_ON:
            # `value1` is a fractional pitch offset in semitones, already in
            # the units the instrument API wants - the host's own detune,
            # not something scaled to a controller range.
            instrument.note_on(data0, _midi_byte(value0), value1, channel,
                               note_id, sample_position)
        elif event_type == vstaudio.EVENT_NOTE_OFF:
            instrument.note_off(data0, channel, note_id, sample_position)
        elif event_type == vstaudio.EVENT_PARAMETER:
            if 0 <= data0 < len(labels):
                instrument.set_macro(data0, value0 * 127.0, channel, note_id,
                                     sample_position)
        elif event_type == vstaudio.EVENT_PROGRAM_CHANGE:
            instrument.program_change(data0, channel, note_id,
                                      sample_position)
        elif event_type == vstaudio.EVENT_PITCH_BEND:
            instrument.pitch_bend(int(max(0.0, min(1.0, float(value0))) *
                                    16383.0 + 0.5), channel,
                                  sample_position)
        elif event_type == vstaudio.EVENT_CONTROL_CHANGE:
            instrument.control_change(data0, _midi_byte(value0), channel,
                                      sample_position)
        elif event_type == vstaudio.EVENT_CHANNEL_PRESSURE:
            instrument.channel_pressure(_midi_byte(value0), channel,
                                        sample_position)
        elif event_type == vstaudio.EVENT_POLY_PRESSURE:
            instrument.poly_pressure(data0, _midi_byte(value0), channel,
                                     note_id,
                                     sample_position)
        # TRANSPORT is not an event to these instruments. The ones that sync
        # to tempo call the `transport` callable when they need a reading,
        # which is why it is passed to `create` above.
        if fill is not None:
            fill()

    vstaudio.on_event(dispatch)
    vstaudio.output(instrument.output)
    _fill = fill
    return instrument


def tick():
    """One housekeeping pass for the attached instrument: call its `fill`.

    A `fill` that raises is dropped, and the error reported the way a script
    error is; the engine goes on rendering what the instrument already has.
    """
    global _fill
    fill = _fill
    if fill is None:
        return
    try:
        fill()
    except Exception as exc:  # noqa: BLE001 - a broken fill must not stop the engine
        _fill = None
        vstaudio.error("{}: {}".format(type(exc).__name__, exc))


def run(name):
    """Import `name` fresh and attach the package factory for that module."""
    # The sidecar reloads a script by re-exec'ing this file, but an import
    # is cached: without this, editing an instrument and hitting reload
    # would rebuild the old code. Drop the whole library rather than just
    # the named module, so an edit to a shared helper counts as a reload
    # too. Costs a wavetable rebuild, which is what a reload is for.
    global module_name
    root = name.split(".")[0]
    for cached in list(sys.modules):
        if cached == root or cached.startswith(root + "."):
            del sys.modules[cached]
    __import__(name)
    import audioinstruments

    instrument_name = name.rsplit(".", 1)[-1]

    def factory(sample_rate, transport=None):
        return audioinstruments.create(
            instrument_name, sample_rate, transport=transport)

    module_name = name
    return attach(factory)
