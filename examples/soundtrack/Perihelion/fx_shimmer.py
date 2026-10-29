# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Load the Shimmer Hall effect, the classic shimmer, as an effect rack.

The effect itself is `ShimmerHall` in the `audioeffects` package. This file is
the small loader the plug-in builds for any library effect: the static
declarations a host reads out of an embedded source without importing
anything (name, categories, macro labels and the one patch), then a call
that hands the work to the library. A composition embeds it in a track's
`effects` list, and it takes four macros: Shimmer, Echo, Space and Tone.

Needs: MPVST installed with `audioeffects`.

Run it: embed it in a composition's `effects` list and render that piece,
from the `soundtrack` folder.

    python composer/preview.py --piece ShimmerLab shimmerlab.wav

Tested on: CPython 3.12.3 on Linux (WSL 2) with pydevices-audiodsp 0.6.7 and
audiocomponents 0.4.1, through the offline `EffectRun`; not loaded in a DAW.
"""

# What a host reads from the embedded source without importing it.
NAME = "fx_shimmer"
DISPLAY_NAME = "Shimmer Hall"
CATEGORIES = ("Effect Rack", "Reverb")
VERSION = "0.0.1"
VENDOR = "PyDevices"
MACRO_LABELS = ("Shimmer", "Echo", "Space", "Tone")
MACRO_MODES = {0: "UNIPOLAR", 1: "UNIPOLAR", 2: "UNIPOLAR", 3: "UNIPOLAR"}
PATCHES = {0: ("Shimmer Hall", (70, 57, 76, 79))}

# Hand the work to the library effect.
import mpvst_effect_adapter

mpvst_effect_adapter.run("ShimmerHall")
