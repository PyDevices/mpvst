"""The editor's Python half: the panel and the adapter it edits through.

The panel is audioinstruments' `panel_view`, which lays it out from `controlkit`,
frozen into the engine. This package keeps the half that knows
the engine: `panel_adapter.EngineAdapter`, which the panel edits through
and which imports nothing from the engine itself.
"""

from audioinstruments.panel_view import Panel, build

from .panel_adapter import EngineAdapter

__all__ = ["EngineAdapter", "Panel", "build"]
