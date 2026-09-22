#!/usr/bin/env python3
"""Report the held-note level of each render, as a fraction of full scale.

matrix_instrument.py renders a constant 0.125 + 0.125 * macro01 while a note
is held, and its own default for macro01 is 0.0. So 0.1250 means the script
kept its own value and 0.1875 means 0.5 was replayed over it. REAPER renders
24-bit here, which is why this decodes three bytes rather than trusting a
width it assumed.
"""
import sys
import wave


def sample_at(path, seconds):
    with wave.open(path, "rb") as w:
        rate, width, ch = w.getframerate(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    off = int(rate * seconds) * ch * width
    chunk = raw[off:off + width]
    value = int.from_bytes(chunk, "little", signed=True)
    return value / float(1 << (8 * width - 1)), width


MEANING = {"0.1250": "the script's own default survived (macro01 = 0.0)",
           "0.1875": "0.5 was replayed over it (macro01 = 0.5)",
           "0.0000": "silence -- nothing was proven"}

for path in sorted(sys.argv[1:]):
    level, width = sample_at(path, 1.5)
    key = "%.4f" % abs(level)
    print("%-22s %d-bit  level@1.5s = %s   %s"
          % (path.rsplit("/", 1)[-1], width * 8, key,
             MEANING.get(key, "unexpected value")))
