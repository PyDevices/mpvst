#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Check that the pad's sidechain duck is locked to the beat in a render.

Takes a stretch of movement III of an Automata render, extracts the
amplitude envelope of the band the pad occupies, and measures the strongest
modulation frequency. If the engine saw a sane transport, the peak sits at
the beat rate (2.1 Hz at 126 bpm) rather than drifting free. The program
prints the peak and "PUMP LOCKED" or "PUMP NOT LOCKED", and exits non-zero
when it is not locked.

Needs: Python 3 with numpy, and a stereo WAV of Automata, such as one rendered with `composer/preview.py`
or bounced from Reaper.

Run it: from the `soundtrack` folder,

    python composer/preview.py --piece Automata automata.wav
    python Automata/check_pump.py automata.wav

Tested on: CPython 3.12.3 on Linux (WSL 2) with numpy 2.5.4, on an Automata
render from `composer/preview.py`.
"""

import sys
import wave
from pathlib import Path

import numpy as np

# Load the Automata composition for its tempo map.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "composer"))
from pieces import load_piece  # noqa: E402

C, _ = load_piece("automata")
SR = C.SAMPLE_RATE


def main():
    # Read the WAV, whatever its sample width, as floats from -1 to 1.
    with wave.open(sys.argv[1]) as handle:
        width = handle.getsampwidth()
        raw = handle.readframes(handle.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        data = v.astype(np.float32) / 8388608.0
    else:
        data = np.frombuffer(raw, dtype=np.float32)
    # Fold to mono.
    mono = data.reshape(-1, 2).mean(axis=1)

    # Movement III bars 5-13: pads pumping, before the arps pile in.
    s0 = int(C.beats_to_seconds(C.b3(5)) * SR)
    s1 = int(C.beats_to_seconds(C.b3(13)) * SR)
    seg = mono[s0:s1]

    # Take the amplitude envelope in 10 ms steps, then its spectrum.
    env = np.abs(seg)
    hop = 480  # 10 ms
    frames = env[:len(env) // hop * hop].reshape(-1, hop).mean(axis=1)
    frames -= frames.mean()
    spec = np.abs(np.fft.rfft(frames * np.hanning(len(frames))))
    freqs = np.fft.rfftfreq(len(frames), hop / SR)
    # Look for the strongest modulation between 0.8 and 5 Hz.
    lo = np.searchsorted(freqs, 0.8)
    hi = np.searchsorted(freqs, 5.0)
    peak_hz = freqs[lo + int(np.argmax(spec[lo:hi]))]
    # Compare it with the beat rate, allowing for half and double time.
    beat_hz = 126.0 / 60.0
    print("envelope modulation peak: %.3f Hz (beat rate %.3f Hz)"
          % (peak_hz, beat_hz))
    ok = abs(peak_hz - beat_hz) < 0.15 or abs(peak_hz - beat_hz / 2) < 0.1 \
        or abs(peak_hz - beat_hz * 2) < 0.2
    print("PUMP %s" % ("LOCKED" if ok else "NOT LOCKED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
