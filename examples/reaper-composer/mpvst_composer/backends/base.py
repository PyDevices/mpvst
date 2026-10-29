# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Define the interface every renderer backend implements.

A backend takes a `Project` and writes it to a file. `ReaperRenderer` writes
a Reaper project and `OfflineRenderer` writes a WAV. Pass a backend class to
`Project.render`.

Needs: Python 3.8 or later.

Tested on: CPython 3.12.3 on Linux (WSL 2) with PyYAML 6.0.3, numpy 2.5.4
and pydevices-audiodsp 0.6.7 and audiocomponents 0.4.1. Exercised by
`converge.py`, `canon_16.py` and `from_yaml.py`.
"""

from abc import ABC, abstractmethod
from ..models import Project

class BaseRenderer(ABC):
    def __init__(self, project: Project):
        self.project = project
        
    @abstractmethod
    def render(self, filepath: str):
        """
        Renders the Project structure into the target format (e.g., .RPP)
        and writes it to the filepath.
        """
        pass
