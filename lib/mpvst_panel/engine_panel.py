# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The generic panel, with the instance's MIDI channel on it.

`audioinstruments.panel_view.Panel` is the same panel on a desktop and in a
board's firmware, and it knows nothing about a host. The MIDI Channel is a
host parameter, so its control lives here: a header button beside FINE that
shows All or 1 to 16 and steps through them on a click, drawn the way the
panel draws its own buttons.
"""

import lvgl as lv
from audioinstruments.panel_view import Panel
from controlkit._draw import box as _box
from controlkit._draw import fill as _fill
from controlkit._draw import label as _label
from controlkit._safe import safe

from .panel_adapter import CHANNEL_STEPS


def channel_name(step):
    """What the control shows for a MIDI Channel step: All, or 1 to 16."""
    return "ALL" if step == 0 else "%d" % step


class EnginePanel(Panel):
    """`Panel` plus a MIDI Channel control, kept in step with the host.

    The adapter's `channel` is the step the host holds, and its `set_channel`
    publishes a change. A host change arrives as the adapter's "channel"
    notification, and moves the control without publishing anything.
    """

    def __init__(self, adapter, **options):
        self._channel_button = None
        self._channel_text = None
        super().__init__(adapter, **options)
        self._build_channel()

    def _build_channel(self):
        theme = self.theme
        s = self._s
        header = self.header
        fine = self.buttons["FINE"][0]
        width = fine.get_width()
        gap = 4 if self.compact else s(8)
        step_x = width + gap
        x = fine.get_x() - step_x
        # Make room by moving the display and the name plate left: the
        # buttons stay where the panel put them.
        bezel = self.display.obj.get_parent().get_parent()
        bezel.set_x(bezel.get_x() - step_x)
        if not self.compact:
            self.title.set_width(max(1, self.title.get_width() - step_x))
            self.subtitle.set_width(max(1, self.subtitle.get_width() - step_x))
        height = header.get_height()
        if self.compact:
            button = _box(header, x, (height - 24) // 2, width, 24)
        else:
            legend = _label(header, "MIDI CH", theme["header_legend"], None, 0)
            legend.set_size(width, 16)
            legend.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
            legend.set_pos(x, s(12))
            button = _box(header, x, s(34), width, s(26))
        button.add_flag(lv.obj.FLAG.CLICKABLE)
        _fill(button, theme["button"], theme["button_bottom"])
        button.set_style_radius(s(4), 0)
        button.set_style_border_width(1, 0)
        button.set_style_border_color(lv.color_hex(theme["pad_edge"]), 0)
        button.set_style_shadow_width(s(4), 0)
        button.set_style_shadow_offset_y(s(2), 0)
        button.set_style_shadow_opa(170, 0)
        button.set_style_shadow_color(lv.color_hex(0), 0)
        button.set_style_translate_y(1, lv.STATE.PRESSED)
        button.set_style_shadow_offset_y(0, lv.STATE.PRESSED)
        button.set_style_outline_width(s(2), lv.STATE.FOCUSED)
        button.set_style_outline_color(lv.color_hex(theme["legend_lit"]), lv.STATE.FOCUSED)
        text = _label(button, "", theme["button_text"], None, 0)
        text.center()
        button.add_event_cb(safe(self._on_channel_click), lv.EVENT.CLICKED, None)
        button.add_event_cb(safe(self._on_channel_key), lv.EVENT.KEY, None)
        if self.group is not None:
            self.group.add_obj(button)
        self._channel_button = button
        self._channel_text = text
        self._show_channel(self.adapter.channel)

    # ---- the engine's side -----------------------------------------------

    def _apply_external(self, kind, index, value):
        if kind == "channel":
            self._show_channel(value)
            return
        super()._apply_external(kind, index, value)

    def _show_channel(self, step):
        self._channel_text.set_text(channel_name(step))
        self._channel_text.center()

    # ---- the user's side ---------------------------------------------------

    def choose_channel(self, step):
        """Pick MIDI Channel *step* (0 for All, 1 to 16) as if it were clicked."""
        step = min(max(step, 0), CHANNEL_STEPS - 1)
        self._show_channel(step)
        if not self._echoing:
            self.adapter.set_channel(step)
        self._flash("MIDI CH %s" % channel_name(step))

    def _on_channel_click(self, _event):
        self.choose_channel((self.adapter.channel + 1) % CHANNEL_STEPS)

    def _on_channel_key(self, event):
        key = event.get_key()
        if key in (lv.KEY.RIGHT, lv.KEY.UP):
            self.choose_channel(self.adapter.channel + 1)
        elif key in (lv.KEY.LEFT, lv.KEY.DOWN):
            self.choose_channel(self.adapter.channel - 1)


def build(adapter, screen=None, group=None, **options):
    """Build the panel for *adapter* and return it.

    *options* are the keywords `Panel` takes: ``theme``, ``title``,
    ``subtitle``, ``on_close``, ``two_wheels``.
    """
    return EnginePanel(adapter, screen=screen, group=group, **options)
