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
    ENGINE_ERROR_SCRIPT, RELOAD, RELOAD_TIMEOUT_MS, EngineAdapter)
import mpvst_editor  # noqa: E402

failures = []


def check(condition, what):
    print(("ok   " if condition else "FAIL ") + what)
    if not condition:
        failures.append(what)


def adapter():
    clock = Clock()
    return EngineAdapter(FakeUi(), "probe.py", ticks_ms=clock), clock


def test_success():
    engine, clock = adapter()
    check(engine.engine_ready and engine.engine_error == 0,
          "a fresh adapter is ready with no error")
    engine.request_reload()
    reload_edits = [edit for edit in engine._ui.edits if edit[1] == RELOAD]
    check([edit[2] for edit in reload_edits if edit[0] == FakeUi.EDIT_PERFORM]
          == [1.0, 0.0], "a press still pulses the RELOAD parameter")
    check(not engine.engine_ready, "not ready once a reload is requested")
    clock.now += 500
    engine.tick()
    check(not engine.engine_ready, "still not ready while the reload is pending")
    engine.note_loaded("")
    check(engine.engine_ready and engine.engine_error == 0,
          "ready again, no error, once the engine has loaded the script")


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


for test in (test_success, test_failure, test_dropped_press,
             test_editor_keeps_panel, test_editor_rebuilds_panel,
             test_initial_load):
    test()

# The adapter must not have grown an engine dependency along the way.
check("vstaudio" not in vars(panel_adapter), "the adapter imports nothing from the engine")

if failures:
    print("{} check(s) failed".format(len(failures)))
    sys.exit(1)
print("all checks passed")
