# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The editor's Python half: the panel and the adapter it edits through.

The panel is audioinstruments' `panel_view`, which lays it out from `controlkit`,
frozen into the engine, with the MIDI Channel control added here. This package
keeps the half that knows the engine: `panel_adapter.EngineAdapter`, which the
panel edits through and which imports nothing from the engine itself.
"""

from .engine_panel import EnginePanel, build
from .panel_adapter import EngineAdapter

__all__ = ["EngineAdapter", "EnginePanel", "build"]
