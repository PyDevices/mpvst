# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Say whether the editor's surface is there, and how big it is.

vstui is the engine's end of the editor window: a framebuffer the host's view
shows, and the pointer and wheel input and parameter edits that flow back.
The surface exists only while the plug-in's editor is open. Without one,
available() is False and the size constants still say how large a panel can be.

Needs: the MPVST engine, started on its own.

Run it:
    mpvst-engine vstui_simpletest.py

Tested on: the MPVST engine for Windows.
"""

import vstui

# Print which build of the module this is, as an issue report would want.
print("vstui", vstui.__revision__)

# Say whether an editor surface is attached, and how large one can be.
print("editor surface attached:", vstui.available())
print("default panel: %d x %d" % (vstui.DEFAULT_WIDTH, vstui.DEFAULT_HEIGHT))
print("largest panel: %d x %d" % (vstui.MAX_WIDTH, vstui.MAX_HEIGHT))
