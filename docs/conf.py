# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Sphinx configuration for the mpvst documentation.

Everything shared by the PyDevices documentation projects (theme, top bar,
Markdown setup) comes from omnipython-docs. mpvst is a tool, not a library,
so there is no API reference to generate.
"""

from omnipython_docs import configure

globals().update(configure(
    "mpvst", __file__,
    repo="PyDevices/mpvst", edit_path="docs",
    version_file="../VERSION",
))


# index.md is plain Markdown so the docs read on GitHub too; the site
# navigation lives in contents.md.
master_doc = "contents"
