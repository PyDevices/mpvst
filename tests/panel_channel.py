# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The editor's panel shows the MIDI channel and changes it, both ways.

Run by the engine itself (ctest mpvst_panel_channel), with the staged bundle
directory as its argument: the real EngineAdapter, the real panel, LVGL on
a display with no window, and a stub where vstui would be. A click on the
control must publish the next step as one edit of the MIDI Channel parameter,
and a channel the host reports must move the control and publish nothing.

    mpvst-engine tests/panel_channel.py <bundle directory>
"""

import sys

sys.path.insert(0, sys.argv[1])

import lvgl as lv

import mpvst_script_namespace

mpvst_script_namespace.namespace = {
    "NAME": "channel-probe",
    "MACRO_LABELS": tuple("Macro %d" % (i + 1) for i in range(16)),
}

MIDI_CHANNEL = 5


class StubUi:
    EDIT_BEGIN = 0
    EDIT_PERFORM = 1
    EDIT_END = 2

    def __init__(self):
        self.edits = []

    def edit(self, kind, parameter, value):
        self.edits.append((kind, parameter, value))


lv.init()
frame = bytearray(800 * 480 * 2)
display = lv.display_create(800, 480)
display.set_color_format(lv.COLOR_FORMAT.RGB565)
display.set_flush_cb(lambda d, area, pixels: d.flush_ready())
display.set_buffers(frame, None, len(frame), lv.DISPLAY_RENDER_MODE.DIRECT)

from mpvst_panel import EngineAdapter, build  # noqa: E402

ui = StubUi()
adapter = EngineAdapter(ui, ticks_ms=lambda: 0)
adapter.channel = 4
panel = build(adapter, group=lv.group_create())
lv.refr_now(display)

failures = []


def check(name, ok, why=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + why))
    if not ok:
        failures.append(name)


def shown():
    return panel._channel_text.get_text()


def sent():
    return [e for e in ui.edits if e[1] == MIDI_CHANNEL]


check("opens on the channel the host holds", shown() == "4", shown())

panel._channel_button.send_event(lv.EVENT.CLICKED, None)
lv.refr_now(display)
check("a click shows the next channel", shown() == "5", shown())
check("and publishes it as one complete edit",
      sent() == [(StubUi.EDIT_BEGIN, MIDI_CHANNEL, 5 / 16.0),
                 (StubUi.EDIT_PERFORM, MIDI_CHANNEL, 5 / 16.0),
                 (StubUi.EDIT_END, MIDI_CHANNEL, 5 / 16.0)], str(sent()))

adapter.note_channel(5)
check("the host's echo publishes nothing more", len(sent()) == 3, str(sent()))

adapter.note_channel(12)
lv.refr_now(display)
check("a channel from the host moves the control", shown() == "12", shown())
check("and publishes nothing", len(sent()) == 3, str(sent()))

adapter.note_channel(0)
check("step 0 reads All", shown() == "ALL", shown())

panel.choose_channel(16)
panel._channel_button.send_event(lv.EVENT.CLICKED, None)
check("a click on 16 wraps round to All", shown() == "ALL", shown())
check("and publishes step 0", sent()[-1] == (StubUi.EDIT_END, MIDI_CHANNEL, 0.0),
      str(sent()[-1]))

print("RESULT " + ("FAIL" if failures else "OK"))
sys.exit(1 if failures else 0)
