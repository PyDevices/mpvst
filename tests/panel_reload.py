# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The panel's view of the engine across a reload, success and failure.

Runs under CPython with stand-ins for the engine's `vstaudio` and `vstui`
modules: what is under test is the adapter's state and the editor's wiring,
not drawing. The real engine path is covered by the editor smoke test.
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))


class FakeUi:
    EDIT_BEGIN = 1
    EDIT_PERFORM = 2
    EDIT_END = 3

    def __init__(self):
        self.edits = []

    def edit(self, kind, parameter, value):
        self.edits.append((kind, parameter, value))


class Clock:
    def __init__(self):
        self.now = 1000

    def __call__(self):
        return self.now


def install_stubs():
    vstaudio = types.ModuleType("vstaudio")
    vstaudio.observers = []
    vstaudio.observe = vstaudio.observers.append
    vstui = types.ModuleType("vstui")
    sys.modules["vstaudio"] = vstaudio
    sys.modules["vstui"] = vstui
    namespace = types.ModuleType("mpvst_script_namespace")
    namespace.namespace = None
    sys.modules["mpvst_script_namespace"] = namespace
    # The package's __init__ brings in the panel, which needs LVGL. The
    # adapter doesn't, so the package is entered without running it.
    package = types.ModuleType("mpvst_panel")
    package.__path__ = [os.path.join(HERE, "..", "lib", "mpvst_panel")]
    sys.modules["mpvst_panel"] = package
    return vstaudio, namespace


VSTAUDIO, SCRIPT = install_stubs()

from mpvst_panel import panel_adapter  # noqa: E402
from mpvst_panel.panel_adapter import (  # noqa: E402
    ENGINE_ERROR_SCRIPT, MIDI_CHANNEL, RELOAD, RELOAD_TIMEOUT_MS, EngineAdapter)
import mpvst_editor  # noqa: E402

failures = []


def check(condition, what):
    print(("ok   " if condition else "FAIL ") + what)
    if not condition:
        failures.append(what)


def adapter():
    clock = Clock()
    return EngineAdapter(FakeUi(), "probe.py", ticks_ms=clock), clock


def reload_values(engine):
    return [edit[2] for edit in engine._ui.edits
            if edit[1] == RELOAD and edit[0] == FakeUi.EDIT_PERFORM]


def test_success():
    engine, clock = adapter()
    check(engine.engine_ready and engine.engine_error == 0,
          "a fresh adapter is ready with no error")
    engine.request_reload()
    check(reload_values(engine) == [1.0],
          "a press holds RELOAD at 1, so a host batching edits keeps the edge")
    check(not engine.engine_ready, "not ready once a reload is requested")
    clock.now += 500
    engine.tick()
    check(not engine.engine_ready, "still not ready while the reload is pending")
    check(reload_values(engine) == [1.0], "RELOAD stays held while pending")
    engine.note_loaded("")
    check(engine.engine_ready and engine.engine_error == 0,
          "ready again, no error, once the engine has loaded the script")
    check(reload_values(engine) == [1.0, 0.0],
          "RELOAD returns to 0 once the reload ends")
    engine.request_reload()
    check(reload_values(engine) == [1.0, 0.0, 1.0],
          "the next press is a fresh edge")


def test_failure():
    engine, _clock = adapter()
    engine.request_reload()
    engine.note_loaded("NameError: name 'oops' isn't defined")
    check(engine.engine_ready, "a failed load still ends the reload")
    check(engine.engine_error == ENGINE_ERROR_SCRIPT,
          "a failed load sets engine_error")
    check(engine.engine_message.startswith("NameError"),
          "engine_message says what the script raised")
    engine.request_reload()
    check(not engine.engine_ready and engine.engine_error == ENGINE_ERROR_SCRIPT,
          "the error stays up while the next reload runs")
    engine.note_loaded("")
    check(engine.engine_ready and engine.engine_error == 0
          and engine.engine_message == "",
          "the next good load clears the error")


def test_dropped_press():
    engine, clock = adapter()
    engine.request_reload()
    clock.now += RELOAD_TIMEOUT_MS - 1
    engine.tick()
    check(not engine.engine_ready, "not given up just before the timeout")
    clock.now += 1
    engine.tick()
    check(engine.engine_ready and engine.engine_error == 0,
          "a reload that never comes is given up after the timeout")
    check(reload_values(engine) == [1.0, 0.0],
          "giving up returns RELOAD to 0")


def test_close_releases_reload():
    engine, _clock = adapter()
    engine.request_reload()
    engine.close_all()
    check(reload_values(engine) == [1.0, 0.0],
          "closing the panel mid-reload returns RELOAD to 0")


def test_editor_keeps_panel():
    SCRIPT.namespace = {"MACRO_LABELS": ("Cut", "Res")}
    editor = mpvst_editor.Editor("probe.py")
    engine, _clock = adapter()
    editor._adapter = engine
    editor._panel = object()
    del VSTAUDIO.observers[:]
    engine.request_reload()
    SCRIPT.namespace = {"MACRO_LABELS": ("Cut", "Res")}
    editor.script_reloaded("probe.py", "")
    check(editor._adapter is engine and editor._panel is not None,
          "same declarations: the panel and its adapter stay")
    check(engine.engine_ready and engine.engine_error == 0,
          "the kept adapter hears the reload end")
    check(VSTAUDIO.observers == [editor._observe],
          "the kept panel observes the new script")

    engine.request_reload()
    editor.script_reloaded("probe.py", "SyntaxError: invalid syntax")
    check(editor._adapter is engine and engine.engine_error == ENGINE_ERROR_SCRIPT,
          "a failed reload reaches the kept adapter")
    editor.script_reloaded("probe.py", "")
    check(engine.engine_error == 0, "and the next good reload clears it")


def test_editor_rebuilds_panel():
    SCRIPT.namespace = {"MACRO_LABELS": ("Cut", "Res")}
    editor = mpvst_editor.Editor("probe.py")
    engine, _clock = adapter()
    editor._adapter = engine
    editor._panel = object()
    engine.request_reload()
    SCRIPT.namespace = {"MACRO_LABELS": ("Cut", "Res", "Drive")}
    editor.script_reloaded("probe.py", "ValueError: bad patch")
    check(editor._adapter is None and editor._panel is None,
          "changed declarations: the panel is released for a rebuild")
    rebuilt = EngineAdapter(FakeUi(), "probe.py", ticks_ms=Clock())
    rebuilt.note_loaded(editor._load_error)
    check(rebuilt.engine_ready and rebuilt.engine_error == ENGINE_ERROR_SCRIPT,
          "the rebuilt panel's adapter starts with the load's error")


def test_initial_load():
    editor = mpvst_editor.Editor("probe.py")
    editor.script_loaded("ImportError: no module named 'synthio'")
    check(editor._load_error.startswith("ImportError"),
          "a first load that failed is kept for the panel built later")


def channel_edits(engine):
    return [edit for edit in engine._ui.edits if edit[1] == MIDI_CHANNEL]


def test_channel_from_panel():
    engine, _clock = adapter()
    heard = []
    engine.on_external_change(lambda *args: heard.append(args))
    engine.set_channel(3)
    check(engine.channel == 3, "choosing a channel on the panel sets it")
    check(channel_edits(engine) == [(FakeUi.EDIT_BEGIN, MIDI_CHANNEL, 3 / 16.0),
                                    (FakeUi.EDIT_PERFORM, MIDI_CHANNEL, 3 / 16.0),
                                    (FakeUi.EDIT_END, MIDI_CHANNEL, 3 / 16.0)],
          "and publishes it to the host as one complete edit of step 3 of 16")
    engine.note_channel(3)
    check(heard == [] and len(channel_edits(engine)) == 3,
          "the host's echo of that change moves nothing and publishes nothing")
    engine.set_channel(0)
    check(channel_edits(engine)[-1] == (FakeUi.EDIT_END, MIDI_CHANNEL, 0.0),
          "All is the first step")


def test_channel_from_host():
    engine, _clock = adapter()
    heard = []
    engine.on_external_change(lambda *args: heard.append(args))
    engine.note_channel(16)
    check(engine.channel == 16 and heard == [("channel", 0, 16)],
          "the host moving the channel moves the panel's control")
    check(channel_edits(engine) == [], "and publishes nothing back")
    engine.note_channel(17)
    engine.note_channel(-1)
    check(engine.channel == 16, "a step outside All and 1 to 16 is ignored")


def test_editor_hears_channel_before_a_panel():
    editor = mpvst_editor.Editor("probe.py")
    editor._observe(mpvst_editor.EVENT_MIDI_CHANNEL, 0, 0, 5, 5 / 16.0, 0.0, 0)
    check(editor._channel == 5,
          "the editor keeps the host's channel while no panel exists")
    engine, _clock = adapter()
    heard = []
    engine.on_external_change(lambda *args: heard.append(args))
    editor._adapter = engine
    editor._observe(mpvst_editor.EVENT_MIDI_CHANNEL, 0, 0, 9, 9 / 16.0, 0.0, 0)
    check(editor._channel == 9 and engine.channel == 9
          and heard == [("channel", 0, 9)],
          "and passes a change on to the panel once there is one")


for test in (test_success, test_failure, test_dropped_press, test_close_releases_reload,
             test_editor_keeps_panel, test_editor_rebuilds_panel,
             test_initial_load, test_channel_from_panel, test_channel_from_host,
             test_editor_hears_channel_before_a_panel):
    test()

# The adapter must not have grown an engine dependency along the way.
check("vstaudio" not in vars(panel_adapter), "the adapter imports nothing from the engine")

if failures:
    print("{} check(s) failed".format(len(failures)))
    sys.exit(1)
print("all checks passed")
