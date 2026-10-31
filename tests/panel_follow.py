"""The editor's panel follows a patch change from the host.

Run by the engine itself (ctest mpvst_panel_follow), with the staged bundle
directory as its argument: the real EngineAdapter, the real panel, LVGL on
a display with no window, and a stub where vstui would be. A host program
change must move every encoder and every LED ring to the patch's macros,
and publish nothing back to the host.

    mpvst-engine tests/panel_follow.py <bundle directory>
"""

import sys

sys.path.insert(0, sys.argv[1])

import lvgl as lv

import mpvst_script_namespace

PATCHES = {
    0: ("Init", [64] * 16),
    1: ("Bright", [10 * i for i in range(13)] + [127, 0, 5]),
    2: ("Dark", [127 - 7 * i for i in range(16)]),
}
mpvst_script_namespace.namespace = {
    "NAME": "follow-probe",
    "MACRO_LABELS": tuple("Macro %d" % (i + 1) for i in range(16)),
    "PATCHES": PATCHES,
}


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
panel = build(adapter, group=lv.group_create())
lv.refr_now(display)

failures = []


def check(name, ok, why=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + why))
    if not ok:
        failures.append(name)


def lit(enc):
    return sum(1 for level in enc.lit() if level)


def expected_lit(value):
    return sum(1 for i in range(16) if value * 16 / 127 - i >= 24 / 255)


check("opens on patch 0", [e.value for e in panel.encoders] == PATCHES[0][1])
for program in (1, 2, 0):
    adapter.note_program(program)
    lv.refr_now(display)
    values = PATCHES[program][1]
    shown = [e.value for e in panel.encoders]
    check("host program %d: every encoder follows" % program, shown == values, "%s != %s" % (shown, values))
    rings = [lit(e) for e in panel.encoders]
    check("host program %d: every ring follows" % program, rings == [expected_lit(v) for v in values], str(rings))
    check("host program %d: its pad is lit" % program, panel.pads[program][3] == "lit")
check("nothing went back to the host", ui.edits == [], str(ui.edits))

print("RESULT " + ("FAIL" if failures else "OK"))
sys.exit(1 if failures else 0)
